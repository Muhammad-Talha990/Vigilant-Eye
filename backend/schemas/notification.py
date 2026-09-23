from datetime import datetime

from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: int
    user_id: int
    case_id: int | None
    type: str
    title: str
    message: str
    is_read: bool
    created_at: datetime
    case_number: str | None = None
    case_status: str | None = None
    case_violation: str | None = None

    model_config = {"from_attributes": True}
