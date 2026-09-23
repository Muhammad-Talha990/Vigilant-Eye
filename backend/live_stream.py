"""
In-process live camera sessions for Phase C1.

Supports:
  - webcam:0 / 0  (local camera)
  - file paths    (demo clips)
  - rtsp://...    (IP cameras; browser cannot play RTSP directly)

Optional YOLO overlay + confirmed detection persistence.

Speed notes:
  - Inference at fixed imgsz (default 416)
  - Detect every N frames; reuse last boxes between inferences
  - COCO mode filters to exam-relevant classes only
  - Persist runs in a background thread so MJPEG stays smooth
"""

from __future__ import annotations

import os
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
AI_DIR = ROOT / "ai"
if str(AI_DIR) not in sys.path:
    sys.path.insert(0, str(AI_DIR))

PENDING_DIR = Path(__file__).resolve().parent / "uploads" / "pending_persist"
PENDING_DIR.mkdir(parents=True, exist_ok=True)

from detection_policy import (  # noqa: E402
    Decision,
    SessionTracker,
    annotate_detection_dict,
    spatial_bin,
)
from posture_analysis import (  # noqa: E402
    analyze_heads,
    draw_head_overlays,
    mediapipe_status,
    observation_to_dict,
)
from suspicion_score import SuspicionEngine  # noqa: E402
from ufm_classes import resolve_weights  # noqa: E402

LIVE_POSTURE = os.getenv("LIVE_POSTURE", "1").strip().lower() not in {
    "0",
    "false",
    "no",
}
POSTURE_EVERY = max(1, int(os.getenv("UFM_POSTURE_EVERY", "3")))

# Live inference tuning (override via env)
LIVE_IMGSZ = int(os.getenv("LIVE_IMGSZ", "640"))
LIVE_DETECT_EVERY = max(1, int(os.getenv("LIVE_DETECT_EVERY", "2")))
LIVE_JPEG_QUALITY = int(os.getenv("LIVE_JPEG_QUALITY", "70"))
# COCO class ids that matter for exam UFM (skips persons/chairs → faster + cleaner)
# 63 laptop, 64 mouse, 66 keyboard, 67 cell phone, 73 book
COCO_UFM_CLASS_IDS = [63, 64, 66, 67, 73]


def _redact_source(url: str | None) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    # Hide credentials in rtsp://user:pass@host/...
    if "://" in raw and "@" in raw.split("://", 1)[1]:
        scheme, rest = raw.split("://", 1)
        hostpart = rest.split("@", 1)[-1]
        return f"{scheme}://***@{hostpart}"
    # Do not expose absolute local paths in production cards
    if raw.lower().startswith(("webcam", "cam", "rtsp")):
        return raw
    if Path(raw).suffix.lower() in {".mp4", ".avi", ".mkv", ".mov"}:
        return f"file:{Path(raw).name}"
    return raw.split("/")[-1] if "/" in raw or "\\" in raw else raw


def _compute_ai_status(session: CameraSession) -> str:
    if session.model_error:
        return "error"
    if session.error and not session.running:
        return "error"
    if not session.running:
        return "idle"
    if session.error:
        return "error"
    if not session.detect:
        return "unavailable"
    if not session.model_ready:
        return "starting"
    if session.frame_index < 3:
        return "starting"
    return "active"


def resolve_capture_source(stream_url: str) -> int | str:
    """Map DB stream_url to OpenCV VideoCapture argument."""
    raw = (stream_url or "").strip()
    if not raw:
        raise ValueError("Empty stream_url")

    lower = raw.lower()
    if lower in ("webcam", "cam", "local"):
        return 0
    if lower.startswith("webcam:"):
        return int(lower.split(":", 1)[1])
    if raw.isdigit():
        return int(raw)

    path = Path(raw)
    if path.is_file():
        return str(path.resolve())

    # Relative to project root (common when API runs from backend/)
    rooted = ROOT / raw
    if rooted.is_file():
        return str(rooted.resolve())

    alt = ROOT / "ai" / "samples" / Path(raw).name
    if alt.is_file():
        return str(alt.resolve())

    return raw


@dataclass
class LiveDetectionEvent:
    label: str
    confidence: float
    frame_index: int
    timestamp: str
    persisted_id: int | None = None
    decision: str = "CONFIRM"
    raw_label: str | None = None
    save_status: str = "none"  # none | pending | saved | failed


