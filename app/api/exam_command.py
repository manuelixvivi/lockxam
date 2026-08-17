"""
Exam Command API — Internal endpoints consumed by Teacher/Proctor Domain.
Auth: X-Internal-Token header (tidak memakai JWT).

Boundary: Exam Domain adalah executor.
  - Validasi WHAT (attempt state machine).
  - WHO (otorisasi pengawas) sudah divalidasi di Teacher Domain sebelum panggilan ini.
"""

import os

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from starlette import status

from app.core.database import get_db
from app.schemas.exam.exam import (
    ExamAttemptResponse,
    ExamPackageSnapshotPayload,
    ProctorCommandRequest,
)
from app.services.exam.exam_service import ExamService

router = APIRouter(prefix="/api/v1/exam/commands", tags=["Exam — Internal Commands"])


def _validate_internal_token(x_internal_token: str | None = Header(default=None)) -> None:
    """Dependency: Pastikan caller adalah internal service yang telah diotorisasi."""
    expected = os.getenv("INTERNAL_SERVICE_TOKEN", "equigrade-internal-secret-token")
    if not expected or x_internal_token != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Internal-Token.")


# ─────────────────────────────────────────────────────────────────────────────
# POST /activate-session  (called by Session Scheduling Service)
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/activate-session",
    status_code=status.HTTP_200_OK,
)
def activate_exam_session(
    session_id: int,
    payload: ExamPackageSnapshotPayload,
    db: Session = Depends(get_db),
    _=Depends(_validate_internal_token),
):
    """UC-1: Aktifkan sesi ujian dan tanamkan snapshot paket soal."""
    return ExamService.activate_exam_session(db=db, session_id=session_id, snapshot_payload=payload)


# ─────────────────────────────────────────────────────────────────────────────
# POST /lock-student
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/lock-student",
    response_model=ExamAttemptResponse,
    status_code=status.HTTP_200_OK,
)
def proctor_lock_student(
    payload: ProctorCommandRequest,
    db: Session = Depends(get_db),
    _=Depends(_validate_internal_token),
):
    """UC-7a: Proctor mengunci siswa (PAUSED, countdown tetap jalan)."""
    return ExamService.proctor_lock_attempt(db=db, payload=payload)


# ─────────────────────────────────────────────────────────────────────────────
# POST /unlock-student
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/unlock-student",
    response_model=ExamAttemptResponse,
    status_code=status.HTTP_200_OK,
)
def proctor_unlock_student(
    payload: ProctorCommandRequest,
    db: Session = Depends(get_db),
    _=Depends(_validate_internal_token),
):
    """UC-7b: Proctor membuka kunci siswa (resume IN_PROGRESS)."""
    return ExamService.proctor_unlock_attempt(
        db=db, attempt_id=payload.attempt_id, exam_session_id=payload.exam_session_id
    )


# ─────────────────────────────────────────────────────────────────────────────
# POST /device-reset
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/device-reset",
    response_model=ExamAttemptResponse,
    status_code=status.HTTP_200_OK,
)
def proctor_device_reset(
    payload: ProctorCommandRequest,
    db: Session = Depends(get_db),
    _=Depends(_validate_internal_token),
):
    """UC-7c: Proctor mereset perangkat siswa (PAUSED, countdown berhenti, sisa detik tersimpan)."""
    return ExamService.proctor_reset_device(db=db, payload=payload)


# ─────────────────────────────────────────────────────────────────────────────
# POST /finalize-evaluation
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/finalize-evaluation",
    status_code=status.HTTP_200_OK,
)
def finalize_evaluation(
    evaluation_id: int,
    score: float,
    teacher_account_id: int,
    feedback: str | None = None,
    db: Session = Depends(get_db),
    _=Depends(_validate_internal_token),
):
    """UC-6: Guru menyelesaikan dan mengunci hasil penilaian essay."""
    return ExamService.finalize_evaluation(
        db=db,
        evaluation_id=evaluation_id,
        score=score,
        feedback=feedback,
        teacher_account_id=teacher_account_id,
    )
