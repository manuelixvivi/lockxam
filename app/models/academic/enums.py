from enum import Enum


class AcademicStatus(str, Enum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    PENDING_ARCHIVE = "PENDING_ARCHIVE"
    ARCHIVED = "ARCHIVED"


class EnrollmentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    TRANSFERRED = "TRANSFERRED"
    COMPLETED = "COMPLETED"
    DROPPED = "DROPPED"


class ExamScheduleStatus(str, Enum):
    DRAFT = "DRAFT"
    READY = "READY"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
