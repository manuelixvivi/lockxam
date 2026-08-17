import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class SchoolCreateRequest(BaseModel):
    npsn: str = Field(..., min_length=8, max_length=20)
    name: str = Field(..., min_length=3, max_length=255)
    domain: str = Field(..., min_length=3, max_length=100, pattern=r'^[a-zA-Z0-9.-]+$')
    school_level_id: int
    initial_subscription_preset: str = "ONE_MONTH"
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    logo_url: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if v is not None:
            v = v.strip()
            if not re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", v):
                raise ValueError("Invalid email format")
        return v


class SchoolUpdateRequest(BaseModel):
    npsn: str | None = None
    code: str | None = None
    name: str | None = None
    domain: str | None = None
    school_level_id: int | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    logo_url: str | None = None
    is_active: bool | None = None
    status: str | None = None


    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if v is not None:
            v = v.strip()
            if not re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", v):
                raise ValueError("Invalid email format")
        return v


class SchoolSettingResponse(BaseModel):
    timezone: str
    language: str

    class Config:
        from_attributes = True


class SchoolResponse(BaseModel):
    id: int
    public_id: UUID
    npsn: str
    code: str
    name: str
    domain: str | None = None
    school_level_id: int
    address: str | None
    phone: str | None
    email: str | None
    website: str | None
    logo_url: str | None
    is_active: bool
    status: str
    created_at: datetime
    updated_at: datetime
    admin_username: str | None = None
    subscription_status: str | None = None
    subscription_end_date: datetime | None = None
    registered_students_count: int = 0
    settings: SchoolSettingResponse | None = None

    class Config:
        from_attributes = True


