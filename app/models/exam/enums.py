from enum import Enum


class ExamSessionStatus(str, Enum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"


class ExamAttemptStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    PAUSED = "PAUSED"
    SUBMITTED = "SUBMITTED"
    GRADING = "GRADING"
    GRADED = "GRADED"


class DeviceSessionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"
    INVALIDATED = "INVALIDATED"


class GradingStatus(str, Enum):
    AI_PENDING = "AI_PENDING"
    AUTO_GRADED = "AUTO_GRADED"
    AI_DRAFT = "AI_DRAFT"
    TEACHER_REVIEWED = "TEACHER_REVIEWED"
    FINALIZED = "FINALIZED"


class GradingSource(str, Enum):
    SYSTEM = "SYSTEM"
    AI = "AI"
    TEACHER = "TEACHER"
