from sqlalchemy import select
from database import SessionLocal
from models.user import User

db = SessionLocal()
rows = db.scalars(select(User).where(User.email.like("%@demo.com"))).all()
print([(u.email, u.role, u.is_active) for u in rows])
db.close()
