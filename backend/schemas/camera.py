from pydantic import BaseModel, Field


class CameraCreate(BaseModel):
    """JSON body the client sends when creating a camera."""

    camera_id: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    room_id: int = Field(gt=0)
    stream_url: str = Field(min_length=1, max_length=255)
    is_active: bool = True


class CameraOut(BaseModel):
    """JSON the API returns for a camera."""

    id: int
    camera_id: str
    name: str
    room_id: int
    stream_url: str
    is_active: bool
    room_label: str | None = None
    source_kind: str | None = None
    stream_display: str | None = None

    model_config = {"from_attributes": True}
