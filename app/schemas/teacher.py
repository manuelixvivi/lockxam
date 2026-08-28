from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.teacher.enums import PackageStatus, QuestionType


class QuestionPackageCreate(BaseModel):
    name: str = Field(..., max_length=255)
    class_level: str = Field(..., max_length=50)
    subject: str = Field(..., max_length=255)
    target_counts: dict[str, int] = Field(
        ...,
        description="Target kuantitas per jenis soal. Contoh: {'PG': 30, 'IS': 5}",
    )

    @field_validator("target_counts")
    @classmethod
    def validate_target_counts(cls, v):
        if not v:
            raise ValueError("Target counts tidak boleh kosong.")
        for k, count in v.items():
            try:
                QuestionType(k)
            except ValueError:
                raise ValueError(f"Jenis soal '{k}' tidak valid.") from None
            if count <= 0:
                raise ValueError("Jumlah target soal wajib bilangan bulat positif (> 0).")
        return v


class QuestionPackageResponse(BaseModel):
    id: int
    public_id: UUID
    school_id: int
    name: str
    class_level: str
    subject: str | None = None
    target_counts: dict[str, int]
    status: PackageStatus
    owner_teacher_account_id: int
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class QuestionCreateRequest(BaseModel):
    type: QuestionType
    content: str = Field(..., min_length=1)
    options: list[str] | None = None
    answer_key: str = Field(..., min_length=1)
    rubrics: list[dict] = []
    subject: str = Field(..., min_length=1)
    class_level: str | None = None
    ai_grading: bool = False


class QuestionUpdateRequest(BaseModel):
    content: str | None = None
    options: list[str] | None = None
    answer_key: str | None = None
    rubrics: list[dict] | None = None
    subject: str | None = None
    class_level: str | None = None
    ai_grading: bool | None = None


class TeacherQuestionResponse(BaseModel):
    id: int
    type: QuestionType
    content: str
    options: list[str] | None = None
    answer_key: str
    rubrics: list[dict]
    owner_teacher_account_id: int
    subject: str | None = None
    class_level: str | None = None
    ai_grading: bool = False
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class PackageQuestionResponse(BaseModel):
    id: int
    type: QuestionType
    content: str
    options: list[str] | None = None
    answer_key: str
    rubrics: list[dict]
    canonical_order: int
    score: float
    subject: str | None = None
    class_level: str | None = None
    ai_grading: bool = False
    created_at: datetime | None = None


class QuestionPackageDetailResponse(BaseModel):
    id: int
    school_id: int
    name: str
    class_level: str
    subject: str | None = None
    target_counts: dict[str, int]
    status: PackageStatus
    owner_teacher_account_id: int
    created_at: datetime | None = None
    questions: list[PackageQuestionResponse]


class QuestionResponse(BaseModel):
    """Schema output DTO publik untuk browser/client. Mengabaikan kunci jawaban & rubrik."""

    id: int
    type: QuestionType
    content: str
    options: list[str] | None

    class Config:
        from_attributes = True


class QuestionSnapshotPayload(BaseModel):
    """Schema internal khusus memuat kunci jawaban, rubrik, dan canonical_order (self-contained)."""

    id: int
    type: QuestionType
    content: str
    options: list[str] | None
    answer_key: str
    rubrics: list[dict]
    canonical_order: int

    class Config:
        from_attributes = True


class QuestionPackageSnapshotPayload(BaseModel):
    """Schema internal untuk pengiriman payload snapshot lintas domain."""

    package_id: int
    name: str
    class_level: str
    questions: list[QuestionSnapshotPayload]
