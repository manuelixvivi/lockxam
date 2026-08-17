from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AcademicYearCreateRequest(BaseModel):
    name: str = Field(..., max_length=50, examples=["2025/2026"])
    start_date: datetime
    end_date: datetime


class AcademicSemesterCreateRequest(BaseModel):
    academic_year_id: int
    code: str = Field(..., description="Must be ODD or EVEN")
    display_name: str = Field(..., max_length=100, examples=["Ganjil"])


class AcademicSemesterResponse(BaseModel):
    id: int
    public_id: UUID
    academic_year_id: int
    code: str
    display_name: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AcademicYearResponse(BaseModel):
    id: int
    public_id: UUID
    school_id: int
    name: str
    start_date: datetime
    end_date: datetime
    status: str
    semesters: list[AcademicSemesterResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
