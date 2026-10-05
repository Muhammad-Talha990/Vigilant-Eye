from pydantic import BaseModel, EmailStr, Field

from schemas.utc_datetime import UtcDateTime


class UserCreate(BaseModel):
    """JSON body the client sends when creating a user."""

    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    # Production minimum: 8 characters. Demo seed password Demo@123 satisfies this.
    password: str = Field(min_length=8, max_length=100)
    role: str = Field(min_length=1, max_length=50)


class UserOut(BaseModel):
    """JSON the API returns. Never includes the password."""

    id: int
    name: str
    email: str
    role: str
    is_active: bool
    created_at: UtcDateTime

    model_config = {"from_attributes": True}
