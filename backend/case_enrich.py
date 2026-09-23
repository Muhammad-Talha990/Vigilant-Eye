"""Serialize enriched UFM case payloads for the portal."""

from __future__ import annotations

from sqlalchemy.orm import Session

from models.exam import Exam
from models.exam_room import ExamRoom
from models.student import Student
from models.ufm_case import UfmCase
from models.user import User


def enrich_case(db: Session, case: UfmCase) -> dict:
    student = db.get(Student, case.student_id)
    exam = db.get(Exam, case.exam_id)
    room = db.get(ExamRoom, exam.room_id) if exam else None
    reporter = db.get(User, case.reported_by)

    return {
        "id": case.id,
        "case_number": case.case_number,
        "student_id": case.student_id,
        "exam_id": case.exam_id,
        "reported_by": case.reported_by,
        "violation_type": case.violation_type,
        "description": case.description,
        "remarks": case.remarks,
        "status": case.status,
        "created_at": case.created_at,
        "updated_at": case.updated_at,
        "signer_name": getattr(case, "signer_name", None),
        "signed_at": getattr(case, "signed_at", None),
        "signature_ack": bool(getattr(case, "signature_ack", False)),
        "student_roll": student.student_id if student else None,
        "student_name": student.name if student else None,
        "student_department": student.department if student else None,
        "student_program": student.program if student else None,
        "exam_course_code": exam.course_code if exam else None,
        "exam_course_name": exam.course_name if exam else None,
        "exam_semester": exam.semester if exam else None,
        "exam_date": exam.exam_date.isoformat() if exam and exam.exam_date else None,
        "room_number": room.room_number if room else None,
        "room_building": room.building if room else None,
        "reporter_name": reporter.name if reporter else None,
        "reporter_role": reporter.role if reporter else None,
    }
