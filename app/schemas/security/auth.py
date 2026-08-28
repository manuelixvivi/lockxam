from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    role: str
    school_id: int | None
    must_change_password: bool
    session_expires_in: int | None = None


class CurrentUserResponse(BaseModel):
    user_id: int
    username: str
    role: str
    school_id: int | None
    school_name: str | None = None
    school_level_code: str | None = None
    must_change_password: bool = False
    name: str | None = None
    nis: str | None = None
    nisn: str | None = None
    birth_date: date | None = None
    gender: str | None = None
    class_name: str | None = None
    registered_year: int | None = None
    nip: str | None = None
    teacher_code: str | None = None
    subjects_taught: list[str] | None = None
    classes_taught: list[str] | None = None


class RefreshRequest(BaseModel):
    refresh_token: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    session_expires_in: int | None = None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class SessionResponse(BaseModel):
    session_id: str
    ip: str | None
    user_agent: str | None
    created_at: datetime
    last_activity_at: datetime
    is_current: bool

    model_config = ConfigDict(from_attributes=True)
