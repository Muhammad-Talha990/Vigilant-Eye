"""Temporary acceptance helper: reactivate *@demo.com users and reset demo password."""

from sqlalchemy import select

from database import SessionLocal
from models.user import User
from security import hash_password

# Same documented demo password as seed_demo_users / README — not printed.
DEMO_PASSWORD = "Demo@123"


def main() -> None:
    db = SessionLocal()
    try:
        rows = db.scalars(select(User).where(User.email.like("%@demo.com"))).all()
        for u in rows:
            u.is_active = True
            u.password_hash = hash_password(DEMO_PASSWORD)
            print(f"ACTIVE {u.email} role={u.role}")
        # Ensure an administrator demo account for admin UI checks if missing
        admin = db.scalar(select(User).where(User.email == "admin@demo.com"))
        if admin is None:
            admin = User(
                name="Demo Administrator",
                email="admin@demo.com",
                password_hash=hash_password(DEMO_PASSWORD),
                role="ADMINISTRATOR",
                is_active=True,
            )
            db.add(admin)
            print("CREATE admin@demo.com role=ADMINISTRATOR")
        else:
            admin.is_active = True
            admin.password_hash = hash_password(DEMO_PASSWORD)
            admin.role = "ADMINISTRATOR"
            print("ACTIVE admin@demo.com role=ADMINISTRATOR")
        db.commit()
        print("DONE")
    finally:
        db.close()


if __name__ == "__main__":
    main()
