"""Phase C1 live monitoring API routes."""

from __future__ import annotations

import asyncio
from pathlib import Path

import cv2
import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from case_access import MONITOR_ROLES
from database import get_db
from deps import bearer_scheme, get_current_user, require_roles
from live_stream import _redact_source, live_manager, resolve_capture_source
from models.audit_log import AuditLog
from models.camera import Camera
from models.exam_room import ExamRoom
from models.user import User
from security import decode_access_token

router = APIRouter(prefix="/live", tags=["live"])

# Keep local aliases aligned with case_access.MONITOR_ROLES (Phase 11).
_MONITOR_ROLES = tuple(MONITOR_ROLES)
_DEMO_ROLES = _MONITOR_ROLES
_CAMERA_ADMIN_ROLES = ("HOD", "EXAM_DEPARTMENT")


class LiveStartRequest(BaseModel):
    """
    mode=production (default): detect+persist forced on; no source override.
    mode=demo: developer toggles allowed; records marked is_demo.
    """

    mode: str = Field(default="production", pattern="^(production|demo)$")
    detect: bool = True
    persist: bool = True
    conf: float = Field(default=0.28, ge=0.05, le=0.95)
    min_frames: int = Field(default=3, ge=1, le=30)
    source_override: str | None = Field(default=None, max_length=512)


class CameraSourceTestRequest(BaseModel):
    stream_url: str = Field(min_length=1, max_length=255)


def _user_from_token(token: str, db: Session) -> User:
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


def get_stream_user(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    token: str | None = Query(default=None, description="JWT for <img> MJPEG"),
) -> User:
    """Allow Bearer header OR ?token= for browser <img> MJPEG (monitor roles only)."""
    raw = None
    if credentials is not None and credentials.credentials:
        raw = credentials.credentials
    elif token:
        raw = token
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = _user_from_token(raw, db)
    if user.role not in MONITOR_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Role '{user.role}' is not allowed. "
                f"Required: {', '.join(sorted(MONITOR_ROLES))}"
            ),
        )
    return user


def _get_camera(db: Session, camera_id: int) -> Camera:
    cam = db.get(Camera, camera_id)
    if cam is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    return cam


def _room_label(db: Session, room_id: int) -> str:
    room = db.get(ExamRoom, room_id)
    if room is None:
        return f"Room #{room_id}"
    return f"{room.room_number} — {room.building}"


def _audit(
    db: Session,
    *,
    user_id: int,
    action: str,
    entity_id: int,
    description: str,
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity_type="camera",
            entity_id=entity_id,
            description=description,
        )
    )
    db.commit()


def _validate_source_url(stream_url: str, *, allow_sample_file: bool = True) -> str:
    raw = (stream_url or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="stream_url is required")
    lower = raw.lower()
    if lower in ("webcam", "cam", "local") or lower.startswith("webcam:"):
        return raw
    if raw.isdigit():
        return raw
    if lower.startswith("rtsp://") or lower.startswith("http://") or lower.startswith(
        "https://"
    ):
        return raw
    # Approved relative sample / project media only (no arbitrary absolute paths)
    if allow_sample_file:
        if ".." in raw.replace("\\", "/"):
            raise HTTPException(
                status_code=400, detail="Invalid path (path traversal blocked)"
            )
        root = Path(__file__).resolve().parents[2]
        candidates = [
            Path(raw),
            root / raw,
            root / "ai" / "samples" / Path(raw).name,
        ]
        for c in candidates:
            try:
                resolved = c.resolve()
            except OSError:
                continue
            if resolved.is_file() and (
                str(resolved).startswith(str(root))
                or str(resolved).startswith(str(root / "ai" / "samples"))
            ):
                # Store portable relative when under project
                try:
                    return resolved.relative_to(root).as_posix()
                except ValueError:
                    return raw
        raise HTTPException(
            status_code=400,
            detail="File source not found under project samples / allowed paths",
        )
    raise HTTPException(
        status_code=400,
        detail="Unsupported stream_url. Use webcam:N, rtsp://..., or approved sample file.",
    )


@router.get("/status")
def live_status(
    current_user: User = Depends(require_roles(*_MONITOR_ROLES)),
):
    _ = current_user
    return live_manager.status()


