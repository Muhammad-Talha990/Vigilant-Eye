"""Pydantic schemas for Phase 18 Administrator user management."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field

from schemas.utc_datetime import UtcDateTime


class AdminUserCreate(BaseModel):
    email: EmailStr
    role: str = Field(min_length=1, max_length=50)
    name: str | None = Field(default=None, max_length=100)
    student_roll: str | None = Field(default=None, max_length=50)
    is_active: bool = True


class AdminUserUpdate(BaseModel):
    """Partial update. Email is intentionally omitted — unsafe without identity migration.

    Role changes and activation also have dedicated endpoints.
    """

    name: str | None = Field(default=None, min_length=1, max_length=100)
    role: str | None = Field(default=None, min_length=1, max_length=50)
    student_roll: str | None = Field(
        default=None,
        max_length=50,
        description="Set to link STUDENT; empty string unlinks.",
    )
    unlink_student: bool = False


class AdminUserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str
    is_active: bool
    created_at: UtcDateTime
    student_roll: str | None = None
    student_pk: int | None = None

    model_config = {"from_attributes": True}


class AdminUserListOut(BaseModel):
    items: list[AdminUserOut]
    total: int
    page: int
    page_size: int


class AdminUserStatsOut(BaseModel):
    total: int
    active: int
    inactive: int
    by_role: dict[str, int]
    students_linked: int
    students_unlinked: int


class ImportRowPreview(BaseModel):
    row_number: int
    email: str
    role: str
    name: str | None = None
    student_roll: str | None = None
    status: Literal[
        "valid",
        "invalid",
        "duplicate_in_file",
        "already_exists",
        "conflict",
        "rejected",
    ]
    detail: str


class ImportPreviewOut(BaseModel):
    total_rows: int
    valid: list[ImportRowPreview]
    invalid: list[ImportRowPreview]
    duplicates: list[ImportRowPreview]
    conflicts: list[ImportRowPreview]
    role_conflicts: list[ImportRowPreview] = Field(default_factory=list)
    student_link_problems: list[ImportRowPreview] = Field(default_factory=list)
    already_exists: list[ImportRowPreview]
    can_import_count: int


class ImportConfirmIn(BaseModel):
    """Rows to import — typically the valid preview rows only."""

    rows: list[dict[str, Any]] = Field(default_factory=list)


class ImportResultOut(BaseModel):
    created: int
    already_existing: int
    rejected: int
    conflicts: int
    invalid: int
    errors: list[str] = Field(default_factory=list)
    created_ids: list[int] = Field(default_factory=list)


class AdminStudentDirectoryItem(BaseModel):
    """Student directory row with linked portal identity (Phase 20)."""

    id: int
    student_id: str
    name: str
    department: str
    program: str
    user_id: int | None = None
    linked_email: str | None = None
    linked_name: str | None = None
    portal_active: bool | None = None
    portal_role: str | None = None


class AdminStudentDirectoryOut(BaseModel):
    items: list[AdminStudentDirectoryItem]
    total: int
    page: int
    page_size: int
