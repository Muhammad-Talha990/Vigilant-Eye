"""
Head / posture analysis for VigilantEye exam monitoring.

Scope (Tools): MediaPipe for candidate behavior and pose analysis.
Python 3.13 may lack a MediaPipe wheel — this module uses MediaPipe when
available and falls back to OpenCV face detection + geometric head-pose
proxies. Fallbacks are labeled estimator='opencv_fallback' and must not be
described as precise gaze tracking.

Head orientation is distinct from true eye-gaze estimation.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

# Optional MediaPipe
_MP = None
_MP_FACE = None
_MP_LOAD_ERROR: str | None = None

try:
    import mediapipe as mp  # type: ignore

    _MP = mp
except Exception as exc:  # noqa: BLE001
    _MP_LOAD_ERROR = f"{type(exc).__name__}: {exc}"


POSTURE_EVERY = max(1, int(os.getenv("UFM_POSTURE_EVERY", "3")))
YAW_ALERT_DEG = float(os.getenv("UFM_YAW_ALERT_DEG", "28"))
PITCH_ALERT_DEG = float(os.getenv("UFM_PITCH_ALERT_DEG", "22"))
MIN_FACE_PX = int(os.getenv("UFM_MIN_FACE_PX", "40"))


@dataclass
class HeadObservation:
    track_id: str
    yaw_deg: float | None
    pitch_deg: float | None
    roll_deg: float | None
    face_box: tuple[int, int, int, int] | None
    quality: str  # good | low | unavailable
    estimator: str  # mediapipe | opencv_fallback
    flags: list[str]


def mediapipe_available() -> bool:
    return _MP is not None


def mediapipe_status() -> dict[str, Any]:
    return {
        "available": mediapipe_available(),
        "error": _MP_LOAD_ERROR,
        "fallback": "opencv_haar_geometry" if not mediapipe_available() else None,
    }


def _ensure_mp_face():
    global _MP_FACE
    if _MP is None:
        return None
    if _MP_FACE is None:
        _MP_FACE = _MP.solutions.face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=int(os.getenv("UFM_MAX_FACES", "12")),
            refine_landmarks=False,
            min_detection_confidence=0.4,
            min_tracking_confidence=0.4,
        )
    return _MP_FACE


def _solve_pnP_angles(
    image_points: np.ndarray, frame_shape: tuple[int, ...]
) -> tuple[float | None, float | None, float | None]:
    """Approximate yaw/pitch/roll (degrees) from 6 facial landmarks via solvePnP."""
    h, w = frame_shape[:2]
    # Generic 3D model points (nose tip, chin, eye corners, mouth corners)
    model_points = np.array(
        [
            (0.0, 0.0, 0.0),
            (0.0, -63.6, -12.5),
            (-43.3, 32.7, -26.0),
            (43.3, 32.7, -26.0),
            (-28.9, -28.9, -24.1),
            (28.9, -28.9, -24.1),
        ],
        dtype=np.float64,
    )
    focal = w
    center = (w / 2.0, h / 2.0)
    camera_matrix = np.array(
        [[focal, 0, center[0]], [0, focal, center[1]], [0, 0, 1]],
        dtype=np.float64,
    )
    dist = np.zeros((4, 1))
    ok, rvec, _ = cv2.solvePnP(
        model_points, image_points, camera_matrix, dist, flags=cv2.SOLVEPNP_ITERATIVE
    )
    if not ok:
        return None, None, None
    rmat, _ = cv2.Rodrigues(rvec)
    # Decompose to yaw/pitch/roll (approx)
    sy = math.sqrt(rmat[0, 0] ** 2 + rmat[1, 0] ** 2)
    singular = sy < 1e-6
    if not singular:
        pitch = math.degrees(math.atan2(-rmat[2, 0], sy))
        yaw = math.degrees(math.atan2(rmat[1, 0], rmat[0, 0]))
        roll = math.degrees(math.atan2(rmat[2, 1], rmat[2, 2]))
    else:
        pitch = math.degrees(math.atan2(-rmat[2, 0], sy))
        yaw = math.degrees(math.atan2(-rmat[0, 1], rmat[1, 1]))
        roll = 0.0
    return yaw, pitch, roll


def _analyze_mediapipe(frame_bgr: np.ndarray) -> list[HeadObservation]:
    mesh = _ensure_mp_face()
    if mesh is None:
        return []
    h, w = frame_bgr.shape[:2]
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    res = mesh.process(rgb)
    out: list[HeadObservation] = []
    if not res.multi_face_landmarks:
        return out
    # Landmark indices for Face Mesh (approx MediaPipe FaceMesh)
    # nose tip 1, chin 152, left eye 33, right eye 263, mouth L 61, mouth R 291
    idxs = [1, 152, 33, 263, 61, 291]
    for i, face in enumerate(res.multi_face_landmarks):
        pts = []
        xs, ys = [], []
        for idx in idxs:
            lm = face.landmark[idx]
            x, y = lm.x * w, lm.y * h
            pts.append([x, y])
            xs.append(x)
            ys.append(y)
        image_points = np.array(pts, dtype=np.float64)
        yaw, pitch, roll = _solve_pnP_angles(image_points, frame_bgr.shape)
        x1, y1, x2, y2 = int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))
        face_w = max(1, x2 - x1)
        quality = "good" if face_w >= MIN_FACE_PX else "low"
        flags: list[str] = []
        if yaw is not None and abs(yaw) >= YAW_ALERT_DEG:
            flags.append("sustained_yaw_candidate")
        if pitch is not None and pitch <= -PITCH_ALERT_DEG:
            flags.append("downward_pitch")  # often normal writing — score engine discounts
        if pitch is not None and pitch >= PITCH_ALERT_DEG:
            flags.append("upward_pitch")
        out.append(
            HeadObservation(
                track_id=f"face-{i}-{int((x1 + x2) / 2) // 80}_{int((y1 + y2) / 2) // 80}",
                yaw_deg=yaw,
                pitch_deg=pitch,
                roll_deg=roll,
                face_box=(x1, y1, x2, y2),
                quality=quality,
                estimator="mediapipe",
                flags=flags,
            )
        )
    return out


_haar = None


def _haar_cascade():
    global _haar
    if _haar is None:
        path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        _haar = cv2.CascadeClassifier(path)
    return _haar


def _analyze_opencv(frame_bgr: np.ndarray) -> list[HeadObservation]:
    """
    Fallback: face boxes only. Yaw/pitch from face center vs frame center —
    coarse hall-level cue, NOT calibrated gaze. Marked low quality.
    """
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    faces = _haar_cascade().detectMultiScale(gray, 1.15, 4, minSize=(MIN_FACE_PX, MIN_FACE_PX))
    h, w = frame_bgr.shape[:2]
    out: list[HeadObservation] = []
    for i, (x, y, fw, fh) in enumerate(faces):
        cx, cy = x + fw / 2.0, y + fh / 2.0
        # Normalize offset to approx degrees-ish (provisional, not metric)
        yaw = ((cx / w) - 0.5) * 70.0
        pitch = ((cy / h) - 0.45) * 50.0
        flags: list[str] = []
        if abs(yaw) >= YAW_ALERT_DEG:
            flags.append("lateral_offset")
        out.append(
            HeadObservation(
                track_id=f"face-{i}-{int(cx) // 80}_{int(cy) // 80}",
                yaw_deg=float(yaw),
                pitch_deg=float(pitch),
                roll_deg=None,
                face_box=(int(x), int(y), int(x + fw), int(y + fh)),
                quality="low",
                estimator="opencv_fallback",
                flags=flags,
            )
        )
    return out


def analyze_heads(frame_bgr: np.ndarray) -> list[HeadObservation]:
    """Detect faces / head orientation for all visible candidates in frame."""
    if frame_bgr is None or getattr(frame_bgr, "size", 0) == 0:
        return []
    if mediapipe_available():
        try:
            return _analyze_mediapipe(frame_bgr)
        except Exception:  # noqa: BLE001
            return _analyze_opencv(frame_bgr)
    return _analyze_opencv(frame_bgr)


def draw_head_overlays(
    frame_bgr: np.ndarray, observations: list[HeadObservation]
) -> np.ndarray:
    draw = frame_bgr
    for obs in observations:
        if not obs.face_box:
            continue
        x1, y1, x2, y2 = obs.face_box
        color = (200, 180, 40) if obs.quality == "good" else (140, 140, 140)
        if obs.flags and (
            "sustained_yaw_candidate" in obs.flags or "lateral_offset" in obs.flags
        ):
            color = (0, 140, 255)
        cv2.rectangle(draw, (x1, y1), (x2, y2), color, 1)
        yaw = f"{obs.yaw_deg:.0f}" if obs.yaw_deg is not None else "?"
        pitch = f"{obs.pitch_deg:.0f}" if obs.pitch_deg is not None else "?"
        label = f"y{yaw}/p{pitch} {obs.estimator[:2]}"
        cv2.putText(
            draw,
            label,
            (x1, max(14, y1 - 4)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            color,
            1,
            cv2.LINE_AA,
        )
    return draw


def observation_to_dict(obs: HeadObservation) -> dict[str, Any]:
    return {
        "track_id": obs.track_id,
        "yaw_deg": None if obs.yaw_deg is None else round(obs.yaw_deg, 1),
        "pitch_deg": None if obs.pitch_deg is None else round(obs.pitch_deg, 1),
        "roll_deg": None if obs.roll_deg is None else round(obs.roll_deg, 1),
        "face_box": list(obs.face_box) if obs.face_box else None,
        "quality": obs.quality,
        "estimator": obs.estimator,
        "flags": list(obs.flags),
    }
