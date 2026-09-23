from datetime import datetime

from pydantic import BaseModel


class EvidenceOut(BaseModel):
    """JSON the API returns for evidence metadata."""

    id: int
    case_id: int | None
    detection_id: int | None
    evidence_type: str
    file_path: str
    timestamp: datetime
    camera_id: int | None
    seat_location: str | None
    confidence: float | None
    uploaded_by: int | None
    is_demo: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}
