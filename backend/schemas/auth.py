from pydantic import BaseModel, EmailStr, Field

from schemas.user import UserOut


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class GoogleLoginRequest(BaseModel):
    """GIS / Google Sign-In ID token (credential JWT)."""

    id_token: str = Field(min_length=20, max_length=8192)


class AuthPublicConfig(BaseModel):
    """Safe public auth mode flags for the login page."""

    auth_mode: str
    password_login_enabled: bool
    google_auth_enabled: bool
    google_client_id: str | None = None
    demo_helpers_enabled: bool = False


class LoginResponse(BaseModel):
    message: str
    access_token: str
    token_type: str = "bearer"
    user: UserOut
