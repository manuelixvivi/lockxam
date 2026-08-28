from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import require_role
from app.models.security.enums import UserRole
from app.schemas.proctor import (
    BAUAttendanceResponse,
    BAUAttendanceUpdate,
    BAUDocumentResponse,
    BAUSubmitRequest,
    ProctorCommandRequest,
    ProctorEventCreate,
    ProctorEventResponse,
)
from app.services.teacher.proctor_service import ProctorService

router = APIRouter(prefix="/api/v1/proctor", tags=["Proctoring & Live Exam"])


@router.post(
    "/assignments/{proctor_assignment_id}/events",
    response_model=ProctorEventResponse,
    status_code=status.HTTP_201_CREATED,
)
def log_proctor_event(
    proctor_assignment_id: int,
    payload: ProctorEventCreate,
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    proctor_id = int(current_user["sub"])
    return ProctorService.log_proctor_event(
        db=db,
        proctor_assignment_id=proctor_assignment_id,
        student_id=payload.student_id,
        event_type=payload.event_type,
        reason=payload.reason,
        proctor_id=proctor_id,
        action_taken=payload.action_taken,
    )


@router.get(
    "/assignments/{proctor_assignment_id}/bau",
    response_model=BAUDocumentResponse,
)
@router.post(
    "/assignments/{proctor_assignment_id}/bau",
    response_model=BAUDocumentResponse,
)
def get_or_create_bau(
    proctor_assignment_id: int,
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    return ProctorService.get_or_create_bau(db, proctor_assignment_id)


@router.put(
    "/bau/{bau_document_id}/attendance",
    response_model=BAUAttendanceResponse,
)
def update_attendance(
    bau_document_id: int,
    payload: BAUAttendanceUpdate,
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    return ProctorService.update_attendance(
        db=db,
        bau_document_id=bau_document_id,
        student_id=payload.student_id,
        status=payload.attendance_status,
        reason=payload.reason,
    )


@router.post(
    "/bau/{bau_document_id}/submit",
    response_model=BAUDocumentResponse,
)
def submit_bau(
    bau_document_id: int,
    payload: BAUSubmitRequest,
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    return ProctorService.submit_bau(
        db=db,
        bau_document_id=bau_document_id,
        proctor_notes=payload.proctor_notes,
    )


@router.post(
    "/bau/{bau_document_id}/request-correction",
    response_model=BAUDocumentResponse,
)
def request_correction(
    bau_document_id: int,
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    return ProctorService.request_correction(db, bau_document_id)


@router.post(
    "/bau/{bau_document_id}/resolve-correction",
    response_model=BAUDocumentResponse,
)
def resolve_correction(
    bau_document_id: int,
    approve: bool,
    current_user=Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return ProctorService.resolve_correction(db, bau_document_id, approve)


@router.post("/commands/lock", status_code=status.HTTP_200_OK)
def proctor_lock_student(
    payload: ProctorCommandRequest,
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    proctor_id = int(current_user["sub"])
    return ProctorService.dispatch_internal_proctor_command(
        db=db,
        endpoint="lock-student",
        proctor_id=proctor_id,
        attempt_id=payload.attempt_id,
        student_id=payload.student_id,
        proctor_assignment_id=payload.proctor_assignment_id,
        exam_session_id=payload.exam_session_id,
        reason=payload.reason or "Locked by proctor",
    )


@router.post("/commands/unlock", status_code=status.HTTP_200_OK)
def proctor_unlock_student(
    payload: ProctorCommandRequest,
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    proctor_id = int(current_user["sub"])
    return ProctorService.dispatch_internal_proctor_command(
        db=db,
        endpoint="unlock-student",
        proctor_id=proctor_id,
        attempt_id=payload.attempt_id,
        student_id=payload.student_id,
        proctor_assignment_id=payload.proctor_assignment_id,
        exam_session_id=payload.exam_session_id,
        reason="",
    )


@router.post("/commands/device-reset", status_code=status.HTTP_200_OK)
def proctor_device_reset(
    payload: ProctorCommandRequest,
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    proctor_id = int(current_user["sub"])
    return ProctorService.dispatch_internal_proctor_command(
        db=db,
        endpoint="device-reset",
        proctor_id=proctor_id,
        attempt_id=payload.attempt_id,
        student_id=payload.student_id,
        proctor_assignment_id=payload.proctor_assignment_id,
        exam_session_id=payload.exam_session_id,
        reason=payload.reason or "Device reset by proctor",
    )


class BroadcastCommandRequest(BaseModel):
    exam_session_id: int
    message: str | None = None
    extra_minutes: int | None = None


@router.post("/commands/broadcast", status_code=status.HTTP_200_OK)
def send_proctor_broadcast(
    payload: BroadcastCommandRequest,
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    """Pengawas mengumumkan pengumuman darurat atau menambah waktu ke seluruh siswa (Ter-persitasi di DB)."""
    from datetime import datetime, timedelta, timezone
    from app.models.teacher.proctor_event import ProctorAuditEvent

    sess_id = payload.exam_session_id
    proctor_id = int(current_user["sub"])

    if payload.message:
        evt = ProctorAuditEvent(
            proctor_assignment_id=sess_id,
            student_id=0,  # 0 indicates broadcast to all students
            event_type="ANNOUNCEMENT",
            reason=payload.message,
            proctor_id=proctor_id,
            action_taken="BROADCAST",
        )
        db.add(evt)

    if payload.extra_minutes and payload.extra_minutes > 0:
        from app.models.exam.enums import ExamAttemptStatus
        from app.models.exam.exam_attempt import ExamAttempt

        attempts = (
            db.query(ExamAttempt)
            .filter(
                ExamAttempt.exam_session_id == sess_id,
                ExamAttempt.status.in_([ExamAttemptStatus.IN_PROGRESS, ExamAttemptStatus.PAUSED]),
            )
            .all()
        )

        for a in attempts:
            if a.deadline_at:
                a.deadline_at = a.deadline_at + timedelta(minutes=payload.extra_minutes)
            if a.remaining_seconds is not None:
                a.remaining_seconds += payload.extra_minutes * 60

        evt = ProctorAuditEvent(
            proctor_assignment_id=sess_id,
            student_id=0,
            event_type="EXTRA_TIME",
            reason=f"⏱️ Pengawas menambahkan waktu ujian sebesar +{payload.extra_minutes} Menit!",
            proctor_id=proctor_id,
            action_taken="EXTRA_TIME_ADDED",
        )
        db.add(evt)

    db.commit()
    return {
        "status": "SUCCESS",
        "message": "Broadcast pengumuman dan penambahan waktu berhasil dikirim dan tersimpan di database!",
    }
