from pydantic import BaseModel, Field

from schemas.utc_datetime import UtcDateTime


class DetectionOut(BaseModel):
    id: int
    camera_id: int | None
    student_id: int | None
    detection_type: str
    confidence: float
    timestamp: UtcDateTime
    is_confirmed: bool
    is_seen: bool = False
    is_demo: bool = False
    source_path: str | None
    frame_index: int | None
    model_version: str | None = None

    model_config = {"from_attributes": True}


class DraftCaseFromDetection(BaseModel):
    student_id: int = Field(gt=0)
    exam_id: int = Field(gt=0)
