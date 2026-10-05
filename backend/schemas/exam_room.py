from pydantic import BaseModel, Field


class ExamRoomCreate(BaseModel):
    """JSON body the client sends when creating an exam room."""

    room_number: str = Field(min_length=1, max_length=50)
    building: str = Field(min_length=1, max_length=100)
    capacity: int = Field(gt=0)


class ExamRoomOut(BaseModel):
    """JSON the API returns for an exam room."""

    id: int
    room_number: str
    building: str
    capacity: int

    model_config = {"from_attributes": True}
