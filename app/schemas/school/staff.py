from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StaffAccountResponse(BaseModel):
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
    nip: str | None = None
    teacher_code: str | None = None
    gender: str | None = None
    registered_year: int | None = None
    classes_taught: list[str] | None = None
    subjects_taught: list[str] | None = None


class TeacherCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    nip: str = Field(..., min_length=4, max_length=20, pattern=r"^[0-9]+$")
    teacher_code: str | None = Field(None, min_length=2, max_length=50)
    gender: str = Field(..., pattern=r"^(L|P)$")
    registered_year: int = Field(..., gt=1900, lt=2100)
    classes_taught: list[str] = Field(default_factory=list)
    # subjects_taught intentionally removed: competency is set via TeacherSubject only.
    # Any submitted value is silently ignored to maintain backward-compatibility.


class TeacherCreateResponse(BaseModel):
    account: StaffAccountResponse
    default_password: str


class TeacherUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    nip: str | None = Field(None, min_length=4, max_length=20, pattern=r"^[0-9]+$")
    teacher_code: str | None = Field(None, min_length=2, max_length=50)
    gender: str | None = Field(None, pattern=r"^(L|P)$")
    registered_year: int | None = Field(None, gt=1900, lt=2100)
    classes_taught: list[str] | None = None
    # subjects_taught intentionally removed: competency is managed via TeacherSubject only.
    # Submitting this field has no effect; rejected at service layer.
    is_active: bool | None = None


class ResetPasswordResponse(BaseModel):
    message: str
    username: str
    new_password: str


class TeacherImportItem(BaseModel):
    name: str
    nip: str | None = None
    teacher_code: str | None = None
    gender: str
    registered_year: int | None = None
    row_num: int | None = None


class TeacherImportRequest(BaseModel):
    teachers: list[TeacherImportItem]
