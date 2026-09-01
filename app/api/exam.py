"""
Exam API â€” Student-facing endpoints.
Auth: Siswa (STUDENT role).
"""

import hashlib
import os
import random
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette import status

from app.core.database import get_db
from app.core.rbac import require_role
from app.models.exam.enums import ExamSessionStatus
from app.models.exam.exam_session import ExamSession
from app.models.security.enums import UserRole
from app.repositories.academic.exam_schedule_repository import exam_schedule_repository
from app.repositories.academic.student_enrollment_repository import student_enrollment_repository
from app.repositories.academic.subject_repository import subject_repository
from app.repositories.exam.attempt_repository import attempt_repository
from app.repositories.exam.checkin_repository import checkin_repository
from app.repositories.exam.exam_session_repository import exam_session_repository
from app.repositories.exam.snapshot_repository import snapshot_repository
from app.repositories.exam.student_answer_repository import student_answer_repository
from app.repositories.security.auth_repository import auth_repository
from app.repositories.teacher.proctor_event_repository import proctor_event_repository
from app.schemas.exam.exam import (
    AICallbackRequest,
    ExamAttemptResponse,
    StudentAnswerResponse,
)
from app.services.exam.exam_service import ExamService
from app.utils.timezone import ensure_wib

router = APIRouter(prefix="/api/v1/exam", tags=["Exam — Student"])

