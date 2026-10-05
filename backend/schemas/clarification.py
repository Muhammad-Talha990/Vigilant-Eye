from pydantic import BaseModel, Field

from schemas.utc_datetime import UtcDateTime


class ClarificationCreate(BaseModel):
    case_id: int = Field(gt=0)
    statement: str = Field(min_length=10, max_length=5000)


class ClarificationOut(BaseModel):
    id: int
    case_id: int
    student_user_id: int
    statement: str
    status: str
    created_at: UtcDateTime

    model_config = {"from_attributes": True}
