"""Validate and resolve UFM case camera_id (cameras.id PK) for an exam room."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.camera import Camera
from models.detection import Detection
from models.exam import Exam


def validate_camera_for_exam(
    db: Session,
    *,
    exam_id: int,
    camera_pk: int | None,
    require_active: bool = True,
) -> int | None:
    """
    Ensure camera_pk (cameras.id) exists and belongs to the exam's room.

    When require_active is True (manual selection), inactive cameras are rejected.
    Detection-originated links may pass require_active=False so historical
    detections remain attachable without fabricating a different camera.

    Returns the validated cameras.id, or None when camera_pk is None.
    """
    if camera_pk is None:
        return None

    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exam not found for exam_id",
        )

    camera = db.get(Camera, camera_pk)
    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Camera not found for camera_id",
        )
    if require_active and not bool(camera.is_active):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Camera is inactive",
        )
    if camera.room_id != exam.room_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Camera does not belong to this examination room",
        )
    return camera.id


def resolve_camera_for_case_create(
    db: Session,
    *,
    exam_id: int,
    camera_id: int | None,
    detection: Detection | None,
) -> int | None:
    """
    Prefer authoritative detection.camera_id when a detection is linked;
    otherwise validate an explicitly supplied camera_id for the exam room.
    """
    if detection is not None and detection.camera_id is not None:
        # Detection camera is authoritative; must still match the chosen exam room.
        return validate_camera_for_exam(
            db,
            exam_id=exam_id,
            camera_pk=detection.camera_id,
            require_active=False,
        )
    return validate_camera_for_exam(
        db, exam_id=exam_id, camera_pk=camera_id, require_active=True
    )
