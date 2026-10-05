import json

from pydantic import BaseModel, Field, field_validator, model_validator

from schemas.exam import ExamCreate
from schemas.student import StudentCreate
from schemas.result_control import ResultControlCaseSummary
from schemas.utc_datetime import UtcDateTime
from ufm_form_constants import (
    RECOVERED_MATERIAL_CODES,
    primary_violation_from_recovered,
)

_ALLOWED_RECOVERED = frozenset(RECOVERED_MATERIAL_CODES)


class UfmCaseCreate(BaseModel):
    """JSON body the client sends when creating a UFM case.

    Provide either an existing student_id or filing-time manual_student
    (not both). Same rule for exam_id / manual_exam.
    Manual student/exam payloads are only resolved during case create —
    they do not grant Invigilator general master-data APIs.

    created_at / updated_at are server-assigned and must not be accepted
    from the client (extra fields are ignored).
    """

    model_config = {"extra": "ignore"}

    student_id: int | None = Field(default=None, gt=0)
    exam_id: int | None = Field(default=None, gt=0)
    manual_student: StudentCreate | None = None
    manual_exam: ExamCreate | None = None
    violation_type: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1)
    remarks: str | None = None
    recovered_materials: list[str] | None = None
    recovered_other_detail: str | None = None
    detection_id: int | None = None
    camera_id: int | None = Field(default=None, gt=0)
    evidence_ids: list[int] | None = Field(default=None, max_length=25)
    signer_name: str = Field(min_length=2, max_length=150)
    signature_ack: bool = True

    @field_validator("evidence_ids")
    @classmethod
    def _validate_evidence_ids(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        cleaned: list[int] = []
        seen: set[int] = set()
        for raw in value:
            eid = int(raw)
            if eid <= 0:
                raise ValueError("evidence_ids must contain positive integers")
            if eid not in seen:
                seen.add(eid)
                cleaned.append(eid)
        return cleaned or None

    @field_validator("recovered_materials")
    @classmethod
    def _validate_materials(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned: list[str] = []
        seen: set[str] = set()
        for raw in value:
            code = str(raw or "").strip().upper()
            if not code:
                continue
            if code not in _ALLOWED_RECOVERED:
                raise ValueError(
                    f"Invalid recovered material '{raw}'. "
                    f"Allowed: {', '.join(RECOVERED_MATERIAL_CODES)}"
                )
            if code not in seen:
                seen.add(code)
                cleaned.append(code)
        return cleaned or None

    @model_validator(mode="after")
    def _refs_or_manual_and_materials(self) -> "UfmCaseCreate":
        has_student_id = self.student_id is not None
        has_manual_student = self.manual_student is not None
        if has_student_id == has_manual_student:
            raise ValueError(
                "Provide exactly one of student_id or manual_student"
            )

        has_exam_id = self.exam_id is not None
        has_manual_exam = self.manual_exam is not None
        if has_exam_id == has_manual_exam:
            raise ValueError("Provide exactly one of exam_id or manual_exam")

        # Filing-time student registration must not attach portal users.
        if self.manual_student is not None and self.manual_student.user_id is not None:
            raise ValueError(
                "manual_student.user_id is not allowed during case filing"
            )

        materials = self.recovered_materials or []
        if "OTHER" in materials:
            detail = (self.recovered_other_detail or "").strip()
            if not detail:
                raise ValueError(
                    "recovered_other_detail is required when "
                    "'Other cheating material' is selected"
                )
            self.recovered_other_detail = detail
        elif self.recovered_other_detail:
            self.recovered_other_detail = None

        derived = primary_violation_from_recovered(materials)
        if derived:
            object.__setattr__(self, "violation_type", derived)
        return self


class UfmCaseOut(BaseModel):
    """JSON the API returns for a UFM case (enriched)."""

    id: int
    case_number: str
    student_id: int
    exam_id: int
    reported_by: int
    violation_type: str
    description: str
    remarks: str | None
    recovered_materials: list[str] | None = None
    recovered_other_detail: str | None = None
    status: str
    created_at: UtcDateTime
    updated_at: UtcDateTime
    signer_name: str | None = None
    signed_at: UtcDateTime | None = None
    signature_ack: bool = False
    student_roll: str | None = None
    student_name: str | None = None
    student_department: str | None = None
    student_program: str | None = None
    exam_course_code: str | None = None
    exam_course_name: str | None = None
    exam_semester: str | None = None
    exam_date: str | None = None
    room_number: str | None = None
    room_building: str | None = None
    camera_id: int | None = None
    camera_code: str | None = None
    camera_name: str | None = None
    reporter_name: str | None = None
    reporter_role: str | None = None
    result_control: ResultControlCaseSummary | None = None

    model_config = {"from_attributes": True}


def serialize_recovered_materials(materials: list[str] | None) -> str | None:
    if not materials:
        return None
    return json.dumps(materials)


def parse_recovered_materials(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(data, list):
        return None
    out = [str(x) for x in data if str(x) in _ALLOWED_RECOVERED]
    return out or None
