from pydantic import BaseModel, Field

from schemas.utc_datetime import UtcDateTime


class ResultControlCreate(BaseModel):
    student_id: int = Field(gt=0)
    case_id: int = Field(gt=0)
    reason: str = Field(min_length=1)
    result_status: str = "HELD"
    transcript_status: str = "BLOCKED"


class ResultControlOut(BaseModel):
    id: int
    student_id: int
    case_id: int
    result_status: str
    transcript_status: str
    reason: str
    released_at: UtcDateTime | None
    released_by: int | None
    # Display enrichment from existing Student / UfmCase / AuditLog joins
    student_roll: str | None = None
    student_name: str | None = None
    student_department: str | None = None
    student_program: str | None = None
    case_number: str | None = None
    case_status: str | None = None
    released_by_name: str | None = None
    held_by: int | None = None
    held_by_name: str | None = None
    held_at: UtcDateTime | None = None
    hold_source: str | None = None

    model_config = {"from_attributes": True}


class ResultControlCaseSummary(BaseModel):
    """Compact hold summary nested on UFM case payloads."""

    id: int
    result_status: str
    transcript_status: str
    reason: str
    released_at: UtcDateTime | None = None
    released_by: int | None = None
    released_by_name: str | None = None
    held_by: int | None = None
    held_by_name: str | None = None
    held_at: UtcDateTime | None = None
    hold_source: str | None = None
    case_id: int
    case_number: str | None = None
    student_name: str | None = None
    student_roll: str | None = None
