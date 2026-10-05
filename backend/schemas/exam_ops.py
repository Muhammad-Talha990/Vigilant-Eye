"""Phase 23 — Exam enrollment, invigilator assignment, exam update schemas."""

from __future__ import annotations

from datetime import date, time

from pydantic import BaseModel, Field

from schemas.exam import ExamOut


class ExamUpdate(BaseModel):
    course_code: str | None = Field(default=None, min_length=1, max_length=50)
    course_name: str | None = Field(default=None, min_length=1, max_length=150)
    semester: str | None = Field(default=None, min_length=1, max_length=50)
    exam_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    room_id: int | None = Field(default=None, gt=0)


class ExamEnrollmentCreate(BaseModel):
    student_id: int = Field(gt=0)


class ExamEnrollmentOut(BaseModel):
    id: int
    exam_id: int
    student_id: int
    student_roll: str | None = None
    student_name: str | None = None

    model_config = {"from_attributes": True}


class ExamInvigilatorCreate(BaseModel):
    user_id: int = Field(gt=0)


class ExamInvigilatorOut(BaseModel):
    id: int
    exam_id: int
    user_id: int
    user_email: str | None = None
    user_name: str | None = None

    model_config = {"from_attributes": True}


class ExamDetailOut(ExamOut):
    enrollments: list[ExamEnrollmentOut] = []
    invigilators: list[ExamInvigilatorOut] = []
    room_cameras: list[dict] = []
