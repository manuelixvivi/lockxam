from enum import Enum


class PackageStatus(str, Enum):
    INCOMPLETE = "INCOMPLETE"
    READY = "READY"


class QuestionType(str, Enum):
    PG = "PG"  # Pilihan Ganda
    IS = "IS"  # Isian Singkat
    ES = "ES"  # Essay / Uraian


class ProctorEventType(str, Enum):
    VIOLATION_DETECTED = "VIOLATION_DETECTED"
    STUDENT_LOCKED = "STUDENT_LOCKED"
    STUDENT_UNLOCKED = "STUDENT_UNLOCKED"
    DEVICE_RESET = "DEVICE_RESET"


class BAUStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    CORRECTION_REQUESTED = "CORRECTION_REQUESTED"


class AttendanceStatus(str, Enum):
    HADIR = "HADIR"
    IZIN = "IZIN"
    SAKIT = "SAKIT"
    ALPA = "ALPA"
