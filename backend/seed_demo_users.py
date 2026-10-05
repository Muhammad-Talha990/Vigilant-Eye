"""
Create demo users for every VigilantEye role (safe to re-run).

Usage (from backend folder, venv active):
    python seed_demo_users.py

Default password for all demo users: Demo@123
(Demo accounts use an 8+ character password that satisfies production UserCreate policy.)

Ensures student roll DEMO001 exists and is linked to student@demo.com via user_id.
"""

from sqlalchemy import select

from database import SessionLocal
from models.student import Student
from models.user import User
from security import hash_password

DEMO_PASSWORD = "Demo@123"
DEMO_STUDENT_ROLL = "DEMO001"
DEMO_STUDENT_EMAIL = "student@demo.com"

DEMO_USERS = [
    ("Demo Student", "student@demo.com", "STUDENT"),
    ("Demo Invigilator", "invigilator@demo.com", "INVIGILATOR"),
    ("Demo HOD", "hod@demo.com", "HOD"),
    ("Demo DEC", "dec@demo.com", "DEC"),
    ("Demo Exam Department", "examdept@demo.com", "EXAM_DEPARTMENT"),
    ("Demo UFM Committee", "ufm@demo.com", "UFM_COMMITTEE"),
]


def seed(*, quiet: bool = False) -> None:
    def log(msg: str) -> None:
        if not quiet:
            print(msg)

    db = SessionLocal()
    try:
        created = 0
        skipped = 0
        for name, email, role in DEMO_USERS:
            existing = db.scalar(select(User).where(User.email == email))
            if existing:
                log(f"SKIP  {email} (already exists, role={existing.role})")
                skipped += 1
                continue

            db.add(
                User(
                    name=name,
                    email=email,
                    password_hash=hash_password(DEMO_PASSWORD),
                    role=role,
                    is_active=True,
                )
            )
            log(f"CREATE {email}  role={role}")
            created += 1

        db.flush()

        student_user = db.scalar(
            select(User).where(User.email == DEMO_STUDENT_EMAIL)
        )
        linked = db.scalar(
            select(Student).where(Student.student_id == DEMO_STUDENT_ROLL)
        )
        if linked is None:
            linked = Student(
                student_id=DEMO_STUDENT_ROLL,
                name="Demo Student",
                department="Computer Science",
                program="BSCS",
                user_id=student_user.id if student_user else None,
            )
            db.add(linked)
            log(
                f"CREATE student roll {DEMO_STUDENT_ROLL} "
                f"(user_id={student_user.id if student_user else None})"
            )
        elif student_user and linked.user_id != student_user.id:
            # Clear any other student that already owns this portal user
            other = db.scalar(
                select(Student).where(
                    Student.user_id == student_user.id,
                    Student.id != linked.id,
                )
            )
            if other:
                other.user_id = None
                log(
                    f"UNLINK student id={other.id} from user_id={student_user.id}"
                )
            linked.user_id = student_user.id
            log(
                f"LINK  roll {DEMO_STUDENT_ROLL} -> {DEMO_STUDENT_EMAIL} "
                f"(user_id={student_user.id})"
            )
        else:
            log(
                f"SKIP  student roll {DEMO_STUDENT_ROLL} "
                f"(id={linked.id}, user_id={linked.user_id})"
            )

        db.commit()
        log("")
        log(f"Done. created={created}, skipped={skipped}")
        # Credentials are documented in README — never print passwords in logs.
        log(
            f"Portal link: {DEMO_STUDENT_EMAIL} <-> roll {DEMO_STUDENT_ROLL} via user_id"
        )
        log("Demo account password: see README (not printed here).")
    finally:
        db.close()


if __name__ == "__main__":
    import sys

    from app_config import demo_seed_enabled

    if not demo_seed_enabled():
        print(
            "Refusing to seed demo users: production mode without "
            "ENABLE_DEMO_SEED=1. Development/viva: unset APP_ENV or set "
            "APP_ENV=development. Explicit lab: ENABLE_DEMO_SEED=1."
        )
        sys.exit(1)
    seed()
