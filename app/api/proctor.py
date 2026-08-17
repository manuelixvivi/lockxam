from fastapi import APIRouter, Depends, status
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
        proctor_assignment_id=payload.proctor_assignment_id,
        exam_session_id=payload.exam_session_id,
        reason=payload.reason or "Device reset by proctor",
    )
