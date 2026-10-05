from pydantic import BaseModel

from schemas.utc_datetime import UtcDateTime


class AuditLogOut(BaseModel):
    """JSON the API returns for an audit log entry."""

    id: int
    user_id: int | None
    action: str
    entity_type: str
    entity_id: int | None
    description: str
    timestamp: UtcDateTime
    # Display enrichment from users.role — not stored on audit_logs.
    user_role: str | None = None

    model_config = {"from_attributes": True}
