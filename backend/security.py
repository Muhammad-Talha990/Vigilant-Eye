import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from dotenv import load_dotenv

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET")
# Default 60 minutes. Production validates <= 60 via app_config.
# Demo/local may raise this via environment (e.g. 480).
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
JWT_ALGORITHM = "HS256"

if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET is missing from .env")


def hash_password(password: str) -> str:
    """Hash a plain password with bcrypt for safe storage."""
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Return True if plain_password matches the stored bcrypt hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        password_hash.encode("utf-8"),
    )


def create_access_token(*, user_id: int, email: str, role: str) -> str:
    """Create a signed JWT for the logged-in user."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT. Raises jwt exceptions on failure."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
