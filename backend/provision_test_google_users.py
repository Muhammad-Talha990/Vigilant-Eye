"""
Development-only: provision an explicitly authorized portal User for Google login.

Does NOT:
- authorize by email domain
- create users on Google login
- assign role from Google claims
- bulk-import addresses

Usage (from backend directory, with DATABASE_URL / .env loaded):

  python provision_test_google_users.py --email 232514@students.au.edu.pk --role STUDENT
  python provision_test_google_users.py --email staff@example.com --role HOD --name "Demo HOD"

Optional student roll link (STUDENT role only):

  python provision_test_google_users.py \\
    --email 232514@students.au.edu.pk --role STUDENT --student-roll 232514

Never commit real personal emails into source. Pass them only via CLI.
"""

from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from sqlalchemy import select

from database import SessionLocal
from google_auth import normalize_email
from models.student import Student
from models.user import User
from security import hash_password

ALLOWED_ROLES = frozenset(
    {
        "ADMINISTRATOR",
        "STUDENT",
        "INVIGILATOR",
        "HOD",
        "DEC",
        "EXAM_DEPARTMENT",
        "UFM_COMMITTEE",
    }
)


def provision(
    *,
    email: str,
    role: str,
    name: str | None = None,
    student_roll: str | None = None,
    activate: bool = True,
) -> User:
    email_n = normalize_email(email)
    role_u = role.strip().upper()
    if role_u not in ALLOWED_ROLES:
        raise ValueError(
            f"Invalid role '{role}'. Allowed: {', '.join(sorted(ALLOWED_ROLES))}"
        )
    if not email_n or "@" not in email_n:
        raise ValueError("A valid email is required")

    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email_n))
        display = (name or "").strip() or email_n.split("@")[0]
        if user is None:
            # Unusable random password — Google login does not use it.
            user = User(
                name=display,
                email=email_n,
                password_hash=hash_password(secrets.token_urlsafe(32)),
                role=role_u,
                is_active=activate,
            )
            db.add(user)
            db.flush()
            action = "CREATE"
        else:
            user.role = role_u
            user.is_active = activate
            if name:
                user.name = display
            action = "UPDATE"

        if role_u == "STUDENT" and student_roll:
            roll = student_roll.strip()
            linked = db.scalar(select(Student).where(Student.student_id == roll))
            if linked is None:
                linked = Student(
                    student_id=roll,
                    name=user.name,
                    department="Computer Science",
                    program="BSCS",
                    user_id=user.id,
                )
                db.add(linked)
                print(f"CREATE student roll {roll} → user_id={user.id}")
            else:
                # Clear other students pointing at this user
                other = db.scalar(
                    select(Student).where(
                        Student.user_id == user.id,
                        Student.id != linked.id,
                    )
                )
                if other:
                    other.user_id = None
                linked.user_id = user.id
                print(f"LINK student roll {roll} → user_id={user.id}")
        elif student_roll and role_u != "STUDENT":
            raise ValueError("--student-roll is only valid with --role STUDENT")

        db.commit()
        db.refresh(user)
        print(
            f"{action} {user.email} role={user.role} "
            f"active={user.is_active} id={user.id}"
        )
        print("Role is stored only in the database User row (not from Google).")
        return user
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Provision an explicitly authorized User for Google Sign-In tests."
    )
    parser.add_argument("--email", required=True, help="Authorized Google account email")
    parser.add_argument(
        "--role",
        required=True,
        help="Portal role (STUDENT, INVIGILATOR, HOD, DEC, EXAM_DEPARTMENT, UFM_COMMITTEE)",
    )
    parser.add_argument("--name", default=None, help="Display name (optional)")
    parser.add_argument(
        "--student-roll",
        default=None,
        help="Optional student roll number to create/link (STUDENT only)",
    )
    parser.add_argument(
        "--inactive",
        action="store_true",
        help="Create/update as inactive (login will be denied)",
    )
    args = parser.parse_args()
    try:
        provision(
            email=args.email,
            role=args.role,
            name=args.name,
            student_roll=args.student_roll,
            activate=not args.inactive,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
