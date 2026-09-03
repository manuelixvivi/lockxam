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
    TIME_ENDED = "TIME_ENDED"
    LOCKED = "LOCKED"
    GRADING = "GRADING"
    GRADED = "GRADED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class GradingRunStatus(str, Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
