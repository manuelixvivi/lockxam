from datetime import date, datetime
from typing import Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class StudentAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    public_id: UUID
    username: str
    role: str
    is_active: bool
    last_login: datetime | None = None
    created_at: datetime

    # Profile fields
    name: str | None = None
    nis: str | None = None
    nisn: str | None = None
    birth_date: date | None = None
    gender: str | None = None
    class_name: str | None = None
    registered_year: int | None = None


class StudentCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    nisn: str = Field(..., min_length=4, max_length=20, pattern=r"^[0-9]+$")
    nis: str | None = Field(None, max_length=20, pattern=r"^[0-9]*$")
    gender: str = Field(..., pattern=r"^[LP]$")
    birth_date: date | None = None
    class_name: str | None = None
    registered_year: int | None = None


class StudentCreateResponse(BaseModel):
    account: StudentAccountResponse
    default_password: str


class StudentUpdateRequest(BaseModel):
    is_active: bool | None = None
    name: str | None = None
    nisn: str | None = Field(None, min_length=4, max_length=20, pattern=r"^[0-9]+$")
    nis: str | None = Field(None, max_length=20, pattern=r"^[0-9]*$")
    birth_date: date | None = None
    gender: str | None = Field(None, pattern=r"^[LP]$")
    class_name: str | None = None
    registered_year: int | None = None


class StudentResetPasswordResponse(BaseModel):
    message: str
    username: str
    new_password: str


class StudentImportRow(BaseModel):
    name: str | None = None
    nisn: str | None = None
    nis: str | None = None
    gender: str | None = None
    birth_date: Any | None = None
    class_name: str | None = None
    registered_year: Any | None = None


class StudentBulkImportRequest(BaseModel):
    academic_year_id: int
    rows: list[StudentImportRow]