@router.post("/cameras/{camera_id}/start")
def start_live(
    camera_id: int,
    body: LiveStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_MONITOR_ROLES)),
):
    cam = _get_camera(db, camera_id)
    mode = (body.mode or "production").lower()
    is_demo = mode == "demo"

    if is_demo and current_user.role not in _DEMO_ROLES:
        raise HTTPException(status_code=403, detail="Demo mode not allowed for role")

    if is_demo:
        detect = bool(body.detect)
        persist = bool(body.persist)
        override = body.source_override
        if override:
            override = _validate_source_url(override, allow_sample_file=True)
    else:
        # Production: always run AI + persist validated incidents
        detect = True
        persist = True
        override = None

    room = _room_label(db, cam.room_id)
    session = live_manager.start(
        camera_pk=cam.id,
        camera_code=cam.camera_id,
        name=cam.name,
        stream_url=cam.stream_url,
        detect=detect,
        persist=persist,
        conf=body.conf,
        min_frames=body.min_frames,
        source_override=override,
        is_demo=is_demo,
        room_label=room,
    )
    if session.error and not session.running:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=session.error,
        )

    _audit(
        db,
        user_id=current_user.id,
        action="MONITORING_START",
        entity_id=cam.id,
        description=(
            f"{'DEMO' if is_demo else 'PROD'} start camera {cam.camera_id} "
            f"detect={detect} persist={persist}"
        ),
    )

    return {
        "ok": True,
        "camera_id": cam.id,
        "running": session.running,
        "detect": session.detect,
        "persist": session.persist,
        "is_demo": session.is_demo,
        "mode": mode,
        "weights_mode": session.weights_mode,
        "model_version": getattr(session, "model_version", None) or None,
        "device": getattr(session, "device_label", None) or None,
        "model_ready": session.model_ready,
        "ai_status": session.ai_status,
        "opened_source_redacted": _redact_source(session.opened_source) if hasattr(session, "opened_source") else None,
        "error": session.error,
        "mjpeg_path": f"/live/cameras/{cam.id}/mjpeg",
    }


@router.post("/cameras/{camera_id}/stop")
def stop_live(
    camera_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_MONITOR_ROLES)),
):
    stopped = live_manager.stop(camera_id)
    _audit(
        db,
        user_id=current_user.id,
        action="MONITORING_STOP",
        entity_id=camera_id,
        description=f"Stop live session camera_id={camera_id}",
    )
    return {"ok": True, "stopped": stopped, "camera_id": camera_id}


@router.post("/test-source")
def test_camera_source(
    body: CameraSourceTestRequest,
    current_user: User = Depends(require_roles(*_CAMERA_ADMIN_ROLES)),
):
    """Authorized connection test before saving camera settings."""
    _ = current_user
    validated = _validate_source_url(body.stream_url, allow_sample_file=True)
    try:
        source = resolve_capture_source(validated)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise HTTPException(
            status_code=400, detail=f"Could not open source: {validated}"
        )
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        raise HTTPException(
            status_code=400, detail="Source opened but no frame could be read"
        )
    h, w = frame.shape[:2]
    return {
        "ok": True,
        "validated_url": validated,
        "frame_width": int(w),
        "frame_height": int(h),
        "message": "Connection test succeeded",
    }


@router.get("/cameras/{camera_id}/snapshot")
def snapshot(
    camera_id: int,
    user: User = Depends(get_stream_user),
):
    _ = user
    session = live_manager.get_session(camera_id)
    if session is None or not session.running:
        raise HTTPException(
            status_code=404,
            detail="No active live session for this camera. Call /start first.",
        )
    jpeg = live_manager.get_jpeg(camera_id)
    if not jpeg:
        raise HTTPException(status_code=503, detail="No frame available yet")
    return Response(content=jpeg, media_type="image/jpeg")


@router.get("/cameras/{camera_id}/mjpeg")
async def mjpeg_stream(
    camera_id: int,
    user: User = Depends(get_stream_user),
):
    _ = user
    session = live_manager.get_session(camera_id)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail="No active live session for this camera. Call /start first.",
        )

    boundary = "frame"

    async def generate():
        while True:
            sess = live_manager.get_session(camera_id)
            if sess is None or sess.stop_event.is_set():
                break
            jpeg = live_manager.get_jpeg(camera_id)
            if jpeg:
                yield (
                    b"--" + boundary.encode() + b"\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n"
                    + jpeg
                    + b"\r\n"
                )
            await asyncio.sleep(0.08)

    return StreamingResponse(
        generate(),
        media_type=f"multipart/x-mixed-replace; boundary={boundary}",
    )
