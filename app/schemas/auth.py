from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str
    school_id: int | None


class CurrentUserResponse(BaseModel):
    user_id: int
    username: str
    role: str
    school_id: int | None


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class SessionResponse(BaseModel):
    session_id: str
    ip: str | None
    user_agent: str | None
    created_at: datetime
    last_activity_at: datetime
    is_current: bool

    model_config = ConfigDict(from_attributes=True)
