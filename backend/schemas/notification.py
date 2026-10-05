from pydantic import BaseModel

from schemas.utc_datetime import UtcDateTime


class NotificationOut(BaseModel):
    id: int
    user_id: int
    case_id: int | None
    type: str
    title: str
    message: str
    is_read: bool
    created_at: UtcDateTime
    case_number: str | None = None
    case_status: str | None = None
    case_violation: str | None = None

    model_config = {"from_attributes": True}
