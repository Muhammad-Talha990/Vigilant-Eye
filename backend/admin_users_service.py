"""Administrator user-management business logic (Phase 18).

Google authenticates identity; this module manages VigilantEye authorization rows.
"""

from __future__ import annotations

import csv
import io
import secrets
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from google_auth import normalize_email
from models.audit_log import AuditLog
from models.student import Student
from models.user import User
from portal_roles import (
    ADMIN_ASSIGNABLE_ROLES,
    PORTAL_ROLES,
    normalize_role,
)
from security import hash_password


def write_user_audit(
    db: Session,
    *,
    actor_id: int | None,
    action: str,
    target_user_id: int | None,
    description: str,
) -> None:
    db.add(
        AuditLog(
            user_id=actor_id,
            action=action,
            entity_type="user",
            entity_id=target_user_id,
            description=description,
        )
    )


def unusable_password_hash() -> str:
    return hash_password(secrets.token_urlsafe(32))


def count_active_administrators(db: Session, *, excluding_user_id: int | None = None) -> int:
    q = select(func.count()).select_from(User).where(
        User.role == "ADMINISTRATOR",
        User.is_active.is_(True),
    )
    if excluding_user_id is not None:
        q = q.where(User.id != excluding_user_id)
    return int(db.scalar(q) or 0)


def ensure_not_last_admin(
    db: Session,
    user: User,
    *,
    new_role: str | None = None,
    new_active: bool | None = None,
) -> None:
    """Block demotion/deactivation of the last active ADMINISTRATOR."""
    if user.role != "ADMINISTRATOR" or not user.is_active:
        return
    role_after = normalize_role(new_role) if new_role is not None else user.role
    active_after = user.is_active if new_active is None else bool(new_active)
    still_admin = role_after == "ADMINISTRATOR" and active_after
    if still_admin:
        return
    others = count_active_administrators(db, excluding_user_id=user.id)
    if others < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot demote or deactivate the last active ADMINISTRATOR",
        )


def student_for_user(db: Session, user_id: int) -> Student | None:
    return db.scalar(select(Student).where(Student.user_id == user_id))


def _user_dict(user: User, linked: Student | None) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "student_roll": linked.student_id if linked else None,
        "student_pk": linked.id if linked else None,
    }


def user_to_admin_out(db: Session, user: User) -> dict:
    return _user_dict(user, student_for_user(db, user.id))


def users_to_admin_out_many(db: Session, users: list[User]) -> list[dict]:
    """Batch student-link lookup to avoid N+1 on paginated lists."""
    if not users:
        return []
    ids = [u.id for u in users]
    by_user: dict[int, Student] = {}
    for st in db.scalars(select(Student).where(Student.user_id.in_(ids))).all():
        if st.user_id is not None:
            by_user[st.user_id] = st
    return [_user_dict(u, by_user.get(u.id)) for u in users]


def validate_assignable_role(role: str) -> str:
    role_u = normalize_role(role)
    if role_u not in ADMIN_ASSIGNABLE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Allowed: {', '.join(sorted(ADMIN_ASSIGNABLE_ROLES))}",
        )
    return role_u


def link_student_roll(
    db: Session,
    user: User,
    student_roll: str | None,
    *,
    create_if_missing: bool = True,
) -> Student | None:
    """Link STUDENT user to a Student row. Clears prior links for this user."""
    if user.role != "STUDENT":
        if student_roll:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="student_roll is only valid for STUDENT role",
            )
        return None

    roll = (student_roll or "").strip()
    if not roll:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="student_roll is required for STUDENT accounts",
        )

    # Clear other students pointing at this user
    for other in db.scalars(select(Student).where(Student.user_id == user.id)).all():
        other.user_id = None

    linked = db.scalar(select(Student).where(Student.student_id == roll))
    if linked is None:
        if not create_if_missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Student roll {roll} not found",
            )
        linked = Student(
            student_id=roll,
            name=user.name,
            department="Unassigned",
            program="Unassigned",
            user_id=user.id,
        )
        db.add(linked)
        db.flush()
        return linked

    if linked.user_id is not None and linked.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Student roll {roll} is already linked to another portal user",
        )
    linked.user_id = user.id
    return linked


def unlink_student(db: Session, user: User) -> None:
    for row in db.scalars(select(Student).where(Student.user_id == user.id)).all():
        row.user_id = None


def create_authorized_user(
    db: Session,
    *,
    email: str,
    role: str,
    name: str | None,
    student_roll: str | None,
    actor_id: int | None,
    is_active: bool = True,
) -> User:
    email_n = normalize_email(email)
    role_u = validate_assignable_role(role)
    if not email_n or "@" not in email_n:
        raise HTTPException(status_code=400, detail="A valid email is required")

    existing = db.scalar(select(User).where(User.email == email_n))
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    display = (name or "").strip() or email_n.split("@")[0]
    user = User(
        name=display[:100],
        email=email_n,
        password_hash=unusable_password_hash(),
        role=role_u,
        is_active=bool(is_active),
    )
    db.add(user)
    db.flush()

    if role_u == "STUDENT":
        link_student_roll(db, user, student_roll, create_if_missing=True)
    elif student_roll:
        raise HTTPException(
            status_code=400,
            detail="student_roll is only valid for STUDENT role",
        )

    write_user_audit(
        db,
        actor_id=actor_id,
        action="USER_CREATED",
        target_user_id=user.id,
        description=f"Created {email_n} as {role_u}",
    )
    return user


