from datetime import datetime

from pydantic import BaseModel, Field


class UfmCaseCreate(BaseModel):
    """JSON body the client sends when creating a UFM case."""

    student_id: int = Field(gt=0)
    exam_id: int = Field(gt=0)
    violation_type: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1)
    remarks: str | None = None
    detection_id: int | None = None
    signer_name: str = Field(min_length=2, max_length=150)
    signature_ack: bool = True


class UfmCaseOut(BaseModel):
    """JSON the API returns for a UFM case (enriched)."""

    id: int
    case_number: str
    student_id: int
    exam_id: int
    reported_by: int
    violation_type: str
    description: str
    remarks: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    signer_name: str | None = None
    signed_at: datetime | None = None
    signature_ack: bool = False
    student_roll: str | None = None
    student_name: str | None = None
    student_department: str | None = None
    student_program: str | None = None
    exam_course_code: str | None = None
    exam_course_name: str | None = None
    exam_semester: str | None = None
    exam_date: str | None = None
    room_number: str | None = None
    room_building: str | None = None
    reporter_name: str | None = None
    reporter_role: str | None = None

    model_config = {"from_attributes": True}
