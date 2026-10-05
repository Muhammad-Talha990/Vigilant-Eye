"""
Seed demo exam room, cameras, and one exam for FYP walkthrough.

Safe to re-run. Call after seed_demo_users.py (or it will create the room/exam alone).

Usage (from backend folder, venv active):
    python seed_demo_cameras.py
"""

from __future__ import annotations

from datetime import date, time

from sqlalchemy import select

from database import SessionLocal
from models.camera import Camera
from models.exam import Exam
from models.exam_room import ExamRoom

DEMO_ROOM = "A-101"
DEMO_CAMERAS = [
    {
        "camera_id": "CAM-A101-01",
        "name": "Hall A Front",
        "stream_url": "webcam:0",
    },
    {
        "camera_id": "CAM-A101-02",
        "name": "Hall A Sample Clip",
        "stream_url": "ai/samples/sample_exam_clip.mp4",
    },
]


def seed(*, quiet: bool = False) -> None:
    def log(msg: str) -> None:
        if not quiet:
            print(msg)

    db = SessionLocal()
    try:
        room = db.scalar(select(ExamRoom).where(ExamRoom.room_number == DEMO_ROOM))
        if room is None:
            room = ExamRoom(
                room_number=DEMO_ROOM,
                building="Academic Block A",
                capacity=40,
            )
            db.add(room)
            db.flush()
            log(f"CREATE room {DEMO_ROOM} id={room.id}")
        else:
            log(f"SKIP  room {DEMO_ROOM} id={room.id}")

        for spec in DEMO_CAMERAS:
            existing = db.scalar(
                select(Camera).where(Camera.camera_id == spec["camera_id"])
            )
            if existing:
                # Keep demo-friendly stream URLs fresh
                existing.stream_url = spec["stream_url"]
                existing.room_id = room.id
                existing.is_active = True
                log(
                    f"UPDATE camera {spec['camera_id']} -> {spec['stream_url']}"
                )
                continue
            db.add(
                Camera(
                    camera_id=spec["camera_id"],
                    name=spec["name"],
                    room_id=room.id,
                    stream_url=spec["stream_url"],
                    is_active=True,
                )
            )
            log(f"CREATE camera {spec['camera_id']}")

        exam = db.scalar(select(Exam).where(Exam.course_code == "CS101"))
        if exam is None:
            db.add(
                Exam(
                    course_code="CS101",
                    course_name="Introduction to Computing",
                    semester="Spring 2026",
                    exam_date=date(2026, 6, 15),
                    start_time=time(9, 0),
                    end_time=time(12, 0),
                    room_id=room.id,
                )
            )
            log("CREATE exam CS101")
        else:
            log(f"SKIP  exam CS101 id={exam.id}")

        db.commit()
        log("")
        log("Demo monitoring ready:")
        log("  CAM-A101-01  stream_url=webcam:0")
        log("  CAM-A101-02  stream_url=ai/samples/sample_exam_clip.mp4")
        log("Login invigilator -> Live Monitoring -> Start sample clip / webcam")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
