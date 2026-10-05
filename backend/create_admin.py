"""
Bootstrap the first (or an additional) ADMINISTRATOR portal account.

Usage (from backend directory, with DATABASE_URL / Compose env loaded):

  python create_admin.py --email university-admin@gmail.com
  python create_admin.py --email university-admin@gmail.com --name "University Admin"

Safe to re-run:
  - If the email already exists as ADMINISTRATOR → reports and exits 0
  - If the email exists with a different role → refuses (exit 1); no silent promote
  - Never creates a usable password (Google Sign-In only)
  - Never auto-promotes "first Google login"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from sqlalchemy import select

from admin_users_service import create_authorized_user, unusable_password_hash
from database import SessionLocal
from google_auth import normalize_email
from models.user import User


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create an explicit ADMINISTRATOR portal user for Google Sign-In."
    )
    parser.add_argument("--email", required=True, help="Authorized Google account email")
    parser.add_argument("--name", default=None, help="Display name (optional)")
    args = parser.parse_args()

    email_n = normalize_email(args.email)
    if not email_n or "@" not in email_n:
        print("ERROR: A valid email is required", file=sys.stderr)
        sys.exit(1)

    db = SessionLocal()
    try:
        existing = db.scalar(select(User).where(User.email == email_n))
        if existing is not None:
            if existing.role == "ADMINISTRATOR" and existing.is_active:
                print(
                    f"OK already ADMINISTRATOR id={existing.id} email={existing.email}"
                )
                sys.exit(0)
            print(
                f"ERROR: email already exists as role={existing.role} "
                f"active={existing.is_active} id={existing.id}. "
                "Refusing to change role automatically. "
                "Use Administrator User Management or provision tooling explicitly.",
                file=sys.stderr,
            )
            sys.exit(1)

        user = create_authorized_user(
            db,
            email=email_n,
            role="ADMINISTRATOR",
            name=args.name,
            student_roll=None,
            actor_id=None,
        )
        # Ensure hash is unusable even if create path changes later
        user.password_hash = unusable_password_hash()
        db.commit()
        db.refresh(user)
        print(
            f"CREATE ADMINISTRATOR id={user.id} email={user.email} active={user.is_active}"
        )
        print("Sign in with Google using this email. Role comes only from the database.")
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
