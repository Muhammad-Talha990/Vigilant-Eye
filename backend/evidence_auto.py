"""Auto-create evidence files (snapshot / short clip) from confirmed detections."""

from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np
from PIL import Image
from sqlalchemy.orm import Session

from models.evidence import Evidence

BACKEND_ROOT = Path(__file__).resolve().parent
EVIDENCE_DIR = BACKEND_ROOT / "uploads" / "evidence"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


def _rel(path: Path) -> str:
    return path.relative_to(BACKEND_ROOT).as_posix()


def save_snapshot_jpeg(frame_bgr: np.ndarray, *, prefix: str = "snap") -> str:
    """Write JPEG under uploads/evidence; return portable relative path."""
    name = f"{prefix}_{uuid.uuid4().hex}.jpg"
    dest = EVIDENCE_DIR / name
    ok, buf = cv2.imencode(".jpg", frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        raise RuntimeError("Failed to encode JPEG snapshot")
    dest.write_bytes(buf.tobytes())
    return _rel(dest)


def frames_to_animated_webp(
    frames: Sequence[np.ndarray],
    *,
    fps: float = 8.0,
    max_frames: int = 48,
    max_width: int = 960,
) -> bytes | None:
    """Encode BGR frames as an animated WebP (plays in browsers via <img>)."""
    if not frames:
        return None
    step = max(1, len(frames) // max_frames) if len(frames) > max_frames else 1
    picked = list(frames)[::step][:max_frames]
    pil_frames: list[Image.Image] = []
    for frame in picked:
        if frame is None or getattr(frame, "size", 0) == 0:
            continue
        h, w = frame.shape[:2]
        if w > max_width:
            nh = max(1, int(h * (max_width / w)))
            frame = cv2.resize(frame, (max_width, nh))
        if frame.shape[1] % 2:
            frame = frame[:, :-1]
        if frame.shape[0] % 2:
            frame = frame[:-1, :]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_frames.append(Image.fromarray(rgb))
    if len(pil_frames) < 2:
        return None
    duration_ms = max(40, int(1000 / max(1.0, fps)))
    buf = io.BytesIO()
    pil_frames[0].save(
        buf,
        format="WEBP",
        save_all=True,
        append_images=pil_frames[1:],
        duration=duration_ms,
        loop=0,
        quality=72,
        method=0,
    )
    data = buf.getvalue()
    return data if len(data) > 100 else None


def save_clip_mp4(
    frames: Sequence[np.ndarray],
    *,
    fps: float = 8.0,
    prefix: str = "clip",
) -> str | None:
    """
    Write a short clip as animated WebP so browsers can preview / open it.

    (AVI/MJPG does not play in Chrome/Edge <video>; OpenCV H.264 needs
    openh264 DLL which is often missing.)
    """
    data = frames_to_animated_webp(frames, fps=fps)
    if not data:
        return None
    name = f"{prefix}_{uuid.uuid4().hex}.webp"
    dest = EVIDENCE_DIR / name
    dest.write_bytes(data)
    return _rel(dest)


def video_file_to_animated_webp(path: Path, *, fps: float = 8.0) -> bytes | None:
    """Decode an on-disk video (e.g. legacy AVI) into animated WebP for preview."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return None
    frames: list[np.ndarray] = []
    try:
        while len(frames) < 48:
            ok, frame = cap.read()
            if not ok:
                break
            frames.append(frame)
    finally:
        cap.release()
    return frames_to_animated_webp(frames, fps=fps)


def create_detection_evidence(
    db: Session,
    *,
    detection_id: int,
    camera_id: int | None,
    confidence: float | None,
    frame_bgr: np.ndarray | None = None,
    clip_frames: Sequence[np.ndarray] | None = None,
    case_id: int | None = None,
    uploaded_by: int | None = None,
) -> list[Evidence]:
    """
    Persist SNAPSHOT and optional CLIP evidence rows linked to a detection.
    case_id may be None until a case is drafted/created.
    """
    created: list[Evidence] = []
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    if frame_bgr is not None:
        try:
            path = save_snapshot_jpeg(frame_bgr, prefix=f"det{detection_id}")
            row = Evidence(
                case_id=case_id,
                detection_id=detection_id,
                evidence_type="SNAPSHOT",
                file_path=path,
                timestamp=now,
                camera_id=camera_id,
                confidence=confidence,
                uploaded_by=uploaded_by,
            )
            db.add(row)
            created.append(row)
        except Exception:  # noqa: BLE001
            pass

    if clip_frames and len(clip_frames) >= 2:
        try:
            clip_path = save_clip_mp4(
                clip_frames, fps=8.0, prefix=f"det{detection_id}"
            )
            if clip_path:
                row = Evidence(
                    case_id=case_id,
                    detection_id=detection_id,
                    evidence_type="CLIP",
                    file_path=clip_path,
                    timestamp=now,
                    camera_id=camera_id,
                    confidence=confidence,
                    uploaded_by=uploaded_by,
                )
                db.add(row)
                created.append(row)
        except Exception:  # noqa: BLE001
            pass

    if created:
        db.flush()
    return created


def attach_detection_evidence_to_case(
    db: Session, *, detection_id: int, case_id: int
) -> int:
    """Link orphan (or any) evidence for a detection to a UFM case. Returns count."""
    from sqlalchemy import select

    rows = db.scalars(
        select(Evidence).where(Evidence.detection_id == detection_id)
    ).all()
    count = 0
    for row in rows:
        if row.case_id is None or row.case_id != case_id:
            row.case_id = case_id
            count += 1
    if count:
        db.flush()
    return count
