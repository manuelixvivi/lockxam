"""
Exam API â€” Student-facing endpoints.
Auth: Siswa (STUDENT role).
"""

import hashlib
import os
import random
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette import status

from app.core.database import get_db
from app.core.rbac import require_role
from app.models.security.enums import UserRole
from app.schemas.exam.exam import (
    AICallbackRequest,
    ExamAttemptResponse,
    StudentAnswerResponse,
)
from app.services.exam.exam_service import ExamService

router = APIRouter(prefix="/api/v1/exam", tags=["Exam — Student"])

# Storage Telemetry Real-time & Broadcast Messages
TELEMETRY_STORE: dict[int, dict] = {}
BROADCAST_STORE: dict[int, list[dict]] = {}


class TelemetryPayload(BaseModel):
    battery_level: int | None = None
    is_charging: bool | None = None
    ping_ms: int | None = None
    is_offline: bool | None = None
    violation_type: str | None = None
    violation_reason: str | None = None


@router.post("/attempts/{attempt_id}/telemetry", status_code=status.HTTP_200_OK)
def update_attempt_telemetry(
    attempt_id: int,
    payload: TelemetryPayload,
    current_user=Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Siswa mengirimkan data telemetry HP (baterai, ping, sinyal, dan event kecurangan/split-screen)."""
    student_id = int(current_user["sub"])
    from app.models.exam.enums import ExamAttemptStatus
    from app.models.exam.exam_attempt import ExamAttempt

    attempt = (
        db.query(ExamAttempt)
        .filter(ExamAttempt.id == attempt_id, ExamAttempt.student_id == student_id)
        .first()
    )

    if not attempt:
        raise HTTPException(status_code=404, detail="Exam attempt not found")

    TELEMETRY_STORE[attempt_id] = {
        "battery_level": payload.battery_level,
        "is_charging": payload.is_charging,
        "ping_ms": payload.ping_ms,
        "is_offline": payload.is_offline,
        "violation_type": payload.violation_type,
        "violation_reason": payload.violation_reason,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    if payload.violation_type in ["SPLIT_SCREEN", "APP_SWITCH", "UNPINNED"]:
        attempt.status = ExamAttemptStatus.PAUSED
        db.commit()
        return {
            "status": "LOCKED",
            "requires_qr_rescan": True,
            "message": f"Ujian dikunci karena terdeteksi {payload.violation_type}. Minta pengawas scan QR pembuka kunci.",
        }

    return {"status": "OK", "requires_qr_rescan": False}


@router.get("/sessions/{session_id}/broadcasts", status_code=status.HTTP_200_OK)
def get_session_broadcasts(
    session_id: int,
    current_user=Depends(require_role(UserRole.STUDENT)),
):
    """Mendapatkan pengumuman darurat / broadcast dari pengawas untuk sesi ujian ini."""
    broadcasts = BROADCAST_STORE.get(session_id, [])
    return {"broadcasts": broadcasts}


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# GET /my-schedules
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@router.get("/my-schedules", status_code=status.HTTP_200_OK)
def list_my_schedules(
    current_user=Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Mendapatkan daftar jadwal ujian aktif yang dapat diikuti oleh siswa."""
    student_id = int(current_user["sub"])
    school_id = current_user.get("school_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="User account is not bound to a school tenant")

    from datetime import datetime, timezone

    from app.models.academic.exam_schedule import ExamSchedule
    from app.models.academic.student_class_enrollment import StudentClassEnrollment
    from app.models.exam.enums import ExamSessionStatus
    from app.models.exam.exam_attempt import ExamAttempt
    from app.models.exam.exam_checkin import ExamCheckin
    from app.models.exam.exam_session import ExamSession
    from app.repositories.academic.subject_repository import subject_repository
    from app.utils.timezone import ensure_wib

    enrollments = (
        db.query(StudentClassEnrollment)
        .filter(
            StudentClassEnrollment.student_id == student_id,
            StudentClassEnrollment.status == "ACTIVE",
        )
        .all()
    )
    if not enrollments:
        return []

    class_ids = [e.class_id for e in enrollments]

    # 1. Active class schedules
    active_schedules = (
        db.query(ExamSchedule)
        .filter(
            ExamSchedule.school_id == school_id,
            ExamSchedule.class_id.in_(class_ids),
            ExamSchedule.status.in_(["READY", "ACTIVE"]),
        )
        .all()
    )

    # 2. Preserve historical schedules where student has attempt or check-in (jejak histori akademik)
    my_attempts = db.query(ExamAttempt).filter(ExamAttempt.student_id == student_id).all()
    attempt_session_ids = [a.exam_session_id for a in my_attempts]

    historical_schedule_ids = []
    if attempt_session_ids:
        attempt_sessions = (
            db.query(ExamSession).filter(ExamSession.id.in_(attempt_session_ids)).all()
        )
        historical_schedule_ids.extend([se.schedule_id for se in attempt_sessions])

    my_checkins = db.query(ExamCheckin).filter(ExamCheckin.student_id == student_id).all()
    if my_checkins:
        historical_schedule_ids.extend([c.schedule_id for c in my_checkins])

    historical_schedules = []
    if historical_schedule_ids:
        historical_schedules = (
            db.query(ExamSchedule)
            .filter(ExamSchedule.id.in_(list(set(historical_schedule_ids))))
            .all()
        )

    schedule_dict = {s.id: s for s in active_schedules + historical_schedules}
    schedules = sorted(schedule_dict.values(), key=lambda s: s.start_time)

    res = []
    now_wib = ensure_wib(datetime.now(timezone.utc))

    for s in schedules:
        subj = subject_repository.get_by_id(db, s.subject_id)
        session = db.query(ExamSession).filter(ExamSession.schedule_id == s.id).first()

        if not session and s.status in ["READY", "ACTIVE"]:
            start_wib = ensure_wib(s.start_time)
            sess_status = (
                ExamSessionStatus.ACTIVE if now_wib >= start_wib else ExamSessionStatus.PLANNED
            )
            session = ExamSession(
                schedule_id=s.id,
                package_id=s.package_id or 0,
                scheduled_start_at=s.start_time,
                scheduled_end_at=s.end_time,
                duration_minutes=s.duration_minutes,
                status=sess_status,
            )
            db.add(session)
            db.commit()
            db.refresh(session)

        attempt = None
        if session:
            attempt = (
                db.query(ExamAttempt)
                .filter(
                    ExamAttempt.exam_session_id == session.id, ExamAttempt.student_id == student_id
                )
                .first()
            )

        # Cek apakah siswa sudah checkin QR untuk jadwal ini
        checkin = (
            db.query(ExamCheckin)
            .filter(
                ExamCheckin.schedule_id == s.id,
                ExamCheckin.student_id == student_id,
            )
            .first()
        )

        res.append(
            {
                "schedule_id": s.id,
                "session_id": session.id if session else None,
                "title": s.title,
                "subject_id": s.subject_id,
                "subject_name": subj.name if subj else None,
                "class_id": s.class_id,
                "start_time": s.start_time,
                "end_time": s.end_time,
                "duration_minutes": s.duration_minutes,
                "lock_browser": s.lock_browser,
                "eyd_language_evaluation": s.eyd_language_evaluation,
                "randomize_per_type": s.randomize_per_type,
                "status": s.status,
                "attempt_id": attempt.id if attempt else None,
                "attempt_status": attempt.status.value if attempt else "NOT_STARTED",
                "attempt_remaining_seconds": attempt.remaining_seconds if attempt else None,
                "final_score": attempt.final_score if attempt else None,
                "has_checked_in": checkin is not None,
                "checked_in_at": checkin.checked_in_at.isoformat() if checkin else None,
            }
        )

    return res


@router.get("/class-leaderboard", status_code=status.HTTP_200_OK)
def get_class_leaderboard(
    current_user=Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Mendapatkan Leaderboard Nilai Rata-rata Ujian untuk Siswa di Kelas yang Sama."""
    student_id = int(current_user["sub"])
    school_id = current_user.get("school_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="User account is not bound to a school tenant")

    from sqlalchemy import func

    from app.models.academic.student_class_enrollment import StudentClassEnrollment
    from app.models.exam.enums import ExamAttemptStatus
    from app.models.exam.exam_attempt import ExamAttempt
    from app.models.security.auth_account import AuthAccount

    # Get student active enrollment class
    enrollment = (
        db.query(StudentClassEnrollment)
        .filter(
            StudentClassEnrollment.student_id == student_id,
            StudentClassEnrollment.status == "ACTIVE",
        )
        .first()
    )

    if not enrollment:
        return {"rank_self": None, "leaderboard": []}

    class_id = enrollment.class_id

    # Get all active student IDs in this class
    class_students = (
        db.query(StudentClassEnrollment)
        .filter(
            StudentClassEnrollment.class_id == class_id, StudentClassEnrollment.status == "ACTIVE"
        )
        .all()
    )
    student_ids = [cs.student_id for cs in class_students]

    # Calculate average final_score for each student in this class
    results = (
        db.query(
            ExamAttempt.student_id,
            func.avg(ExamAttempt.final_score).label("avg_score"),
            func.count(ExamAttempt.id).label("total_exams"),
        )
        .filter(
            ExamAttempt.student_id.in_(student_ids),
            ExamAttempt.status.in_(
                [ExamAttemptStatus.GRADED, ExamAttemptStatus.SUBMITTED, "GRADED", "SUBMITTED"]
            ),
            ExamAttempt.final_score.isnot(None),
        )
        .group_by(ExamAttempt.student_id)
        .order_by(func.avg(ExamAttempt.final_score).desc())
        .all()
    )

    # Map student names
    accounts = db.query(AuthAccount).filter(AuthAccount.id.in_(student_ids)).all()
    account_map = {a.id: a for a in accounts}

    leaderboard = []
    rank_self = None

    for idx, (s_id, avg_sc, tot_ex) in enumerate(results):
        acc = account_map.get(s_id)
        name = acc.name or acc.username if acc else f"Siswa #{s_id}"
        avg_val = round(float(avg_sc or 0.0), 1)
        rank = idx + 1
        is_me = s_id == student_id

        if is_me:
            rank_self = rank

        leaderboard.append(
            {
                "rank": rank,
                "student_id": s_id,
                "student_name": name,
                "avatar_initial": name[0].upper() if name else "S",
                "avg_score": avg_val,
                "total_exams": tot_ex,
                "is_self": is_me,
            }
        )

    return {
        "rank_self": rank_self,
        "total_class_students": len(student_ids),
        "leaderboard": leaderboard[:10],
    }


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# GET /schedules/{schedule_id}/qr-token  â€” Pengawas generate token QR absen
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@router.get(
    "/schedules/{schedule_id}/qr-token",
    status_code=status.HTTP_200_OK,
)
def get_qr_checkin_token(
    schedule_id: int,
    current_user=Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    """Pengawas mengambil token QR absen untuk suatu jadwal ujian.
    Token berlaku 10 menit dan di-sign dengan HMAC-SHA256."""
    import hmac
    import time

    from app.models.academic.exam_schedule import ExamSchedule

    schedule = db.get(ExamSchedule, schedule_id)
    title = f"Jadwal Ujian #{schedule_id}"
    if schedule:
        title = getattr(schedule, "title", getattr(schedule, "name", f"Jadwal Ujian #{schedule_id}"))

    # Token: base64url( schedule_id | expires_ts | hmac )
    secret = os.environ.get("SECRET_KEY", "equigrade-secret")
    expires_ts = int(time.time()) + 600  # 10 menit
    payload_str = f"{schedule_id}:{expires_ts}"
    sig = hmac.new(secret.encode(), payload_str.encode(), hashlib.sha256).hexdigest()[:16]
    token = f"{schedule_id}:{expires_ts}:{sig}"

    return {
        "schedule_id": schedule_id,
        "schedule_title": title,
        "token": token,
        "qr_token": token,
        "expires_in_seconds": 600,
    }


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# POST /checkin  â€” Siswa scan QR absen, merekam device fingerprint
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@router.post("/checkin", status_code=status.HTTP_200_OK)
def student_checkin(
    request: Request,
    current_user=Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Siswa melakukan absensi dengan scan QR dari pengawas.
    Endpoint ini:
    1. Memvalidasi token QR (sudah di-sign & belum expired)
    2. Merekam device_id siswa ke tabel exam_checkins (upsert)
    3. Mengembalikan info jadwal agar siswa bisa menunggu jam ujian
    """
    import hmac
    import time

    from app.models.academic.exam_schedule import ExamSchedule
    from app.models.exam.exam_checkin import ExamCheckin

    body = request.json() if hasattr(request, "json") else {}
    # FastAPI endpoint menerima JSON body â€” gunakan Pydantic inline

    # Baca body secara sinkron (endpoint ini sync)
    body_bytes = b""
    # Body sudah di-cache oleh Starlette â€” akses via scope
    # Kita gunakan query param karena ini lebih aman di sync handler
    token: str = request.query_params.get("token", "")
    device_id: str = request.headers.get("X-Device-Id", "unknown")

    if not token:
        raise HTTPException(status_code=422, detail="Token QR wajib disertakan.")

    # Validasi token
    secret = os.environ.get("SECRET_KEY", "equigrade-secret")
    try:
        parts = token.split(":")
        if len(parts) != 3:
            raise ValueError()
        schedule_id_str, expires_ts_str, sig_received = parts
        schedule_id = int(schedule_id_str)
        expires_ts = int(expires_ts_str)
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail="Format token QR tidak valid.")

    # Cek expiry
    if int(time.time()) > expires_ts:
        raise HTTPException(
            status_code=400, detail="Token QR sudah kadaluarsa. Minta pengawas generate ulang."
        )

    # Cek HMAC signature
    payload_str = f"{schedule_id}:{expires_ts}"
    sig_expected = hmac.new(secret.encode(), payload_str.encode(), hashlib.sha256).hexdigest()[:16]
    if not hmac.compare_digest(sig_received, sig_expected):
        raise HTTPException(status_code=400, detail="Token QR tidak valid atau telah dimodifikasi.")

    # Cek jadwal ada
    schedule = db.get(ExamSchedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Jadwal ujian tidak ditemukan.")

    student_id = int(current_user["sub"])

    # Upsert ExamCheckin
    try:
        checkin = (
            db.query(ExamCheckin)
            .filter(
                ExamCheckin.schedule_id == schedule_id,
                ExamCheckin.student_id == student_id,
            )
            .first()
        )

        if checkin:
            # Update device_id jika berbeda (rebind pre-exam)
            checkin.device_id = device_id
            checkin.ip_address = request.client.host if request.client else None
        else:
            from datetime import datetime, timezone

            checkin = ExamCheckin(
                schedule_id=schedule_id,
                student_id=student_id,
                device_id=device_id,
                ip_address=request.client.host if request.client else None,
                checked_in_at=datetime.now(timezone.utc),
            )
            db.add(checkin)

        db.commit()
        db.refresh(checkin)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal menyimpan data absensi: {str(e)}")

    return {
        "success": True,
        "message": "Absensi berhasil! Kamu terdaftar untuk ujian ini.",
        "schedule_id": schedule_id,
        "schedule_title": schedule.title if hasattr(schedule, "title") else schedule.name,
        "start_time": schedule.start_time.isoformat() if schedule.start_time else None,
        "end_time": schedule.end_time.isoformat() if schedule.end_time else None,
        "checked_in_at": checkin.checked_in_at.isoformat(),
        "device_id": device_id,
    }


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# POST /sessions/{session_id}/start-attempt
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@router.post(
    "/sessions/{session_id}/start-attempt",
    response_model=ExamAttemptResponse,
    status_code=status.HTTP_200_OK,
)
def start_attempt(
    session_id: int,
    request: Request,
    current_user=Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """UC-2: Siswa memulai atau melanjutkan pengerjaan ujian."""
    student_id = int(current_user["sub"])
    device_id = request.headers.get("X-Device-Id", "unknown-device")
    ip_address = request.client.host if request.client else "unknown"

    attempt = ExamService.start_attempt(
        db=db,
        session_id=session_id,
        student_id=student_id,
        device_id=device_id,
        ip_address=ip_address,
    )

    from app.models.exam.student_answer import StudentAnswer
    from app.repositories.exam.snapshot_repository import snapshot_repository

    snapshot = snapshot_repository.get_by_session(db, session_id)
    questions_data = []

    if snapshot and snapshot.questions_json:
        q_map = {}
        for q in snapshot.questions_json:
            q_id = q.get("id") or q.get("question_id")
            opts = q.get("options", [])
            formatted_opts = []
            if isinstance(opts, list):
                for idx, opt in enumerate(opts):
                    if isinstance(opt, str):
                        formatted_opts.append({"key": chr(65 + idx), "text": opt})
                    elif isinstance(opt, dict):
                        formatted_opts.append(opt)

            # Deterministic Option Shuffle per Student per Question
            if formatted_opts and len(formatted_opts) > 1:
                opt_seed = f"{session_id}_{student_id}_{q_id}"
                opt_hash = hashlib.sha256(opt_seed.encode("utf-8")).hexdigest()
                opt_rng = random.Random(int(opt_hash, 16))
                shuffled_opts = list(formatted_opts)
                opt_rng.shuffle(shuffled_opts)
                formatted_opts = [
                    {
                        "key": chr(65 + i),
                        "text": o.get("text", str(o)) if isinstance(o, dict) else str(o),
                    }
                    for i, o in enumerate(shuffled_opts)
                ]

            q_map[q_id] = {
                "question_id": q_id,
                "question_type": q.get("type", "PG"),
                "content": q.get("content", ""),
                "options": formatted_opts,
                "score_weight": float(q.get("max_score", q.get("score", 5.0))),
            }

        order_list = attempt.randomized_order or list(q_map.keys())
        for q_id in order_list:
            if q_id in q_map:
                questions_data.append(q_map[q_id])
            elif isinstance(q_id, int) and q_id in q_map:
                questions_data.append(q_map[q_id])

        for q_id, q_item in q_map.items():
            if q_item not in questions_data:
                questions_data.append(q_item)

    saved_answers = (
        db.query(StudentAnswer).filter(StudentAnswer.exam_attempt_id == attempt.id).all()
    )
    answers_map = {}
    for sa in saved_answers:
        answers_map[sa.question_id] = {
            "selected_option": sa.selected_option,
            "text_answer": sa.text_answer,
        }

    status_str = attempt.status.value if hasattr(attempt.status, "value") else str(attempt.status)

    return ExamAttemptResponse(
        id=attempt.id,
        exam_session_id=attempt.exam_session_id,
        student_id=attempt.student_id,
        status=status_str,
        started_at=attempt.started_at,
        deadline_at=attempt.deadline_at,
        remaining_seconds=attempt.remaining_seconds,
        final_score=attempt.final_score,
        randomized_order=attempt.randomized_order,
        questions=questions_data,
        answers=answers_map,
    )


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# POST /attempts/{attempt_id}/autosave
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@router.post(
    "/attempts/{attempt_id}/autosave",
    response_model=StudentAnswerResponse,
    status_code=status.HTTP_200_OK,
)
def autosave_answer(
    attempt_id: int,
    question_id: int,
    selected_option: str | None = None,
    text_answer: str | None = None,
    x_device_token: str | None = Header(default=None, alias="X-Device-Token"),
    current_user=Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """UC-3: Autosave jawaban siswa per soal."""
    student_id = int(current_user["sub"])
    if not x_device_token:
        raise HTTPException(status_code=401, detail="X-Device-Token diperlukan.")

    return ExamService.autosave_answer(
        db=db,
        attempt_id=attempt_id,
        question_id=question_id,
        selected_option=selected_option,
        text_answer=text_answer,
        student_id=student_id,
        token=x_device_token,
    )


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# POST /attempts/{attempt_id}/submit
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@router.post(
    "/attempts/{attempt_id}/submit",
    response_model=ExamAttemptResponse,
    status_code=status.HTTP_200_OK,
)
def submit_attempt(
    attempt_id: int,
    current_user=Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    attempt = ExamService.submit_attempt(db=db, attempt_id=attempt_id)
    status_str = attempt.status.value if hasattr(attempt.status, "value") else str(attempt.status)

    return ExamAttemptResponse(
        id=attempt.id,
        exam_session_id=attempt.exam_session_id,
        student_id=attempt.student_id,
        status=status_str,
        started_at=attempt.started_at,
        deadline_at=attempt.deadline_at,
        remaining_seconds=attempt.remaining_seconds,
        final_score=attempt.final_score,
        randomized_order=attempt.randomized_order,
        answers={},
    )


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# POST /ai/callback  (AI Grading Webhook â€” HMAC verified)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


async def _verify_ai_hmac(request: Request) -> None:
    """Verifikasi raw-body HMAC-SHA256 dari AI service sebelum payload di-parse."""
    import hashlib
    import hmac

    secret = os.getenv("AI_WEBHOOK_SECRET", "")
    if not secret:
        raise HTTPException(status_code=500, detail="AI_WEBHOOK_SECRET not configured")

    sig_header = request.headers.get("X-AI-Signature", "")
    raw_body = await request.body()
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(f"sha256={expected}", sig_header):
        raise HTTPException(status_code=403, detail="Invalid HMAC signature")


@router.post(
    "/ai/callback",
    status_code=status.HTTP_200_OK,
)
async def ai_grading_callback(
    request: Request,
    db: Session = Depends(get_db),
):
    """UC-5: Menerima hasil penilaian dari AI service (HMAC-secured webhook)."""
    # Verifikasi HMAC dari raw body (sebelum parse JSON)
    await _verify_ai_hmac(request)

    import json

    raw = await request.body()
    try:
        data = json.loads(raw)
        payload = AICallbackRequest(**data)
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid callback payload.")

    ExamService.process_ai_callback(
        db=db,
        event_id=str(payload.event_id),
        attempt_id=payload.attempt_id,
        question_id=payload.question_id,
        score=payload.score,
        feedback_text=payload.feedback_text,
        version=payload.grading_version,
    )
    return {"status": "accepted"}