@dataclass
class PendingPersist:
    """Bounded in-memory retry queue for failed / in-flight incident saves."""

    label: str
    confidence: float
    confirmed: bool
    raw_label: str | None
    event_key: str
    frame_jpeg: bytes | None = None
    attempts: int = 0
    last_error: str | None = None
    created_at: float = field(default_factory=time.monotonic)
    is_demo: bool = False


PENDING_PERSIST_MAX = 16
PENDING_PERSIST_MAX_ATTEMPTS = 5


def _pending_meta_path(camera_pk: int, event_key: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in event_key)[:120]
    return PENDING_DIR / str(camera_pk) / f"{safe}.json"


def _spill_pending(camera_pk: int, pending: "PendingPersist") -> None:
    """Write pending item to disk so it survives process restart."""
    import json

    folder = PENDING_DIR / str(camera_pk)
    folder.mkdir(parents=True, exist_ok=True)
    meta = _pending_meta_path(camera_pk, pending.event_key)
    jpg = meta.with_suffix(".jpg")
    if pending.frame_jpeg:
        try:
            jpg.write_bytes(pending.frame_jpeg)
        except OSError:
            pass
    payload = {
        "label": pending.label,
        "confidence": pending.confidence,
        "confirmed": pending.confirmed,
        "raw_label": pending.raw_label,
        "event_key": pending.event_key,
        "attempts": pending.attempts,
        "last_error": pending.last_error,
        "is_demo": pending.is_demo,
        "jpg": jpg.name if jpg.exists() else None,
    }
    try:
        meta.write_text(json.dumps(payload), encoding="utf-8")
    except OSError:
        pass


def _delete_pending_spill(camera_pk: int, event_key: str) -> None:
    meta = _pending_meta_path(camera_pk, event_key)
    jpg = meta.with_suffix(".jpg")
    for p in (meta, jpg):
        try:
            if p.exists():
                p.unlink()
        except OSError:
            pass


def _load_pending_spills(camera_pk: int) -> list["PendingPersist"]:
    import json

    folder = PENDING_DIR / str(camera_pk)
    if not folder.is_dir():
        return []
    items: list[PendingPersist] = []
    for meta in sorted(folder.glob("*.json"))[:PENDING_PERSIST_MAX]:
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
            frame_jpeg = None
            jpg_name = data.get("jpg")
            if jpg_name:
                jpg = folder / jpg_name
                if jpg.is_file():
                    frame_jpeg = jpg.read_bytes()
            items.append(
                PendingPersist(
                    label=str(data.get("label") or "unknown"),
                    confidence=float(data.get("confidence") or 0.0),
                    confirmed=bool(data.get("confirmed", True)),
                    raw_label=data.get("raw_label"),
                    event_key=str(data.get("event_key") or meta.stem),
                    frame_jpeg=frame_jpeg,
                    attempts=int(data.get("attempts") or 0),
                    last_error=data.get("last_error"),
                    is_demo=bool(data.get("is_demo", False)),
                )
            )
        except Exception:  # noqa: BLE001
            continue
    return items


@dataclass
class CameraSession:
    camera_pk: int
    camera_code: str
    name: str
    stream_url: str
    detect: bool = False
    persist: bool = False
    conf: float = 0.28
    min_frames: int = 3
    persist_cooldown_sec: float = 90.0
    stop_event: threading.Event = field(default_factory=threading.Event)
    thread: threading.Thread | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)
    latest_jpeg: bytes | None = None
    latest_labels: list[dict[str, Any]] = field(default_factory=list)
    recent_events: list[LiveDetectionEvent] = field(default_factory=list)
    pending_persists: list[PendingPersist] = field(default_factory=list)
    frame_index: int = 0
    error: str | None = None
    model_error: str | None = None
    running: bool = False
    weights_mode: str = "coco"
    opened_source: str = ""
    # Short ring buffer of annotated frames for CLIP evidence
    frame_buffer: list[Any] = field(default_factory=list)
    frame_buffer_max: int = 24
    tracker: Any = None
    suspicion: Any = None
    latest_posture: list[dict[str, Any]] = field(default_factory=list)
    latest_scores: list[dict[str, Any]] = field(default_factory=list)
    is_demo: bool = False
    ai_status: str = "idle"
    model_ready: bool = False
    persist_error: str | None = None
    last_persist_ok: bool | None = None
    room_label: str = ""