# Storage Telemetry Real-time
TELEMETRY_STORE: dict[int, dict] = {}


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
    attempt = attempt_repository.get_by_id_and_student(
        db, attempt_id=attempt_id, student_id=student_id
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
        from app.models.exam.enums import ExamAttemptStatus

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
    db: Session = Depends(get_db),
):
    """Mendapatkan pengumuman darurat / broadcast dari pengawas untuk sesi ujian ini (Dari DB)."""
    events = proctor_event_repository.get_by_assignment(db, assignment_id=session_id)
    broadcasts = [
        {
            "id": ev.id,
            "message": ev.reason,
            "timestamp": ev.timestamp.isoformat() if ev.timestamp else "",
        }
        for ev in events
    ]
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

    enrollments = student_enrollment_repository.list_active_by_student(db, student_id)
    if not enrollments:
        return []

    class_ids = [e.class_id for e in enrollments]

    # Fetch all eligible schedules (READY, ACTIVE, CLOSED, FINISHED, EXPIRED) for missed-exam detection
    active_schedules = exam_schedule_repository.list_eligible_for_classes(db, school_id, class_ids)

    # 2. Preserve historical schedules where student has attempt or check-in
    my_attempts = attempt_repository.get_by_student(db, student_id)
    attempt_session_ids = [a.exam_session_id for a in my_attempts]

    historical_schedule_ids = []
    if attempt_session_ids:
        attempt_sessions = exam_session_repository.get_by_ids(db, attempt_session_ids)
        historical_schedule_ids.extend([se.schedule_id for se in attempt_sessions])

    my_checkins = checkin_repository.get_by_student(db, student_id)
    if my_checkins:
        historical_schedule_ids.extend([c.schedule_id for c in my_checkins])

    historical_schedules = []
    if historical_schedule_ids:
        historical_schedules = exam_schedule_repository.get_by_ids(
            db, list(set(historical_schedule_ids))
        )

    schedule_dict = {s.id: s for s in active_schedules + historical_schedules}
    schedules = sorted(schedule_dict.values(), key=lambda s: s.start_time)

    # Auto-sweep & auto-submit expired attempts (ensures disconnected students have last autosaved answers submitted on timeout)
    try:
        ExamService.auto_submit_expired_attempts(db, student_id=student_id)
    except Exception as sweep_err:
        print(f"Sweep error in get_my_schedules: {sweep_err}")

    res = []
    now_wib = ensure_wib(datetime.now(timezone.utc))

    for s in schedules:
        subj = subject_repository.get_by_id(db, s.subject_id)
        session = exam_session_repository.get_by_schedule_id(db, s.id)

        if not session and s.status != "CANCELLED":
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
        elif session and session.status != ExamSessionStatus.ACTIVE:
            start_wib = ensure_wib(s.start_time)
            if now_wib >= start_wib:
                session.status = ExamSessionStatus.ACTIVE
                db.commit()

        attempt = None
        if session:
            attempt = attempt_repository.get_by_session_and_student(db, session.id, student_id)

        # Cek apakah siswa sudah checkin QR untuk jadwal ini
        checkin = checkin_repository.get_by_schedule_and_student(db, s.id, student_id)

        # ── Classify exam into one of 4 categories ────────────────────────────
        # COMPLETED : student has a submitted/graded attempt
        # ACTIVE    : exam window is currently open (start <= now <= end)
        # MISSED    : exam window has passed AND student has no attempt AND no checkin
        # UPCOMING  : exam has not started yet
        end_wib = ensure_wib(s.end_time)
        start_wib = ensure_wib(s.start_time)

        is_submitted = attempt and attempt.status.value in ("SUBMITTED", "GRADED", "GRADING")
        has_participation = attempt is not None or checkin is not None

        if s.status == "CANCELLED":
            category = "CANCELLED"
        elif is_submitted:
            category = "COMPLETED"
        elif now_wib > end_wib and not has_participation:
            category = "MISSED"
        elif now_wib >= start_wib and now_wib <= end_wib:
            category = "ACTIVE"
        elif now_wib > end_wib and has_participation:
            # Has checkin or in-progress attempt but exam window closed
            category = "COMPLETED"
        else:
            category = "UPCOMING"

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
                "category": category,
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

    enrollment = student_enrollment_repository.get_active_by_student(db, student_id)

    if not enrollment:
        return {"rank_self": None, "leaderboard": []}

    class_id = enrollment.class_id

    # Get all active student IDs in this class
    class_students = student_enrollment_repository.list_by_class(db, class_id, status="ACTIVE")
    student_ids = [cs.student_id for cs in class_students]

    # Calculate average final_score for each student in this class
    results = attempt_repository.get_class_leaderboard(db, student_ids)

    # Map student names
    accounts = auth_repository.get_by_ids(db, student_ids)
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
# In-memory PIN cache for 6-digit short checkin tokens
ACTIVE_PIN_CACHE: dict[str, dict] = {}


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
    Token berlaku 3 menit dan di-sign dengan HMAC-SHA256."""
    import hmac
    import time

    from app.repositories.academic.exam_schedule_repository import exam_schedule_repository

    schedule = exam_schedule_repository.get_by_id(db, schedule_id)
    title = f"Jadwal Ujian #{schedule_id}"
    if schedule:
        title = getattr(
            schedule, "title", getattr(schedule, "name", f"Jadwal Ujian #{schedule_id}")
        )

    # Token: base64url( schedule_id | expires_ts | hmac )
    secret = os.environ.get("SECRET_KEY", "equigrade-secret")
    expires_ts = int(time.time()) + 180  # 3 menit (180 detik)
    payload_str = f"{schedule_id}:{expires_ts}"
    sig = hmac.new(secret.encode(), payload_str.encode(), hashlib.sha256).hexdigest()[:16]
    token = f"{schedule_id}:{expires_ts}:{sig}"

    # Generate short 6-digit numeric PIN
    pin_number = (int(sig[:8], 16) % 900000) + 100000
    pin_code = str(pin_number)

    # Cache PIN mapping
    ACTIVE_PIN_CACHE[pin_code] = {
        "schedule_id": schedule_id,
        "token": token,
        "expires_ts": expires_ts,
    }

    return {
        "schedule_id": schedule_id,
        "schedule_title": title,
        "token": token,
        "qr_token": token,
        "pin_code": pin_code,
        "display_code": pin_code,
        "expires_in_seconds": 180,
    }


# ─────────────────────────────────────────────────────────────────────────────
# POST /checkin  — Siswa scan QR absen / input PIN 6-digit
# ─────────────────────────────────────────────────────────────────────────────


@router.post("/checkin", status_code=status.HTTP_200_OK)
def student_checkin(
    request: Request,
    current_user=Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Siswa melakukan absensi dengan scan QR / input PIN 6-digit dari pengawas."""
    import hmac
    import time

    from app.models.exam.exam_checkin import ExamCheckin

    raw_token: str = request.query_params.get("token", "").strip()
    expected_schedule_id_raw = request.query_params.get("expected_schedule_id")
    expected_schedule_id = (
        int(expected_schedule_id_raw)
        if expected_schedule_id_raw and expected_schedule_id_raw.isdigit()
        else None
    )
    device_id: str = request.headers.get("X-Device-Id", "unknown")

    if not raw_token:
        raise HTTPException(
            status_code=422, detail="Token QR atau Kode PIN 6-digit wajib disertakan."
        )

    clean_pin = raw_token.replace("-", "").replace(" ", "").upper()

    # Resolution from 6-digit PIN cache if student typed PIN
    if clean_pin in ACTIVE_PIN_CACHE:
        cached = ACTIVE_PIN_CACHE[clean_pin]
        if int(time.time()) <= cached["expires_ts"]:
            raw_token = cached["token"]

    # Validasi token
    secret = os.environ.get("SECRET_KEY", "equigrade-secret")
    try:
        parts = raw_token.split(":")
        if len(parts) != 3:
            raise ValueError()
        schedule_id_str, expires_ts_str, sig_received = parts
        schedule_id = int(schedule_id_str)
        expires_ts = int(expires_ts_str)
    except (ValueError, IndexError):
        raise HTTPException(
            status_code=400, detail="Format token QR atau Kode PIN 6-digit tidak valid."
        )

    if expected_schedule_id and expected_schedule_id != schedule_id:
        target_schedule = exam_schedule_repository.get_by_id(db, schedule_id)
        target_title = (
            getattr(
                target_schedule, "title", getattr(target_schedule, "name", f"Jadwal #{schedule_id}")
            )
            if target_schedule
            else f"Jadwal #{schedule_id}"
        )
        raise HTTPException(
            status_code=400,
            detail=f"Token QR ini milik mata pelajaran '{target_title}'. Silakan scan QR sesuai jadwal ujian yang Anda buka!",
        )

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
    schedule = exam_schedule_repository.get_by_id(db, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Jadwal ujian tidak ditemukan.")

    student_id = int(current_user["sub"])

    # Upsert ExamCheckin
    try:
        checkin = checkin_repository.get_by_schedule_and_student(db, schedule_id, student_id)

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

        # Auto-mark student present in Proctor BAP / BAU Document
        try:
            from app.services.teacher.proctor_service import ProctorService

            ProctorService.auto_mark_student_present(db, schedule_id, student_id)
        except Exception as _bau_err:
            print(f"[Checkin BAP Sync Warning] {_bau_err}")

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

    from app.repositories.exam.exam_session_repository import exam_session_repository

    snapshot = snapshot_repository.get_by_session(db, session_id)
    if not snapshot:
        session = exam_session_repository.get_by_id(db, session_id)
        if session:
            try:
                snapshot = ExamService._lazy_create_package_snapshot(db, session)
            except Exception as e:
                print(f"Lazy snapshot creation error: {e}")

    questions_data = []

    if snapshot and snapshot.questions_json:
        q_map = {}
        for q in snapshot.questions_json:
            q_id = q.get("id") or q.get("question_id")
            if q_id is None:
                continue
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
            elif str(q_id) in q_map:
                questions_data.append(q_map[str(q_id)])
            elif isinstance(q_id, str) and q_id.isdigit() and int(q_id) in q_map:
                questions_data.append(q_map[int(q_id)])

        for q_id, q_item in q_map.items():
            if q_item not in questions_data:
                questions_data.append(q_item)

    saved_answers = student_answer_repository.get_all_by_attempt(db, attempt.id)
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
async def autosave_answer(
    attempt_id: int,
    request: Request,
    x_device_token: str | None = Header(default=None, alias="X-Device-Token"),
    current_user=Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """UC-3: Autosave jawaban siswa per soal (Mendukung JSON Body & Query Params)."""
    student_id = int(current_user["sub"])
    if not x_device_token or not x_device_token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header X-Device-Token wajib disertakan dan terdaftar.",
        )
    token_val = x_device_token.strip()

    question_id = None
    selected_option = None
    text_answer = None

    try:
        body = await request.json()
        if isinstance(body, dict):
            question_id = body.get("question_id")
            selected_option = body.get("selected_option")
            text_answer = body.get("text_answer")
    except Exception:
        pass

    if question_id is None:
        q_param = request.query_params.get("question_id")
        if q_param and q_param.isdigit():
            question_id = int(q_param)
        selected_option = request.query_params.get("selected_option")
        text_answer = request.query_params.get("text_answer")

    if question_id is None:
        raise HTTPException(status_code=422, detail="question_id wajib disertakan.")

    return ExamService.autosave_answer(
        db=db,
        attempt_id=attempt_id,
        question_id=int(question_id),
        selected_option=selected_option,
        text_answer=text_answer,
        student_id=student_id,
        token=token_val,
    )


@router.post(
    "/attempts/{attempt_id}/flush-answers",
    status_code=status.HTTP_200_OK,
)
async def flush_all_answers(
    attempt_id: int,
    request: Request,
    x_device_token: str | None = Header(default=None, alias="X-Device-Token"),
    current_user=Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """UC-3.1: Flush & batch save semua jawaban lokal siswa ke database sebelum submit."""
    student_id = int(current_user["sub"])
    token_val = x_device_token or ""

    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    answers_map = body.get("answers", {}) if isinstance(body, dict) else {}

    ExamService.flush_all_answers(
        db=db,
        attempt_id=attempt_id,
        answers_map=answers_map,
        student_id=student_id,
        token=token_val,
    )
    return {"status": "OK", "flushed_count": len(answers_map)}


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
    background_tasks: BackgroundTasks,
    request: Request,
    current_user=Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    attempt = ExamService.submit_attempt(db=db, attempt_id=attempt_id)
    status_str = attempt.status.value if hasattr(attempt.status, "value") else str(attempt.status)

    if status_str == "GRADING":
        base_url = str(request.base_url)
        background_tasks.add_task(
            run_ai_grading_background, attempt_id=attempt.id, base_url=base_url
        )

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

    secret = os.getenv("AI_WEBHOOK_SECRET", "equigrade-ai-webhook-secret-default")
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


def run_ai_grading_background(attempt_id: int, base_url: str = "", _db=None):
    from app.core.database import SessionLocal
    from app.models.exam.enums import ExamAttemptStatus, GradingStatus
    from app.models.exam.exam_attempt import ExamAttempt
    from app.repositories.exam.evaluation_repository import evaluation_repository
    from app.services.exam.exam_service import ExamService, calculate_final_score

    test_mode = _db is not None
    db = _db if test_mode else SessionLocal()

    try:
        # Delegate essay evaluation to domain service layer
        ExamService.execute_ai_essay_grading_job(db, attempt_id)

        # Check if all essay evaluations are graded to advance overall attempt status to GRADED
        db.expire_all()
        evals = evaluation_repository.get_all_by_attempt(db, attempt_id)
        if evals:
            all_graded = True
            total_score = 0.0
            total_max = 0.0
            for ev in evals:
                total_score += float(ev.score)
                total_max += float(ev.max_score)
                if ev.grading_status == GradingStatus.AI_PENDING:
                    all_graded = False

            if all_graded:
                attempt = db.query(ExamAttempt).filter(ExamAttempt.id == attempt_id).first()
                if attempt:
                    attempt.status = ExamAttemptStatus.GRADED
                    attempt.final_score = calculate_final_score(total_score, total_max)
                    if not test_mode:
                        db.commit()
                    else:
                        db.flush()
    finally:
        if not test_mode:
            db.close()