@dataclass
class ParsedImportRow:
    row_number: int
    email: str
    role: str
    name: str | None
    student_roll: str | None


def parse_users_csv(content: bytes | str) -> list[ParsedImportRow]:
    if isinstance(content, bytes):
        text = content.decode("utf-8-sig")
    else:
        text = content
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV has no header row")
    fields = {((f or "").strip().lower()): (f or "") for f in reader.fieldnames}
    required = {"email", "role"}
    missing = required - set(fields)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"CSV missing required columns: {', '.join(sorted(missing))}",
        )

    rows: list[ParsedImportRow] = []
    for i, raw in enumerate(reader, start=2):  # header is line 1
        email = (raw.get(fields["email"]) or "").strip()
        role = (raw.get(fields["role"]) or "").strip()
        name_key = fields.get("name")
        roll_key = fields.get("student_roll")
        name = (raw.get(name_key) or "").strip() if name_key else ""
        roll = (raw.get(roll_key) or "").strip() if roll_key else ""
        rows.append(
            ParsedImportRow(
                row_number=i,
                email=email,
                role=role,
                name=name or None,
                student_roll=roll or None,
            )
        )
    return rows


def classify_import_rows(db: Session, rows: list[ParsedImportRow]) -> dict[str, list[dict]]:
    buckets: dict[str, list[dict]] = {
        "valid": [],
        "invalid": [],
        "duplicates": [],
        "conflicts": [],
        "role_conflicts": [],
        "student_link_problems": [],
        "already_exists": [],
    }
    seen_emails: dict[str, int] = {}
    seen_rolls: dict[str, int] = {}

    for row in rows:
        email_n = normalize_email(row.email)
        role_u = normalize_role(row.role)
        base = {
            "row_number": row.row_number,
            "email": email_n or row.email,
            "role": role_u or row.role,
            "name": row.name,
            "student_roll": row.student_roll,
        }

        if not email_n or "@" not in email_n:
            buckets["invalid"].append({**base, "status": "invalid", "detail": "Invalid email"})
            continue
        if role_u not in PORTAL_ROLES:
            buckets["invalid"].append(
                {
                    **base,
                    "status": "invalid",
                    "detail": f"Unsupported role '{row.role}'",
                }
            )
            continue
        if role_u == "STUDENT" and not (row.student_roll or "").strip():
            buckets["invalid"].append(
                {
                    **base,
                    "status": "invalid",
                    "detail": "student_roll required for STUDENT",
                }
            )
            continue
        if role_u != "STUDENT" and (row.student_roll or "").strip():
            buckets["invalid"].append(
                {
                    **base,
                    "status": "invalid",
                    "detail": "student_roll not allowed for staff roles",
                }
            )
            continue

        if email_n in seen_emails:
            buckets["duplicates"].append(
                {
                    **base,
                    "status": "duplicate_in_file",
                    "detail": f"Duplicate email of row {seen_emails[email_n]}",
                }
            )
            continue
        seen_emails[email_n] = row.row_number

        roll = (row.student_roll or "").strip()
        if role_u == "STUDENT" and roll:
            if roll in seen_rolls:
                buckets["duplicates"].append(
                    {
                        **base,
                        "status": "duplicate_in_file",
                        "detail": f"Duplicate student_roll of row {seen_rolls[roll]}",
                    }
                )
                continue
            seen_rolls[roll] = row.row_number

        existing = db.scalar(select(User).where(User.email == email_n))
        if existing is not None:
            if normalize_role(existing.role) != role_u:
                item = {
                    **base,
                    "status": "conflict",
                    "detail": (
                        f"Existing user id={existing.id} has role "
                        f"{existing.role}; will not overwrite"
                    ),
                }
                buckets["conflicts"].append(item)
                buckets["role_conflicts"].append(item)
            else:
                buckets["already_exists"].append(
                    {
                        **base,
                        "status": "already_exists",
                        "detail": f"Already registered as {existing.role} (id={existing.id})",
                    }
                )
            continue

        if role_u == "STUDENT" and roll:
            linked = db.scalar(select(Student).where(Student.student_id == roll))
            if linked is not None and linked.user_id is not None:
                item = {
                    **base,
                    "status": "conflict",
                    "detail": f"Student roll {roll} already linked to user_id={linked.user_id}",
                }
                buckets["conflicts"].append(item)
                buckets["student_link_problems"].append(item)
                continue

        buckets["valid"].append(
            {**base, "status": "valid", "detail": "Ready to create"}
        )

    return buckets