class LiveStreamManager:
    """Process-wide registry of active camera sessions."""

    def __init__(self) -> None:
        self._sessions: dict[int, CameraSession] = {}
        self._lock = threading.Lock()
        self._model = None
        self._model_path: str | None = None
        self._model_mode: str = "coco"
        self._custom_model = None
        self._custom_model_path: str | None = None
        self._model_lock = threading.Lock()

    def status(self) -> dict[str, Any]:
        with self._lock:
            sessions = []
            for s in self._sessions.values():
                sessions.append(
                    {
                        "camera_id": s.camera_pk,
                        "camera_code": s.camera_code,
                        "name": s.name,
                        "room_label": s.room_label,
                        "stream_url_redacted": _redact_source(s.stream_url),
                        "opened_source_redacted": _redact_source(s.opened_source),
                        "running": s.running,
                        "detect": s.detect,
                        "persist": s.persist,
                        "is_demo": s.is_demo,
                        "weights_mode": s.weights_mode,
                        "model_ready": s.model_ready,
                        "ai_status": _compute_ai_status(s),
                        "monitoring_status": (
                            "monitoring"
                            if s.running and not s.error
                            else ("error" if s.error else "stopped")
                        ),
                        "frame_index": s.frame_index,
                        "error": s.error,
                        "persist_error": s.persist_error,
                        "last_persist_ok": s.last_persist_ok,
                        "pending_persists": len(s.pending_persists),
                        "model_error": s.model_error,
                        "latest_labels": list(s.latest_labels),
                        "latest_posture": list(s.latest_posture),
                        "latest_scores": list(s.latest_scores),
                        "posture_engine": mediapipe_status(),
                        "recent_events": [
                            {
                                "label": e.label,
                                "confidence": e.confidence,
                                "frame_index": e.frame_index,
                                "timestamp": e.timestamp,
                                "persisted_id": e.persisted_id,
                                "decision": e.decision,
                                "raw_label": e.raw_label,
                                "save_status": e.save_status,
                            }
                            for e in s.recent_events[-10:]
                        ],
                    }
                )
            return {
                "active_sessions": len(sessions),
                "weights_mode": self._model_mode if self._model is not None else None,
                "sessions": sessions,
            }

    def get_session(self, camera_pk: int) -> CameraSession | None:
        with self._lock:
            return self._sessions.get(camera_pk)

    def start(
        self,
        *,
        camera_pk: int,
        camera_code: str,
        name: str,
        stream_url: str,
        detect: bool = True,
        persist: bool = True,
        conf: float = 0.25,
        min_frames: int = 3,
        source_override: str | None = None,
        is_demo: bool = False,
        room_label: str = "",
    ) -> CameraSession:
        self.stop(camera_pk)

        url = (source_override or stream_url).strip()
        session = CameraSession(
            camera_pk=camera_pk,
            camera_code=camera_code,
            name=name,
            stream_url=url,
            detect=detect,
            persist=persist,
            conf=conf,
            min_frames=min_frames,
            persist_cooldown_sec=45.0,
            tracker=SessionTracker(
                confirm_frames=max(3, min_frames),
                review_frames=max(2, min_frames - 1),
                cooldown_sec=45.0,
            ),
            suspicion=SuspicionEngine(),
            is_demo=is_demo,
            room_label=room_label or "",
            ai_status="starting" if detect else "unavailable",
        )

        if detect:
            try:
                mode = self._ensure_model()
                session.weights_mode = mode
                session.model_ready = True
                session.model_error = None
                session.ai_status = "starting"
            except Exception as exc:  # noqa: BLE001
                session.model_ready = False
                session.model_error = f"AI model unavailable: {exc}"
                session.ai_status = "error"
                # Still allow video stream without claiming AI is active
                session.detect = False
        else:
            session.model_ready = False
            session.ai_status = "unavailable"

        thread = threading.Thread(
            target=self._run_loop,
            args=(session,),
            name=f"live-cam-{camera_pk}",
            daemon=True,
        )
        session.thread = thread

        with self._lock:
            self._sessions[camera_pk] = session

        # Restore durable pending saves from previous process crash
        for spilled in _load_pending_spills(camera_pk):
            with session.lock:
                if len(session.pending_persists) >= PENDING_PERSIST_MAX:
                    break
                # Align demo flag with this session if restarting same camera
                spilled.is_demo = bool(is_demo)
                session.pending_persists.append(spilled)

        thread.start()
        # Wait until camera opens or fails (webcam can take >0.4s)
        deadline = time.monotonic() + 2.5
        while time.monotonic() < deadline:
            if session.running or session.error:
                break
            time.sleep(0.1)
        return session

    def stop(self, camera_pk: int) -> bool:
        with self._lock:
            session = self._sessions.pop(camera_pk, None)
        if session is None:
            return False
        session.stop_event.set()
        if session.thread and session.thread.is_alive():
            session.thread.join(timeout=3.0)
        session.running = False
        return True

    def stop_all(self) -> None:
        with self._lock:
            ids = list(self._sessions.keys())
        for camera_pk in ids:
            self.stop(camera_pk)

    def get_jpeg(self, camera_pk: int) -> bytes | None:
        session = self.get_session(camera_pk)
        if session is None:
            return None
        with session.lock:
            return session.latest_jpeg

    def _ensure_model(self) -> str:
        with self._model_lock:
            from ultralytics import YOLO

            from ufm_classes import default_custom_weights

            weights, mode = resolve_weights(None)
            weights_s = str(weights)
            if self._model is None or self._model_path != weights_s:
                self._model = YOLO(weights_s)
                self._model_path = weights_s
                self._model_mode = mode
                # Warm-up so the first live frame is not unusually slow
                try:
                    import numpy as _np

                    dummy = _np.zeros((LIVE_IMGSZ, LIVE_IMGSZ, 3), dtype=_np.uint8)
                    self._model.predict(
                        dummy,
                        imgsz=LIVE_IMGSZ,
                        conf=0.5,
                        verbose=False,
                        half=self._use_half(),
                    )
                except Exception:  # noqa: BLE001
                    pass
                print(
                    f"[live] YOLO loaded mode={mode} weights={weights_s} "
                    f"imgsz={LIVE_IMGSZ} detect_every={LIVE_DETECT_EVERY}"
                )

            # Optional secondary custom model — OFF by default because the current
            # ufm_custom checkpoint often emits empty / wrong labels and overwrites
            # good COCO phone detections. Enable with YOLO_MERGE_CUSTOM=1 after retraining.
            merge_flag = os.getenv("YOLO_MERGE_CUSTOM", "0").strip().lower()
            merge_custom = merge_flag in {"1", "true", "yes"}
            custom_path = default_custom_weights()
            if (
                merge_custom
                and mode == "coco"
                and custom_path.is_file()
                and str(custom_path.resolve()) != weights_s
            ):
                custom_s = str(custom_path.resolve())
                if self._custom_model is None or self._custom_model_path != custom_s:
                    try:
                        self._custom_model = YOLO(custom_s)
                        self._custom_model_path = custom_s
                        print(f"[live] secondary custom YOLO loaded: {custom_s}")
                    except Exception as exc:  # noqa: BLE001
                        print(f"[live] secondary custom YOLO skipped: {exc}")
                        self._custom_model = None
                        self._custom_model_path = None
            else:
                self._custom_model = None
                self._custom_model_path = None

            return self._model_mode

    def _use_half(self) -> bool:
        try:
            import torch

            return bool(torch.cuda.is_available())
        except Exception:  # noqa: BLE001
            return False

    def _run_loop(self, session: CameraSession) -> None:
        try:
            source = resolve_capture_source(session.stream_url)
            session.opened_source = str(source)
            cap = cv2.VideoCapture(source)
            if not cap.isOpened():
                kind = (session.stream_url or "").strip().lower()
                hint = ""
                if kind.startswith("webcam") or kind.isdigit():
                    hint = (
                        " No webcam detected — configure an approved sample clip "
                        "or RTSP URL in Master Data."
                    )
                session.error = f"Could not open source: {session.stream_url}.{hint}"
                session.running = False
                return

            # Prefer lower capture resolution when the device supports it
            try:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:  # noqa: BLE001
                pass

            session.running = True
            # Keep model_error; only clear camera open errors
            session.error = None
            # Retry any durable pending saves restored after crash
            if session.persist and session.pending_persists:
                self._retry_pending_persists(session)
            tracker: SessionTracker = session.tracker or SessionTracker()
            session.tracker = tracker
            is_file = isinstance(source, str) and Path(source).is_file()
            last_labels: list[dict[str, Any]] = []
            loop_i = 0
            model_mode = self._model_mode or session.weights_mode or "coco"
            last_retry_at = 0.0

            while not session.stop_event.is_set():
                ok, frame = cap.read()
                if not ok:
                    if is_file:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    time.sleep(0.02)
                    continue

                now_mono = time.monotonic()
                if session.persist and now_mono - last_retry_at >= 2.0:
                    last_retry_at = now_mono
                    self._retry_pending_persists(session)

                labels: list[dict[str, Any]] = []
                draw = frame
                run_detect = session.detect and (loop_i % LIVE_DETECT_EVERY == 0)

                if session.detect:
                    if run_detect:
                        draw, labels = self._detect_frame(frame, session.conf, model_mode)
                        last_labels = labels
                        now = time.monotonic()
                        tracker.prune(now)
                        engine: SuspicionEngine = session.suspicion or SuspicionEngine()
                        session.suspicion = engine
                        for item in labels:
                            decision_s = item.get("decision")
                            category = item.get("category")
                            if not category or decision_s == Decision.IGNORE.value:
                                continue
                            try:
                                decision = Decision(decision_s)
                            except ValueError:
                                continue
                            xyxy = item.get("xyxy") or [0, 0, 0, 0]
                            bin_id = spatial_bin(
                                (
                                    float(xyxy[0]),
                                    float(xyxy[1]),
                                    float(xyxy[2]),
                                    float(xyxy[3]),
                                )
                            )
                            emit = tracker.observe(
                                category=category,
                                decision=decision,
                                confidence=float(item["confidence"]),
                                bin_id=bin_id,
                                now=now,
                            )
                            if emit is None:
                                continue
                            engine.apply_object_event(
                                track_id=f"obj-{bin_id}",
                                decision=emit.value,
                                category=category,
                                now=now,
                            )
                            event = LiveDetectionEvent(
                                label=category,
                                confidence=float(item["confidence"]),
                                frame_index=session.frame_index,
                                timestamp=datetime.now(timezone.utc)
                                .replace(tzinfo=None)
                                .isoformat(timespec="seconds"),
                                decision=emit.value,
                                raw_label=item.get("raw_label"),
                                save_status="pending" if session.persist else "none",
                            )
                            with session.lock:
                                session.recent_events.append(event)
                                if len(session.recent_events) > 50:
                                    session.recent_events = session.recent_events[-50:]
                            if session.persist:
                                self._enqueue_persist(
                                    session,
                                    event=event,
                                    annotated_frame=draw,
                                    confirmed=emit == Decision.CONFIRM,
                                )
                                try:
                                    from ws_hub import broadcast_alert

                                    broadcast_alert(
                                        {
                                            "type": (
                                                "DETECTION_ALERT_DEMO"
                                                if session.is_demo
                                                else "DETECTION_ALERT"
                                            ),
                                            "camera_id": session.camera_pk,
                                            "label": category,
                                            "decision": emit.value,
                                            "confidence": float(item["confidence"]),
                                            "is_demo": bool(session.is_demo),
                                        }
                                    )
                                except Exception:  # noqa: BLE001
                                    pass
                    else:
                        # Reuse last boxes — cheap redraw between inference frames
                        draw, labels = self._draw_labels(frame, last_labels)

                    # Posture / head orientation (every N loops) — does not invent identity
                    if LIVE_POSTURE and (loop_i % POSTURE_EVERY == 0):
                        try:
                            heads = analyze_heads(frame)
                            engine = session.suspicion or SuspicionEngine()
                            session.suspicion = engine
                            posture_payload = []
                            score_payload = []
                            for obs in heads:
                                snap = engine.update_head(
                                    track_id=obs.track_id,
                                    yaw_deg=obs.yaw_deg,
                                    pitch_deg=obs.pitch_deg,
                                    quality=obs.quality,
                                )
                                posture_payload.append(observation_to_dict(obs))
                                score_payload.append(snap)
                                if snap.get("should_alert"):
                                    event = LiveDetectionEvent(
                                        label="head_orientation",
                                        confidence=min(0.99, snap["score"] / 100.0),
                                        frame_index=session.frame_index,
                                        timestamp=datetime.now(timezone.utc)
                                        .replace(tzinfo=None)
                                        .isoformat(timespec="seconds"),
                                        decision="REVIEW",
                                        raw_label=f"score={snap['score']}",
                                    )
                                    with session.lock:
                                        session.recent_events.append(event)
                                    try:
                                        from ws_hub import broadcast_alert

                                        broadcast_alert(
                                            {
                                                "type": "SUSPICION_ALERT",
                                                "camera_id": session.camera_pk,
                                                "track_id": snap["track_id"],
                                                "score": snap["score"],
                                                "level": snap["level"],
                                                "config_version": snap.get(
                                                    "config_version"
                                                ),
                                            }
                                        )
                                    except Exception:  # noqa: BLE001
                                        pass
                            draw = draw_head_overlays(draw, heads)
                            with session.lock:
                                session.latest_posture = posture_payload
                                session.latest_scores = score_payload
                        except Exception:  # noqa: BLE001
                            pass

                ok_jpg, buf = cv2.imencode(
                    ".jpg",
                    draw,
                    [int(cv2.IMWRITE_JPEG_QUALITY), LIVE_JPEG_QUALITY],
                )
                if ok_jpg:
                    with session.lock:
                        session.latest_jpeg = buf.tobytes()
                        session.latest_labels = labels
                        session.frame_index += 1
                        if session.detect and run_detect:
                            session.frame_buffer.append(draw.copy())
                            if len(session.frame_buffer) > session.frame_buffer_max:
                                session.frame_buffer = session.frame_buffer[
                                    -session.frame_buffer_max :
                                ]

                loop_i += 1
                time.sleep(0.02)

            cap.release()
        except Exception as exc:  # noqa: BLE001 — surface to UI
            session.error = str(exc)
        finally:
            session.running = False

    def _draw_labels(
        self, frame: np.ndarray, labels: list[dict[str, Any]]
    ) -> tuple[np.ndarray, list[dict[str, Any]]]:
        if not labels:
            return frame, labels
        draw = frame.copy()
        for item in labels:
            xyxy = item.get("xyxy") or [0, 0, 0, 0]
            x1, y1, x2, y2 = [int(v) for v in xyxy]
            decision = item.get("decision")
            if decision == Decision.CONFIRM.value:
                color = (40, 180, 80)
            elif decision == Decision.REVIEW.value:
                color = (0, 165, 255)
            else:
                color = (160, 160, 160)
            cv2.rectangle(draw, (x1, y1), (x2, y2), color, 2)
            score = float(item.get("confidence") or 0)
            caption = f"{item.get('raw_label', item.get('label'))} {score:.2f}"
            if item.get("category"):
                caption = f"{item['category']} {score:.2f}"
                if item.get("raw_label") and item["raw_label"] != item["category"]:
                    caption = f"{item['category']} ({item['raw_label']}) {score:.2f}"
            if decision == Decision.REVIEW.value:
                caption = f"REVIEW {caption}"
            elif decision == Decision.CONFIRM.value:
                caption = f"UFM {caption}"
            cv2.putText(
                draw,
                caption,
                (x1, max(18, y1 - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1,
                cv2.LINE_AA,
            )
        return draw, labels

    def _detect_frame(
        self, frame: np.ndarray, conf: float, model_mode: str
    ) -> tuple[np.ndarray, list[dict[str, Any]]]:
        self._ensure_model()
        assert self._model is not None

        conf_gate = max(0.18, min(float(conf), 0.30))
        predict_kwargs: dict[str, Any] = {
            "imgsz": LIVE_IMGSZ,
            "conf": conf_gate,
            "verbose": False,
            "half": self._use_half(),
        }
        # Class filter only for pretrained COCO (custom models have different ids)
        if model_mode == "coco":
            predict_kwargs["classes"] = COCO_UFM_CLASS_IDS

        result = self._model.predict(frame, **predict_kwargs)[0]
        frame_wh = (int(frame.shape[1]), int(frame.shape[0]))
        labels = self._boxes_to_labels(
            result, model_mode=model_mode, frame_wh=frame_wh
        )

        # Merge custom UFM classes (smart_watch, notes_paper, …) when available
        if self._custom_model is not None and model_mode == "coco":
            try:
                custom_result = self._custom_model.predict(
                    frame,
                    imgsz=LIVE_IMGSZ,
                    conf=conf_gate,
                    verbose=False,
                    half=self._use_half(),
                )[0]
                custom_labels = self._boxes_to_labels(
                    custom_result, model_mode="custom", frame_wh=frame_wh
                )
                labels = self._merge_labels(labels, custom_labels)
            except Exception:  # noqa: BLE001
                pass

        draw = frame.copy()
        return self._draw_labels(draw, labels)[0], labels

    def _boxes_to_labels(
        self,
        result: Any,
        *,
        model_mode: str,
        frame_wh: tuple[int, int],
    ) -> list[dict[str, Any]]:
        labels: list[dict[str, Any]] = []
        if result.boxes is None:
            return labels
        names = result.names
        for box in result.boxes:
            cls_id = int(box.cls[0].item())
            score = float(box.conf[0].item())
            raw = str(names.get(cls_id, str(cls_id)))
            x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]
            item = annotate_detection_dict(
                raw_label=raw,
                confidence=score,
                model_mode=model_mode,
                xyxy=(x1, y1, x2, y2),
                frame_wh=frame_wh,
            )
            # Always keep mapped UFM categories for on-screen labels
            if item["decision"] == Decision.IGNORE.value and not item.get("category"):
                if score < 0.40:
                    continue
            labels.append(item)
        return labels

    def _merge_labels(
        self, primary: list[dict[str, Any]], secondary: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Merge custom detections carefully.
        Never overwrite COCO mobile_phone / electronic_gadget with custom guesses.
        Prefer custom only for smart_watch (COCO has no watch class).
        """
        protected = {"mobile_phone", "electronic_gadget"}
        allowed_custom = {"smart_watch", "suspicious_object"}
        merged = list(primary)
        primary_cats = {
            (e.get("category") or e.get("raw_label")) for e in primary if e.get("category")
        }
        for item in secondary:
            cat = item.get("category")
            if cat not in allowed_custom:
                continue
            if cat in protected:
                continue
            if float(item.get("confidence") or 0) < 0.40:
                continue
            # Don't add smart_watch if we already have a strong phone in same region
            overlap = False
            for existing in merged:
                ex_cat = existing.get("category") or existing.get("raw_label")
                if self._iou(existing.get("xyxy"), item.get("xyxy")) > 0.35:
                    if ex_cat in protected:
                        overlap = True
                        break
                    if ex_cat == cat:
                        if float(item.get("confidence") or 0) > float(
                            existing.get("confidence") or 0
                        ):
                            existing.update(item)
                        overlap = True
                        break
            if not overlap and cat not in primary_cats:
                merged.append(item)
        return merged

    @staticmethod
    def _iou(a: Any, b: Any) -> float:
        if not a or not b or len(a) < 4 or len(b) < 4:
            return 0.0
        ax1, ay1, ax2, ay2 = [float(v) for v in a[:4]]
        bx1, by1, bx2, by2 = [float(v) for v in b[:4]]
        ix1, iy1 = max(ax1, bx1), max(ay1, by1)
        ix2, iy2 = min(ax2, bx2), min(ay2, by2)
        iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
        inter = iw * ih
        if inter <= 0:
            return 0.0
        area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
        area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
        denom = area_a + area_b - inter
        return inter / denom if denom > 0 else 0.0

    def _frame_to_jpeg(self, frame: np.ndarray | None) -> bytes | None:
        if frame is None:
            return None
        try:
            ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
            if not ok:
                return None
            return buf.tobytes()
        except Exception:  # noqa: BLE001
            return None

    def _jpeg_to_frame(self, data: bytes | None) -> np.ndarray | None:
        if not data:
            return None
        try:
            arr = np.frombuffer(data, dtype=np.uint8)
            return cv2.imdecode(arr, cv2.IMREAD_COLOR)
        except Exception:  # noqa: BLE001
            return None

    def _event_key(self, event: LiveDetectionEvent) -> str:
        return f"{event.timestamp}|{event.frame_index}|{event.label}|{event.decision}"

    def _mark_event_save(
        self,
        session: CameraSession,
        event_key: str,
        *,
        status: str,
        persisted_id: int | None = None,
        already_locked: bool = False,
    ) -> None:
        def _apply() -> None:
            for ev in session.recent_events:
                if self._event_key(ev) == event_key:
                    ev.save_status = status
                    if persisted_id is not None:
                        ev.persisted_id = persisted_id
                    break

        if already_locked:
            _apply()
        else:
            with session.lock:
                _apply()

    def _enqueue_persist(
        self,
        session: CameraSession,
        *,
        event: LiveDetectionEvent,
        annotated_frame: np.ndarray | None,
        confirmed: bool,
    ) -> None:
        key = self._event_key(event)
        pending = PendingPersist(
            label=event.label,
            confidence=float(event.confidence),
            confirmed=confirmed,
            raw_label=event.raw_label,
            event_key=key,
            frame_jpeg=self._frame_to_jpeg(
                annotated_frame.copy() if annotated_frame is not None else None
            ),
            is_demo=bool(session.is_demo),
        )
        with session.lock:
            # Drop oldest if bounded queue is full
            while len(session.pending_persists) >= PENDING_PERSIST_MAX:
                dropped = session.pending_persists.pop(0)
                self._mark_event_save(
                    session, dropped.event_key, status="failed", already_locked=True
                )
                _delete_pending_spill(session.camera_pk, dropped.event_key)
            session.pending_persists.append(pending)
            session.last_persist_ok = None
        _spill_pending(session.camera_pk, pending)

        threading.Thread(
            target=self._persist_pending_item,
            args=(session, pending),
            daemon=True,
            name=f"persist-{session.camera_pk}",
        ).start()

    def _retry_pending_persists(self, session: CameraSession) -> None:
        with session.lock:
            retryable = [
                p
                for p in session.pending_persists
                if p.attempts < PENDING_PERSIST_MAX_ATTEMPTS
                and (p.last_error is not None or p.attempts == 0)
            ]
        for pending in retryable[:3]:
            threading.Thread(
                target=self._persist_pending_item,
                args=(session, pending),
                daemon=True,
                name=f"persist-retry-{session.camera_pk}",
            ).start()

    def _persist_pending_item(
        self, session: CameraSession, pending: PendingPersist
    ) -> None:
        if pending.attempts >= PENDING_PERSIST_MAX_ATTEMPTS:
            self._mark_event_save(session, pending.event_key, status="failed")
            return
        pending.attempts += 1
        frame = self._jpeg_to_frame(pending.frame_jpeg)
        det_id = self._persist_detection(
            session,
            pending.label,
            pending.confidence,
            frame,
            confirmed=pending.confirmed,
            raw_label=pending.raw_label,
        )
        if det_id is not None:
            with session.lock:
                session.pending_persists = [
                    p for p in session.pending_persists if p.event_key != pending.event_key
                ]
                session.last_persist_ok = True
                session.persist_error = None
            _delete_pending_spill(session.camera_pk, pending.event_key)
            self._mark_event_save(
                session, pending.event_key, status="saved", persisted_id=det_id
            )
            return

        pending.last_error = session.persist_error or "persist failed"
        _spill_pending(session.camera_pk, pending)
        if pending.attempts >= PENDING_PERSIST_MAX_ATTEMPTS:
            with session.lock:
                session.pending_persists = [
                    p for p in session.pending_persists if p.event_key != pending.event_key
                ]
            _delete_pending_spill(session.camera_pk, pending.event_key)
            self._mark_event_save(session, pending.event_key, status="failed")
        else:
            self._mark_event_save(session, pending.event_key, status="pending")

    def _persist_detection(
        self,
        session: CameraSession,
        label: str,
        confidence: float,
        annotated_frame: np.ndarray | None = None,
        *,
        confirmed: bool = True,
        raw_label: str | None = None,
    ) -> int | None:
        try:
            from database import SessionLocal
            from detection_bridge import notify_detection_alert
            from evidence_auto import create_detection_evidence
            from models.detection import Detection

            with session.lock:
                clip_frames = [f.copy() for f in session.frame_buffer[-16:]]
            if annotated_frame is not None:
                clip_frames.append(annotated_frame.copy())

            db = SessionLocal()
            try:
                det_type = label
                row = Detection(
                    camera_id=session.camera_pk,
                    student_id=None,
                    detection_type=det_type,
                    confidence=confidence,
                    timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
                    is_confirmed=confirmed,
                    is_demo=bool(session.is_demo),
                    source_path=(
                        f"live:{session.camera_code}"
                        + (f"|raw={raw_label}" if raw_label else "")
                        + ("" if confirmed else "|review")
                        + ("|demo" if session.is_demo else "")
                    ),
                    frame_index=session.frame_index,
                )
                db.add(row)
                db.flush()
                # Only alert HODs for confirmed prohibited detections
                if confirmed:
                    notify_detection_alert(db, row, is_demo=bool(session.is_demo))
                if annotated_frame is not None:
                    created = create_detection_evidence(
                        db,
                        detection_id=int(row.id),
                        camera_id=session.camera_pk,
                        confidence=confidence,
                        frame_bgr=annotated_frame,
                        clip_frames=clip_frames if confirmed else None,
                        case_id=None,
                    )
                    for ev in created or []:
                        try:
                            ev.is_demo = bool(session.is_demo)
                        except Exception:  # noqa: BLE001
                            pass
                db.commit()
                with session.lock:
                    session.last_persist_ok = True
                    session.persist_error = None
                return int(row.id)
            finally:
                db.close()
        except Exception as exc:  # noqa: BLE001
            with session.lock:
                session.last_persist_ok = False
                session.persist_error = str(exc)[:240]
            return None


live_manager = LiveStreamManager()
