from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ── 1. Subject Schemas ──


class SubjectCreateRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=50, examples=["MAT-10"])
    name: str = Field(..., min_length=1, max_length=200, examples=["Matematika Wajib"])
    description: str | None = Field(None, max_length=500)


class SubjectUpdateRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=500)
    is_active: bool = True


class SubjectResponse(BaseModel):
    id: int
    public_id: UUID
    school_id: int
    code: str
    name: str
    description: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── 2. Teacher Competency & Candidate Schemas ──


class TeacherCandidateResponse(BaseModel):
    teacher_id: int
    public_id: UUID
    name: str
    username: str
    nip: str | None = None
    is_active: bool
    status: str = "ACTIVE"

    model_config = ConfigDict(from_attributes=True)


class TeacherCompetencyAssignRequest(BaseModel):
    teacher_id: int
    subject_id: int


class TeacherSubjectResponse(BaseModel):
    id: int
    school_id: int
    teacher_id: int
    subject_id: int
    created_at: datetime
    teacher_name: str | None = None
    teacher_username: str | None = None
    subject_code: str | None = None
    subject_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


# ── 3. Class Schemas ──


class ClassCreateRequest(BaseModel):
    academic_year_id: int
    name: str = Field(..., min_length=1, max_length=100, examples=["X MIPA 1"])
    grade_level: str | None = Field(None, max_length=50, examples=["10"])


class ClassUpdateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    grade_level: str | None = Field(None, max_length=50)
    is_active: bool = True


class ClassResponse(BaseModel):
    id: int
    public_id: UUID
    school_id: int
    academic_year_id: int
    name: str
    grade_level: str | None = None
    is_active: bool
    student_count: int = 0
    subject_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── 4. Student Enrollment Schemas ──


class StudentEnrollmentRequest(BaseModel):
    student_id: int


class StudentEnrollmentResponse(BaseModel):
    id: int
    public_id: UUID
    school_id: int
    student_id: int
    class_id: int
    academic_year_id: int
    status: str
    start_date: datetime
    end_date: datetime | None = None
    student_name: str | None = None
    student_username: str | None = None
    nisn: str | None = None
    nis: str | None = None
    class_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


# ── 5. Class ↔ Subject & Teacher Assignment Schemas ──


class ClassSubjectAssignRequest(BaseModel):
    subject_id: int


class ClassSubjectResponse(BaseModel):
    id: int
    school_id: int
    class_id: int
    subject_id: int
    created_at: datetime
    subject_code: str | None = None
    subject_name: str | None = None
    teacher_id: int | None = None
    teacher_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


# ── 6. Bulk & Import Schemas ──


class StudentBulkEnrollRequest(BaseModel):
    student_ids: list[int]


class StudentBulkRemoveRequest(BaseModel):
    student_ids: list[int]


class ClassSubjectBulkAssignRequest(BaseModel):
    subject_ids: list[int]


class ClassSubjectBulkRemoveRequest(BaseModel):
    subject_ids: list[int]


class SubjectBulkDeleteRequest(BaseModel):
    subject_ids: list[int]


class SubjectBulkDeactivateRequest(BaseModel):
    subject_ids: list[int]


class ClassFullImportItem(BaseModel):
    name: str
    grade_level: str | None = None
    students: list[dict] = Field(default_factory=list)
    subjects: list[dict] = Field(default_factory=list)


class ClassFullImportRequest(BaseModel):
    academic_year_id: int
    classes: list[ClassFullImportItem]


class ClassSubjectTeacherAssignRequest(BaseModel):
    teacher_id: int


class ClassSubjectTeacherResponse(BaseModel):
    id: int
    school_id: int
    class_id: int
    subject_id: int
    teacher_id: int
    created_at: datetime
    teacher_name: str | None = None
    teacher_username: str | None = None
    teacher_nip: str | None = None
    subject_name: str | None = None
    class_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


# ── 6. Exam Schedule Schemas ──


class ExamSchedulePackageCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    academic_year_id: int


class ExamScheduleCreateRequest(BaseModel):
    package_id: int | None = None
    academic_year_id: int
    academic_semester_id: int
    class_id: int
    subject_id: int
    title: str | None = Field(None, max_length=200)
    name: str | None = Field(None, max_length=200)
    start_time: datetime
    end_time: datetime
    duration_minutes: int = Field(..., gt=0)
    proctor_id: int | None = None
    target_type: str = "ALL_CLASS"
    allowed_student_ids: list[int] | None = None
    lock_browser: bool = True
    eyd_language_evaluation: bool = False
    randomize_per_type: bool = True


class ExamScheduleUpdateRequest(BaseModel):
    academic_semester_id: int | None = None
    class_id: int | None = None
    subject_id: int | None = None
    title: str | None = Field(None, max_length=200)
    name: str | None = Field(None, max_length=200)
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration_minutes: int | None = Field(None, gt=0)
    proctor_id: int | None = None
    status: str | None = None
    target_type: str | None = None
    allowed_student_ids: list[int] | None = None
    lock_browser: bool | None = None
    eyd_language_evaluation: bool | None = None
    randomize_per_type: bool | None = None


class ExamScheduleProctorAssignRequest(BaseModel):
    proctor_id: int | None = None


class ExamScheduleResponse(BaseModel):
    id: int
    public_id: UUID
    school_id: int
    package_id: int | None = None
    academic_year_id: int
    academic_semester_id: int
    class_id: int
    subject_id: int
    teacher_id: int
    proctor_id: int | None = None
    title: str
    name: str | None = None
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    status: str
    lock_browser: bool = True
    eyd_language_evaluation: bool = False
    randomize_per_type: bool = True
    target_type: str = "ALL_CLASS"
    allowed_student_ids: list[int] | None = None
    created_at: datetime
    updated_at: datetime
    class_name: str | None = None
    subject_name: str | None = None
    teacher_name: str | None = None
    proctor_name: str | None = None
    proctor_code: str | None = None
    academic_year_name: str | None = None
    academic_semester_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ExamSchedulePackageResponse(BaseModel):
    id: int
    public_id: UUID
    school_id: int
    academic_year_id: int
    title: str
    is_closed: bool = False
    created_at: datetime
    updated_at: datetime
    academic_year_name: str | None = None
    schedules: list[ExamScheduleResponse] = []

    model_config = ConfigDict(from_attributes=True)


class SubjectImportItem(BaseModel):
    code: str
    name: str
    description: str | None = None
    row_num: int | None = None


class SubjectImportRequest(BaseModel):
    subjects: list[SubjectImportItem]


# Batch 3 Bulk Import Remediation Verified

