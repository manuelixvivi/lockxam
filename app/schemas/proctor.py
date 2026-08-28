from datetime import datetime

from pydantic import BaseModel, Field

from app.models.teacher.enums import AttendanceStatus, BAUStatus, ProctorEventType


class ProctorEventCreate(BaseModel):
    student_id: int
    event_type: ProctorEventType
    reason: str = Field(..., max_length=1000)
    action_taken: str = Field(..., max_length=255)


class ProctorEventResponse(BaseModel):
    id: int
    proctor_assignment_id: int
    student_id: int
    event_type: ProctorEventType
    timestamp: datetime
    reason: str
    proctor_id: int
    action_taken: str

    class Config:
        from_attributes = True


class BAUAttendanceUpdate(BaseModel):
    student_id: int
    attendance_status: AttendanceStatus
    reason: str | None = Field(None, max_length=255)


class BAUSubmitRequest(BaseModel):
    proctor_notes: str | None = Field(None, max_length=2000)


class BAUAttendanceResponse(BaseModel):
    id: int
    student_id: int
    attendance_status: AttendanceStatus
    reason: str | None

    class Config:
        from_attributes = True


class BAUDocumentResponse(BaseModel):
    id: int
    proctor_assignment_id: int
    status: BAUStatus
    proctor_notes: str | None
    submitted_at: datetime | None
    attendances: list[BAUAttendanceResponse]

    class Config:
        from_attributes = True


class ProctorCommandRequest(BaseModel):
    attempt_id: int
    student_id: int | None = None
    proctor_assignment_id: int
    actor_teacher_id: int | None = None
    exam_session_id: int
    reason: str | None = Field(None, max_length=500)
