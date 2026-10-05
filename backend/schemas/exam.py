from datetime import date, time

from pydantic import BaseModel, Field


class ExamCreate(BaseModel):
    """JSON body the client sends when creating an exam."""

    course_code: str = Field(min_length=1, max_length=50)
    course_name: str = Field(min_length=1, max_length=150)
    semester: str = Field(min_length=1, max_length=50)
    exam_date: date
    start_time: time
    end_time: time
    room_id: int = Field(gt=0)


class ExamOut(BaseModel):
    """JSON the API returns for an exam."""

    id: int
    course_code: str
    course_name: str
    semester: str
    exam_date: date
    start_time: time
    end_time: time
    room_id: int

    model_config = {"from_attributes": True}
