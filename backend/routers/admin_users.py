"""Phase 18 — ADMINISTRATOR-only user management API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from admin_users_service import (
    build_user_query,
    classify_import_rows,
    create_authorized_user,
    ensure_not_last_admin,
    execute_import,
    link_student_roll,
    parse_users_csv,
    student_for_user,
    unlink_student,
    user_stats,
    user_to_admin_out,
    users_to_admin_out_many,
    validate_assignable_role,
    write_user_audit,
)
from database import get_db
from deps import require_roles
from models.user import User
from schemas.admin_user import (
    AdminStudentDirectoryItem,
    AdminStudentDirectoryOut,
    AdminUserCreate,
    AdminUserListOut,
    AdminUserOut,
    AdminUserStatsOut,
    AdminUserUpdate,
    ImportConfirmIn,
    ImportPreviewOut,
    ImportResultOut,
    ImportRowPreview,
)
from models.audit_log import AuditLog
from models.student import Student
from schemas.audit_log import AuditLogOut
from role_permissions_catalog import ROLE_PERMISSION_MATRIX
from app_config import (
    APP_ENV,
    IS_PRODUCTION,
    auth_mode,
    demo_helpers_enabled,
    google_auth_enabled,
    password_login_enabled,
)
from pydantic import BaseModel

router = APIRouter(prefix="/admin", tags=["admin-users"])

_admin = require_roles("ADMINISTRATOR")


class AdminAuditListOut(BaseModel):
    items: list[AuditLogOut]
    total: int


class AdminSystemInfoOut(BaseModel):
    project: str = "VigilantEye"
    app_env: str
    is_production: bool
    auth_mode: str
    google_auth_enabled: bool
    password_login_enabled: bool
    demo_helpers_enabled: bool
    portal_roles: list[str]
    api_available: bool = True
    database_available: bool = True
    application_version: str | None = None
    alembic_current_revision: str | None = None
    alembic_head_revision: str | None = None
    migrations_pending: bool | None = None
    # Phase 24 — safe email status (never secrets)
    email_notifications: str | None = None
    email_enabled: bool | None = None
    smtp_configured: bool | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_use_tls: bool | None = None
    smtp_from_configured: bool | None = None
    smtp_auth_configured: bool | None = None
    portal_base_url_configured: bool | None = None
    last_delivery_status: str | None = None
    last_delivery_at: str | None = None
    last_delivery_to_masked: str | None = None
    last_delivery_error_category: str | None = None


class AdminEmailTestOut(BaseModel):
    ok: bool
    result: str
    to_masked: str
    detail: str


class RolePermissionOut(BaseModel):
    role: str
    title: str
    summary: str
    can: list[str]
    cannot: list[str]


class AdminAuditActorOut(AuditLogOut):
    actor_email: str | None = None
    actor_name: str | None = None
    actor_role: str | None = None


class AdminAuditListEnrichedOut(BaseModel):
    items: list[AdminAuditActorOut]
    total: int


def _out(db: Session, user: User) -> AdminUserOut:
    return AdminUserOut(**user_to_admin_out(db, user))


@router.get("/users/stats", response_model=AdminUserStatsOut)
def admin_user_stats(
    db: Session = Depends(get_db),
    _: User = Depends(_admin),
):
    return AdminUserStatsOut(**user_stats(db))


@router.get("/users", response_model=AdminUserListOut)
def admin_list_users(
    q: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
    kind: str | None = Query(
        default=None,
        description="student | staff",
    ),
    linked: str | None = Query(
        default=None,
        description="linked | unlinked (students)",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(_admin),
):
    query = build_user_query(
        db,
        q=q,
        role=role,
        is_active=is_active,
        staff_or_student=kind,
        linked=linked,
    )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = list(
        db.scalars(query.offset((page - 1) * page_size).limit(page_size)).all()
    )
    return AdminUserListOut(
        items=[AdminUserOut(**row) for row in users_to_admin_out_many(db, rows)],
        total=int(total),
        page=page,
        page_size=page_size,
    )


@router.get("/users/{user_id}", response_model=AdminUserOut)
def admin_get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(_admin),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _out(db, user)


@router.post("/users", response_model=AdminUserOut, status_code=status.HTTP_201_CREATED)
def admin_create_user(
    body: AdminUserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin),
):
    user = create_authorized_user(
        db,
        email=str(body.email),
        role=body.role,
        name=body.name,
        student_roll=body.student_roll,
        actor_id=current_user.id,
        is_active=bool(body.is_active),
    )
    db.commit()
    db.refresh(user)
    return _out(db, user)


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def admin_patch_user(
    user_id: int,
    body: AdminUserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if body.name is not None:
        user.name = body.name.strip()

    if body.role is not None:
        new_role = validate_assignable_role(body.role)
        if new_role != user.role:
            ensure_not_last_admin(db, user, new_role=new_role)
            old = user.role
            user.role = new_role
            write_user_audit(
                db,
                actor_id=current_user.id,
                action="USER_ROLE_CHANGED",
                target_user_id=user.id,
                description=f"Role {old} → {new_role} for {user.email}",
            )
            if new_role != "STUDENT":
                unlink_student(db, user)
                write_user_audit(
                    db,
                    actor_id=current_user.id,
                    action="USER_STUDENT_UNLINKED",
                    target_user_id=user.id,
                    description=f"Cleared student link after role change to {new_role}",
                )

    if body.unlink_student:
        if student_for_user(db, user.id):
            unlink_student(db, user)
            write_user_audit(
                db,
                actor_id=current_user.id,
                action="USER_STUDENT_UNLINKED",
                target_user_id=user.id,
                description=f"Unlinked student from {user.email}",
            )
    elif body.student_roll is not None:
        roll = body.student_roll.strip()
        if roll == "":
            unlink_student(db, user)
            write_user_audit(
                db,
                actor_id=current_user.id,
                action="USER_STUDENT_UNLINKED",
                target_user_id=user.id,
                description=f"Unlinked student from {user.email}",
            )
        else:
            if user.role != "STUDENT":
                raise HTTPException(
                    status_code=400,
                    detail="Only STUDENT accounts can be linked to a student roll",
                )
            link_student_roll(db, user, roll, create_if_missing=True)
            write_user_audit(
                db,
                actor_id=current_user.id,
                action="USER_STUDENT_LINKED",
                target_user_id=user.id,
                description=f"Linked {user.email} to student roll {roll}",
            )

    db.commit()
    db.refresh(user)
    return _out(db, user)


@router.post("/users/{user_id}/activate", response_model=AdminUserOut)
def admin_activate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        user.is_active = True
        write_user_audit(
            db,
            actor_id=current_user.id,
            action="USER_REACTIVATED",
            target_user_id=user.id,
            description=f"Reactivated {user.email}",
        )
        db.commit()
        db.refresh(user)
    return _out(db, user)


@router.post("/users/{user_id}/deactivate", response_model=AdminUserOut)
def admin_deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    ensure_not_last_admin(db, user, new_active=False)
    if user.is_active:
        user.is_active = False
        write_user_audit(
            db,
            actor_id=current_user.id,
            action="USER_DEACTIVATED",
            target_user_id=user.id,
            description=f"Deactivated {user.email}",
        )
        db.commit()
        db.refresh(user)
    return _out(db, user)


@router.post("/users/import/preview", response_model=ImportPreviewOut)
async def admin_import_preview(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(_admin),
):
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(raw) > 2_000_000:
        raise HTTPException(status_code=400, detail="CSV too large (max 2MB)")
    parsed = parse_users_csv(raw)
    classified = classify_import_rows(db, parsed)

    def _map(items: list[dict]) -> list[ImportRowPreview]:
        return [ImportRowPreview(**i) for i in items]

    return ImportPreviewOut(
        total_rows=len(parsed),
        valid=_map(classified["valid"]),
        invalid=_map(classified["invalid"]),
        duplicates=_map(classified["duplicates"]),
        conflicts=_map(classified["conflicts"]),
        role_conflicts=_map(classified.get("role_conflicts") or []),
        student_link_problems=_map(classified.get("student_link_problems") or []),
        already_exists=_map(classified["already_exists"]),
        can_import_count=len(classified["valid"]),
    )


@router.post("/users/import", response_model=ImportResultOut)
def admin_import_confirm(
    body: ImportConfirmIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin),
):
    if not body.rows:
        raise HTTPException(status_code=400, detail="No rows to import")
    try:
        result = execute_import(db, rows=body.rows, actor_id=current_user.id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return ImportResultOut(**result)


_USER_ADMIN_ACTIONS = frozenset(
    {
        "USER_CREATED",
        "USER_ROLE_CHANGED",
        "USER_DEACTIVATED",
        "USER_REACTIVATED",
        "USER_STUDENT_LINKED",
        "USER_STUDENT_UNLINKED",
        "USER_BULK_IMPORTED",
    }
)


@router.get("/audit-logs", response_model=AdminAuditListEnrichedOut)
def admin_audit_logs(
    q: str | None = None,
    action: str | None = None,
    user_admin_only: bool = Query(
        True,
        description="When true, only user-management audit actions",
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(_admin),
):
    query = select(AuditLog)
    if user_admin_only:
        query = query.where(AuditLog.action.in_(sorted(_USER_ADMIN_ACTIONS)))
    if action:
        query = query.where(AuditLog.action == action.strip().upper())
    if q:
        term = f"%{q.strip()}%"
        query = query.where(AuditLog.description.ilike(term))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = list(
        db.scalars(query.order_by(AuditLog.id.desc()).offset(offset).limit(limit)).all()
    )
    actor_ids = {r.user_id for r in rows if r.user_id}
    actors = {}
    if actor_ids:
        for u in db.scalars(select(User).where(User.id.in_(actor_ids))).all():
            actors[u.id] = u
    items: list[AdminAuditActorOut] = []
    for r in rows:
        actor = actors.get(r.user_id) if r.user_id else None
        items.append(
            AdminAuditActorOut(
                id=r.id,
                user_id=r.user_id,
                action=r.action,
                entity_type=r.entity_type,
                entity_id=r.entity_id,
                description=r.description,
                timestamp=r.timestamp,
                actor_email=actor.email if actor else None,
                actor_name=actor.name if actor else None,
                actor_role=actor.role if actor else None,
            )
        )
    return AdminAuditListEnrichedOut(items=items, total=int(total))


@router.get("/students", response_model=AdminStudentDirectoryOut)
def admin_student_directory(
    q: str | None = None,
    linked: str | None = Query(None, description="linked | unlinked"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(_admin),
):
    """Access-management student directory — not the operational UFM Students page."""
    query = select(Student)
    if q:
        term = f"%{q.strip()}%"
        query = query.where(
            or_(
                Student.student_id.ilike(term),
                Student.name.ilike(term),
                Student.department.ilike(term),
                Student.program.ilike(term),
            )
        )
    if linked == "linked":
        query = query.where(Student.user_id.is_not(None))
    elif linked == "unlinked":
        query = query.where(Student.user_id.is_(None))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = list(
        db.scalars(
            query.order_by(Student.id).offset((page - 1) * page_size).limit(page_size)
        ).all()
    )
    user_ids = {s.user_id for s in rows if s.user_id is not None}
    users_by_id: dict[int, User] = {}
    if user_ids:
        for u in db.scalars(select(User).where(User.id.in_(user_ids))).all():
            users_by_id[u.id] = u
    items: list[AdminStudentDirectoryItem] = []
    for s in rows:
        portal = users_by_id.get(s.user_id) if s.user_id else None
        items.append(
            AdminStudentDirectoryItem(
                id=s.id,
                student_id=s.student_id,
                name=s.name,
                department=s.department,
                program=s.program,
                user_id=s.user_id,
                linked_email=portal.email if portal else None,
                linked_name=portal.name if portal else None,
                portal_active=portal.is_active if portal else None,
                portal_role=portal.role if portal else None,
            )
        )
    return AdminStudentDirectoryOut(
        items=items,
        total=int(total),
        page=page,
        page_size=page_size,
    )


@router.get("/system-info", response_model=AdminSystemInfoOut)
def admin_system_info(
    db: Session = Depends(get_db),
    _: User = Depends(_admin),
):
    """Non-secret runtime flags for the Administrator System page."""
    from portal_roles import PORTAL_ROLES
    from db_migrations import get_alembic_migration_status

    db_ok = True
    mig = {
        "current_revision": None,
        "head_revision": None,
        "migrations_pending": None,
    }
    try:
        db.execute(select(1))
        mig = get_alembic_migration_status()
    except Exception:  # noqa: BLE001
        db_ok = False

    version = None
    try:
        from main import app as fastapi_app

        version = getattr(fastapi_app, "version", None) or None
    except Exception:  # noqa: BLE001
        version = None

    from email_notify import get_email_status

    email = get_email_status()

    return AdminSystemInfoOut(
        app_env=APP_ENV,
        is_production=IS_PRODUCTION,
        auth_mode=auth_mode(),
        google_auth_enabled=google_auth_enabled(),
        password_login_enabled=password_login_enabled(),
        demo_helpers_enabled=demo_helpers_enabled(),
        portal_roles=sorted(PORTAL_ROLES),
        api_available=True,
        database_available=db_ok,
        application_version=version,
        alembic_current_revision=mig.get("current_revision"),
        alembic_head_revision=mig.get("head_revision"),
        migrations_pending=mig.get("migrations_pending"),
        email_notifications=email.get("email_notifications"),
        email_enabled=email.get("email_enabled"),
        smtp_configured=email.get("smtp_configured"),
        smtp_host=email.get("smtp_host"),
        smtp_port=email.get("smtp_port"),
        smtp_use_tls=email.get("smtp_use_tls"),
        smtp_from_configured=email.get("smtp_from_configured"),
        smtp_auth_configured=email.get("smtp_auth_configured"),
        portal_base_url_configured=email.get("portal_base_url_configured"),
        last_delivery_status=email.get("last_delivery_status"),
        last_delivery_at=email.get("last_delivery_at"),
        last_delivery_to_masked=email.get("last_delivery_to_masked"),
        last_delivery_error_category=email.get("last_delivery_error_category"),
    )


@router.post("/email/test", response_model=AdminEmailTestOut)
def admin_send_test_email(
    db: Session = Depends(get_db),
    admin: User = Depends(_admin),
):
    """
    Send a controlled test email to the authenticated Administrator's User.email.

    Does not accept arbitrary recipient addresses from the client.
    """
    from email_notify import PORTAL_BASE_URL, mask_email, send_email
    from email_templates import build_test_email

    recipient = (admin.email or "").strip()
    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrator account has no User.email",
        )
    if not bool(admin.is_active):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive accounts cannot send test email",
        )

    content = build_test_email(portal_base_url=PORTAL_BASE_URL or None)
    result = send_email(
        to_email=recipient,
        subject=content.subject,
        body=content.text,
        html=content.html,
    )
    masked = mask_email(recipient)
    write_user_audit(
        db,
        actor_id=admin.id,
        action="ADMIN_EMAIL_TEST",
        target_user_id=admin.id,
        description=f"Administrator email test result={result} to={masked}",
    )
    db.commit()

    ok = result in {"sent", "mock"}
    if result == "sent":
        detail = "SMTP accepted the test message for your User.email."
    elif result == "mock":
        detail = (
            "Email is enabled but SMTP is not fully configured; "
            "test recorded as EMAIL_MOCK (no real delivery)."
        )
    elif result == "disabled":
        detail = "Email notifications are disabled (EMAIL_ENABLED=0)."
    else:
        detail = (
            "SMTP delivery failed. Check server logs (error category only) "
            "and SMTP_* configuration. Portal operations are unaffected."
        )

    return AdminEmailTestOut(
        ok=ok,
        result=result,
        to_masked=masked,
        detail=detail,
    )


@router.get("/roles", response_model=list[RolePermissionOut])
def admin_roles_catalog(_: User = Depends(_admin)):
    return [RolePermissionOut(**row) for row in ROLE_PERMISSION_MATRIX]