def execute_import(
    db: Session,
    *,
    rows: list[dict],
    actor_id: int,
) -> dict:
    """
    Create users for validated rows only.
    Never silently overwrites existing roles.
    Single transaction; raises → caller rolls back.
    """
    created_ids: list[int] = []
    already = 0
    rejected = 0
    conflicts = 0
    invalid = 0
    errors: list[str] = []

    # Re-classify from payload for safety (never trust client status labels alone)
    parsed = [
        ParsedImportRow(
            row_number=int(r.get("row_number") or 0),
            email=str(r.get("email") or ""),
            role=str(r.get("role") or ""),
            name=(str(r["name"]) if r.get("name") else None),
            student_roll=(str(r["student_roll"]) if r.get("student_roll") else None),
        )
        for r in rows
    ]
    classified = classify_import_rows(db, parsed)

    for bucket, key in (
        (classified["invalid"], "invalid"),
        (classified["duplicates"], "rejected"),
        (classified["conflicts"], "conflicts"),
        (classified["already_exists"], "already"),
    ):
        n = len(bucket)
        if key == "invalid":
            invalid += n
        elif key == "rejected":
            rejected += n
        elif key == "conflicts":
            conflicts += n
        else:
            already += n

    for item in classified["valid"]:
        try:
            user = create_authorized_user(
                db,
                email=item["email"],
                role=item["role"],
                name=item.get("name"),
                student_roll=item.get("student_roll"),
                actor_id=actor_id,
            )
            created_ids.append(user.id)
        except HTTPException as exc:
            rejected += 1
            errors.append(f"row {item.get('row_number')}: {exc.detail}")
        except Exception as exc:  # noqa: BLE001
            rejected += 1
            errors.append(f"row {item.get('row_number')}: {exc}")

    write_user_audit(
        db,
        actor_id=actor_id,
        action="USER_BULK_IMPORTED",
        target_user_id=None,
        description=(
            f"Bulk import created={len(created_ids)} already={already} "
            f"conflicts={conflicts} invalid={invalid} rejected={rejected}"
        ),
    )
    return {
        "created": len(created_ids),
        "already_existing": already,
        "rejected": rejected,
        "conflicts": conflicts,
        "invalid": invalid,
        "errors": errors,
        "created_ids": created_ids,
    }


def build_user_query(
    db: Session,
    *,
    q: str | None,
    role: str | None,
    is_active: bool | None,
    staff_or_student: str | None,
    linked: str | None,
):
    query = select(User)
    if q:
        term = f"%{q.strip().lower()}%"
        roll_ids = list(
            db.scalars(
                select(Student.user_id).where(
                    Student.student_id.ilike(term),
                    Student.user_id.is_not(None),
                )
            ).all()
        )
        clauses = [
            func.lower(User.email).like(term),
            func.lower(User.name).like(term),
        ]
        if q.strip().isdigit():
            clauses.append(User.id == int(q.strip()))
        if roll_ids:
            clauses.append(User.id.in_(roll_ids))
        query = query.where(or_(*clauses))

    if role:
        query = query.where(User.role == normalize_role(role))
    if is_active is not None:
        query = query.where(User.is_active.is_(is_active))
    if staff_or_student == "student":
        query = query.where(User.role == "STUDENT")
    elif staff_or_student == "staff":
        query = query.where(User.role.in_(list(PORTAL_ROLES - {"STUDENT"})))

    if linked in {"linked", "unlinked"}:
        linked_ids = set(
            db.scalars(
                select(Student.user_id).where(Student.user_id.is_not(None))
            ).all()
        )
        if linked == "linked":
            query = query.where(User.id.in_(linked_ids or [-1]))
        else:
            if linked_ids:
                query = query.where(
                    User.role == "STUDENT",
                    User.id.notin_(linked_ids),
                )
            else:
                query = query.where(User.role == "STUDENT")

    return query.order_by(User.id)


def user_stats(db: Session) -> dict:
    """Aggregate stats without loading every User row into Python."""
    total = int(db.scalar(select(func.count()).select_from(User)) or 0)
    active = int(
        db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True)))
        or 0
    )
    inactive = max(0, total - active)
    by_role = {r: 0 for r in sorted(PORTAL_ROLES)}
    for role, count in db.execute(
        select(User.role, func.count()).group_by(User.role)
    ).all():
        by_role[str(role)] = int(count)
    students_total = by_role.get("STUDENT", 0)
    linked = int(
        db.scalar(
            select(func.count()).select_from(Student).where(
                Student.user_id.is_not(None),
                Student.user_id.in_(
                    select(User.id).where(User.role == "STUDENT")
                ),
            )
        )
        or 0
    )
    return {
        "total": total,
        "active": active,
        "inactive": inactive,
        "by_role": by_role,
        "students_linked": linked,
        "students_unlinked": max(0, students_total - linked),
    }
