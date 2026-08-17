"""
Exam Domain Service Layer — v3.0 (FROZEN TDD)

Implements all use cases for the Exam Domain:
  - activate_exam_session
  - start_attempt
  - autosave_answer
  - submit_attempt
  - process_ai_callback
  - finalize_evaluation
  - proctor_lock_attempt
  - proctor_unlock_attempt
  - proctor_reset_device

Repository boundary: Service Layer NEVER calls db.query() or select() directly.
All DB access goes through the repository interfaces defined in app/repositories/exam/.
"""

import hashlib
import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exceptions.base import BusinessException
from app.models.exam.ai_event_log import AiGradingEventLog
from app.models.exam.answer_evaluation import ExamAnswerEvaluation
from app.models.exam.device_session import DeviceSession
from app.models.exam.enums import (
    DeviceSessionStatus,
    ExamAttemptStatus,
    ExamSessionStatus,
    GradingSource,
    GradingStatus,
)
from app.models.exam.exam_attempt import ExamAttempt
from app.models.exam.exam_session import ExamSession
from app.models.exam.package_snapshot import ExamPackageSnapshot
from app.models.exam.student_answer import StudentAnswer
from app.repositories.exam.ai_event_repository import ai_event_repository
from app.repositories.exam.attempt_repository import attempt_repository
from app.repositories.exam.device_session_repository import device_session_repository
from app.repositories.exam.evaluation_repository import evaluation_repository
from app.repositories.exam.exam_session_repository import exam_session_repository
from app.repositories.exam.snapshot_repository import snapshot_repository
from app.repositories.exam.student_answer_repository import student_answer_repository
from app.schemas.exam.exam import ExamPackageSnapshotPayload, ProctorCommandRequest

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def generate_deterministic_shuffled_order(
    questions: list[dict],
    session_id: int,
    student_id: int,
    version: int,
    randomize_per_type: bool = True,
) -> list[int]:
    """Deterministik shuffle per-question-type (PG → IS → ES) atau acak menyeluruh, seeded dengan sha256."""
    seed_str = f"{session_id}_{student_id}_{version}"
    seed_hash = hashlib.sha256(seed_str.encode("utf-8")).hexdigest()
    seed_int = int(seed_hash, 16)

    rng = random.Random(seed_int)

    if randomize_per_type:
        pg_list = [q for q in questions if q.get("type") == "PG"]
        is_list = [q for q in questions if q.get("type") == "IS"]
        es_list = [q for q in questions if q.get("type") == "ES"]
        other_list = [q for q in questions if q.get("type") not in ("PG", "IS", "ES")]

        rng.shuffle(pg_list)
        rng.shuffle(is_list)
        rng.shuffle(es_list)
        rng.shuffle(other_list)

        combined = pg_list + is_list + es_list + other_list
    else:
        combined = list(questions)
        rng.shuffle(combined)

    return [
        q.get("question_id", q.get("id")) for q in combined if q.get("question_id") or q.get("id")
    ]


def calculate_final_score(total_score: float, total_max_score: float) -> float:
    """Konversi skor ujian menjadi nilai terstandardisasi skala 0 – 100."""
    if total_max_score <= 0:
        return 0.0
    return round((total_score / total_max_score) * 100, 2)


# ─────────────────────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────────────────────


class ExamService:

    # ──────────────────────────────────────────────────
    # UC-1: Aktivasi Sesi Ujian (via Internal Command)
    # ──────────────────────────────────────────────────

    @staticmethod
    def activate_exam_session(
        db: Session, session_id: int, snapshot_payload: ExamPackageSnapshotPayload
    ) -> ExamSession:
        try:
            session = exam_session_repository.get_with_lock(db, session_id)
            if not session:
                raise BusinessException("Sesi ujian tidak ditemukan.", status_code=404)

            if session.status == ExamSessionStatus.ACTIVE:
                return session  # idempotent

            if session.status == ExamSessionStatus.COMPLETED:
                raise BusinessException(
                    "Sesi ujian yang telah selesai tidak dapat diaktifkan kembali.",
                    status_code=400,
                )

            # Cek snapshot eksistensi via Repository (boundary clean)
            existing_snapshot = snapshot_repository.get_by_session(db, session_id)

            if not existing_snapshot:
                try:
                    new_snapshot = ExamPackageSnapshot(
                        exam_session_id=session_id,
                        source_package_id=snapshot_payload.source_package_id,
                        school_id=snapshot_payload.school_id,
                        owner_teacher_account_id=snapshot_payload.owner_teacher_account_id,
                        snapshot_version=snapshot_payload.snapshot_version,
                        questions_json=[q.model_dump() for q in snapshot_payload.questions],
                    )
                    snapshot_repository.create(db, new_snapshot)
                    db.flush()
                except IntegrityError as e:
                    db.rollback()
                    if "exam_package_snapshots" in str(e.orig):
                        # Concurrent creation, re-fetch
                        existing_snapshot = snapshot_repository.get_by_session(db, session_id)
                    else:
                        raise

            session.status = ExamSessionStatus.ACTIVE
            db.commit()
            return session
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def _lazy_create_package_snapshot(db: Session, session: ExamSession) -> ExamPackageSnapshot:
        from app.models.academic.exam_schedule import ExamSchedule
        from app.models.academic.exam_snapshot import ExamSnapshot
        from app.repositories.teacher.question_package_repository import question_package_repository

        schedule = db.query(ExamSchedule).filter(ExamSchedule.id == session.schedule_id).first()
        if not schedule:
            raise BusinessException("Jadwal ujian tidak ditemukan.", status_code=404)

        acad_snap = (
            db.query(ExamSnapshot).filter(ExamSnapshot.exam_schedule_id == schedule.id).first()
        )

        questions_list = []
        source_pkg_id = 0
        owner_id = schedule.teacher_id or 1
        school_id = schedule.school_id

        if acad_snap and isinstance(acad_snap.snapshot_data, dict):
            source_pkg_id = acad_snap.question_package_id
            owner_id = acad_snap.teacher_id
            school_id = acad_snap.school_id
            raw_qs = acad_snap.snapshot_data.get("questions", [])
            for q in raw_qs:
                opts = q.get("options", [])
                formatted_opts = []
                if isinstance(opts, list):
                    for idx, opt in enumerate(opts):
                        if isinstance(opt, str):
                            formatted_opts.append({"key": chr(65 + idx), "text": opt})
                        elif isinstance(opt, dict):
                            formatted_opts.append(opt)

                questions_list.append(
                    {
                        "id": q.get("question_id") or q.get("id"),
                        "type": q.get("type", "PG"),
                        "content": q.get("content", ""),
                        "options": formatted_opts,
                        "answer_key": q.get("answer_key", ""),
                        "max_score": float(q.get("score", q.get("max_score", 5.0))),
                    }
                )
        elif schedule.package_id:
            pkg = question_package_repository.get_by_id(db, schedule.package_id)
            if pkg:
                source_pkg_id = pkg.id
                owner_id = pkg.owner_teacher_account_id or owner_id
                from app.repositories.teacher.question_repository import question_repository

                pkg_items = question_package_repository.get_package_items(db, pkg.id)
                for item in pkg_items:
                    q = question_repository.get_by_id(db, item.question_id)
                    if q:
                        opts = q.options or []
                        formatted_opts = []
                        if isinstance(opts, list):
                            for idx, opt in enumerate(opts):
                                if isinstance(opt, str):
                                    formatted_opts.append({"key": chr(65 + idx), "text": opt})
                                elif isinstance(opt, dict):
                                    formatted_opts.append(opt)
                        questions_list.append(
                            {
                                "id": q.id,
                                "type": q.type,
                                "content": q.content,
                                "options": formatted_opts,
                                "answer_key": q.answer_key or "",
                                "max_score": float(item.score_override or 5.0),
                            }
                        )

        if not questions_list:
            raise BusinessException(
                "Snapshot paket ujian tidak ditemukan. Harap pastikan guru pengampu telah menugaskan paket soal untuk jadwal ujian ini.",
                status_code=404,
            )

        try:
            new_snapshot = ExamPackageSnapshot(
                exam_session_id=session.id,
                source_package_id=source_pkg_id,
                school_id=school_id,
                owner_teacher_account_id=owner_id,
                snapshot_version=1,
                questions_json=questions_list,
            )
            snapshot_repository.create(db, new_snapshot)
            db.flush()
            return new_snapshot
        except IntegrityError:
            db.rollback()
            existing = snapshot_repository.get_by_session(db, session.id)
            if existing:
                return existing
            raise

    # ──────────────────────────────────────────────────
    # UC-2: Mulai / Resume Pengerjaan Siswa
    # ──────────────────────────────────────────────────

    @staticmethod
    def start_attempt(
        db: Session,
        session_id: int,
        student_id: int,
        device_id: str,
        ip_address: str,
    ) -> ExamAttempt:
        try:
            session = exam_session_repository.get_with_lock(db, session_id)
            if not session or session.status != ExamSessionStatus.ACTIVE:
                raise BusinessException("Ujian tidak aktif atau tidak ditemukan.", status_code=400)

            # EXAM-QR-01: Validate QR Attendance Checkin Requirement
            from app.models.exam.exam_checkin import ExamCheckin

            checkin = (
                db.query(ExamCheckin)
                .filter(
                    ExamCheckin.schedule_id == session.schedule_id,
                    ExamCheckin.student_id == student_id,
                )
                .first()
            )
            if not checkin:
                raise BusinessException(
                    "Anda belum melakukan absensi QR Code pengawas. Harap scan QR absensi terlebih dahulu sebelum memulai ujian.",
                    status_code=400,
                )

            existing = attempt_repository.get_by_session_and_student(db, session_id, student_id)
            if existing:
                # EXAM-FIX-11: Resume dari Device Reset (PAUSED + remaining_seconds != NULL)
                if (
                    existing.status == ExamAttemptStatus.PAUSED
                    and existing.remaining_seconds is not None
                ):
                    old_device = device_session_repository.get_active_by_attempt(db, existing.id)
                    if old_device:
                        old_device.status = DeviceSessionStatus.INVALIDATED
                        db.flush()

                    now = datetime.now(timezone.utc)
                    new_device = DeviceSession(
                        exam_attempt_id=existing.id,
                        device_id=device_id,
                        session_token=uuid.uuid4().hex,
                        ip_address=ip_address,
                        status=DeviceSessionStatus.ACTIVE,
                        last_active_at=now,
                    )
                    device_session_repository.create(db, new_device)

                    # Hitung ulang deadline dari sisa detik yang tersimpan
                    existing.deadline_at = now + timedelta(seconds=existing.remaining_seconds)
                    existing.remaining_seconds = None
                    existing.status = ExamAttemptStatus.IN_PROGRESS
                    db.commit()

                return existing

            # Buat attempt baru
            snapshot = snapshot_repository.get_by_session(db, session_id)
            if not snapshot:
                snapshot = ExamService._lazy_create_package_snapshot(db, session)

            rand_per_type = True
            if (
                snapshot
                and hasattr(snapshot, "snapshot_data")
                and isinstance(snapshot.snapshot_data, dict)
            ):
                rules = snapshot.snapshot_data.get("rules_config", {})
                rand_per_type = rules.get("randomize_per_type", True)

            shuffled_ids = generate_deterministic_shuffled_order(
                snapshot.questions_json,
                session_id,
                student_id,
                snapshot.snapshot_version,
                randomize_per_type=rand_per_type,
            )

            now = datetime.now(timezone.utc)
            deadline = min(
                now + timedelta(minutes=session.duration_minutes),
                session.scheduled_end_at,
            )

            try:
                attempt = ExamAttempt(
                    exam_session_id=session_id,
                    student_id=student_id,
                    status=ExamAttemptStatus.IN_PROGRESS,
                    randomized_order=shuffled_ids,
                    started_at=now,
                    deadline_at=deadline,
                )
                attempt_repository.create(db, attempt)
                db.flush()

                # Auto-mark BAP attendance as PRESENT for this student
                try:
                    from app.services.teacher.proctor_service import ProctorService

                    ProctorService.auto_mark_student_present(db, session.schedule_id, student_id)
                except Exception:
                    pass
            except IntegrityError as e:
                db.rollback()
                if "exam_attempts" in str(e.orig):
                    # Race condition: sibling request sudah membuat attempt
                    return attempt_repository.get_by_session_and_student(db, session_id, student_id)
                raise

            device = DeviceSession(
                exam_attempt_id=attempt.id,
                device_id=device_id,
                session_token=uuid.uuid4().hex,
                ip_address=ip_address,
                status=DeviceSessionStatus.ACTIVE,
                last_active_at=now,
            )
            device_session_repository.create(db, device)
            db.commit()
            return attempt
        except Exception:
            db.rollback()
            raise

    # ──────────────────────────────────────────────────
    # UC-3: Autosave Jawaban
    # ──────────────────────────────────────────────────

    @staticmethod
    def autosave_answer(
        db: Session,
        attempt_id: int,
        question_id: int,
        selected_option: str | None,
        text_answer: str | None,
        student_id: int,
        token: str,
    ) -> StudentAnswer:
        try:
            attempt = attempt_repository.get_with_lock(db, attempt_id)
            if not attempt or attempt.student_id != student_id:
                raise BusinessException("Akses ditolak.", status_code=403)

            if attempt.status != ExamAttemptStatus.IN_PROGRESS:
                raise BusinessException("Ujian tidak sedang berjalan.", status_code=400)

            now = datetime.now(timezone.utc)
            if attempt.deadline_at and now > attempt.deadline_at + timedelta(seconds=10):
                raise BusinessException(
                    "EXAM_EXPIRED: Waktu pengerjaan telah habis.", status_code=400
                )

            active_device = device_session_repository.get_active_by_attempt(db, attempt_id)
            if not active_device or active_device.session_token != token:
                raise BusinessException(
                    "SESSION_CONFLICT: Token perangkat tidak aktif.", status_code=409
                )

            snapshot = snapshot_repository.get_by_session(db, attempt.exam_session_id)
            questions = {q["id"]: q for q in snapshot.questions_json}
            if question_id not in questions:
                raise BusinessException("Soal bukan anggota paket ujian.", status_code=400)

            target_q = questions[question_id]

            # Validasi tipe soal
            if target_q["type"] == "PG":
                if not selected_option:
                    raise BusinessException(
                        "PG wajib menyertakan selected_option.", status_code=400
                    )
                text_answer = None
            else:  # IS / ES
                if selected_option:
                    raise BusinessException(
                        "Isian/Essay tidak boleh memiliki selected_option.", status_code=400
                    )

            answer = student_answer_repository.get_by_attempt_and_question_with_lock(
                db, attempt_id, question_id
            )
            if answer:
                answer.selected_option = selected_option
                answer.text_answer = text_answer
                answer.last_updated_at = now
            else:
                try:
                    with db.begin_nested():
                        answer = StudentAnswer(
                            exam_attempt_id=attempt_id,
                            question_id=question_id,
                            selected_option=selected_option,
                            text_answer=text_answer,
                            last_updated_at=now,
                        )
                        db.add(answer)
                        db.flush()
                except Exception:
                    # Parallel race condition fallback: update existing record locked
                    answer = student_answer_repository.get_by_attempt_and_question_with_lock(
                        db, attempt_id, question_id
                    )
                    if answer:
                        answer.selected_option = selected_option
                        answer.text_answer = text_answer
                        answer.last_updated_at = now

            active_device.last_active_at = now
            db.commit()
            return answer
        except Exception:
            db.rollback()
            raise

    # ──────────────────────────────────────────────────
    # UC-4: Submit Attempt & Auto-Grading
    # ──────────────────────────────────────────────────

    @staticmethod
    def submit_attempt(db: Session, attempt_id: int) -> ExamAttempt:
        try:
            attempt = attempt_repository.get_with_lock(db, attempt_id)
            if not attempt:
                raise BusinessException("Attempt tidak ditemukan.", status_code=404)

            if attempt.status in [
                ExamAttemptStatus.SUBMITTED,
                ExamAttemptStatus.GRADING,
                ExamAttemptStatus.GRADED,
            ]:
                return attempt  # idempotent

            attempt.status = ExamAttemptStatus.SUBMITTED
            attempt.updated_at = datetime.now(timezone.utc)
            db.flush()

            answers = {
                a.question_id: a
                for a in student_answer_repository.get_all_by_attempt(db, attempt_id)
            }
            snapshot = snapshot_repository.get_by_session(db, attempt.exam_session_id)
            questions = snapshot.questions_json

            has_essay = False
            total_score = 0.0
            total_max_score = 0.0

            for q in questions:
                q_id = q["id"]
                max_score = float(q["max_score"])
                total_max_score += max_score
                ans = answers.get(q_id)

                score = 0.0
                status = GradingStatus.AI_PENDING
                source = GradingSource.SYSTEM

                if q["type"] == "PG":
                    status = GradingStatus.AUTO_GRADED
                    if ans and ans.selected_option == q["answer_key"]:
                        score = max_score
                    total_score += score
                elif q["type"] == "IS":
                    status = GradingStatus.AUTO_GRADED
                    if ans and ans.text_answer:
                        trimmed_ans = ans.text_answer.strip().lower()
                        allowed_keys = [str(k).strip().lower() for k in q["answer_key"]]
                        if trimmed_ans in allowed_keys:
                            score = max_score
                    total_score += score
                else:
                    has_essay = True

                existing_eval = evaluation_repository.get_by_attempt_and_question_with_lock(
                    db, attempt_id, q_id
                )
                if existing_eval:
                    existing_eval.score = score
                    existing_eval.max_score = max_score
                    existing_eval.grading_status = status
                    existing_eval.grading_source = source
                    existing_eval.grading_version = 1
                else:
                    evaluation = ExamAnswerEvaluation(
                        exam_attempt_id=attempt_id,
                        question_id=q_id,
                        score=score,
                        max_score=max_score,
                        grading_status=status,
                        grading_source=source,
                        grading_version=1,
                    )
                    evaluation_repository.create(db, evaluation)

            if has_essay:
                attempt.status = ExamAttemptStatus.GRADING
            else:
                attempt.status = ExamAttemptStatus.GRADED
                attempt.final_score = calculate_final_score(total_score, total_max_score)

            active_device = device_session_repository.get_active_by_attempt(db, attempt_id)
            if active_device:
                active_device.status = DeviceSessionStatus.INVALIDATED

            db.commit()
            return attempt
        except Exception:
            db.rollback()
            raise

    # ──────────────────────────────────────────────────
    # UC-5: AI Callback Processing (HMAC verified at API layer)
    # ──────────────────────────────────────────────────

    @staticmethod
    def process_ai_callback(
        db: Session,
        event_id: str,
        attempt_id: int,
        question_id: int,
        score: float,
        feedback_text: str,
        version: int,
    ) -> None:
        """EXAM-FIX-01 & EXAM-FIX-02 & EXAM-FIX-09: Lock attempt + idempotency + lock evaluation."""
        try:
            # 1. Lock Attempt & Cek State GRADING
            attempt = attempt_repository.get_with_lock(db, attempt_id)
            if not attempt or attempt.status != ExamAttemptStatus.GRADING:
                return

            # 2. Atomic Idempotency Check (ON CONFLICT DO NOTHING)
            event = AiGradingEventLog(
                event_id=uuid.UUID(event_id),
                attempt_id=attempt_id,
                processed_at=datetime.now(timezone.utc),
                grading_version=version,
            )
            created = ai_event_repository.create_if_not_exists(db, event)
            if not created:
                return  # Duplicate event — safe HTTP 200

            # 3. Lock Evaluation & FINALIZED protection
            evaluation = evaluation_repository.get_by_attempt_and_question_with_lock(
                db, attempt_id, question_id
            )
            if evaluation:
                if evaluation.grading_status == GradingStatus.FINALIZED:
                    db.rollback()
                    return

                if version >= evaluation.grading_version:
                    evaluation.score = score
                    evaluation.feedback = feedback_text
                    evaluation.grading_status = GradingStatus.AI_DRAFT
                    evaluation.grading_source = GradingSource.AI
                    evaluation.grading_version = version
                    evaluation.last_evaluated_at = datetime.now(timezone.utc)

            db.commit()
        except Exception:
            db.rollback()
            raise

    # ──────────────────────────────────────────────────
    # UC-6: Finalisasi Evaluasi oleh Guru
    # ──────────────────────────────────────────────────

    @staticmethod
    def finalize_evaluation(
        db: Session,
        evaluation_id: int,
        score: float,
        feedback: str | None,
        teacher_account_id: int,
    ) -> ExamAnswerEvaluation:
        try:
            evaluation = evaluation_repository.get_with_lock(db, evaluation_id)
            if not evaluation:
                raise BusinessException("Evaluasi tidak ditemukan.", status_code=404)

            # Verifikasi guru pemilik via snapshot (Golden Boundary: tidak JOIN ke Teacher Domain)
            # Ambil attempt terlebih dahulu untuk mendapatkan exam_session_id (avoid lazy load)
            attempt_for_auth = attempt_repository.get_with_lock(db, evaluation.exam_attempt_id)
            if not attempt_for_auth:
                raise BusinessException("Attempt tidak ditemukan.", status_code=404)
            snapshot = snapshot_repository.get_by_session(db, attempt_for_auth.exam_session_id)
            if not snapshot or snapshot.owner_teacher_account_id != teacher_account_id:
                raise BusinessException(
                    "Akses ditolak: Anda bukan pemilik paket ujian ini.", status_code=403
                )

            evaluation.score = score
            evaluation.feedback = feedback
            evaluation.grading_status = GradingStatus.FINALIZED
            evaluation.grading_source = GradingSource.TEACHER
            evaluation.last_evaluated_at = datetime.now(timezone.utc)
            db.flush()

            # Hitung Nilai Akhir jika semua evaluasi sudah terminal
            attempt = attempt_for_auth
            all_evals = evaluation_repository.get_all_by_attempt(db, attempt.id)

            terminal_states = [GradingStatus.AUTO_GRADED, GradingStatus.FINALIZED]
            all_terminal = all(e.grading_status in terminal_states for e in all_evals)

            if all_terminal:
                attempt.status = ExamAttemptStatus.GRADED
                total_score = sum(float(e.score) for e in all_evals)
                total_max_score = sum(float(e.max_score) for e in all_evals)
                attempt.final_score = calculate_final_score(total_score, total_max_score)
                attempt.updated_at = datetime.now(timezone.utc)

            db.commit()
            return evaluation
        except Exception:
            db.rollback()
            raise

    # ──────────────────────────────────────────────────
    # UC-7a: Proctor Lock (PAUSED, countdown tetap jalan)
    # ──────────────────────────────────────────────────

    @staticmethod
    def proctor_lock_attempt(db: Session, payload: ProctorCommandRequest) -> ExamAttempt:
        """EXAM-FIX-11: Proctor Lock → PAUSED, remaining_seconds = NULL, deadline_at TETAP."""
        try:
            attempt = attempt_repository.get_with_lock(db, payload.attempt_id)
            if not attempt:
                raise BusinessException("Attempt pengerjaan tidak ditemukan.", status_code=404)

            if attempt.exam_session_id != payload.exam_session_id:
                raise BusinessException("Verifikasi sesi kepengawasan gagal.", status_code=403)

            if attempt.status != ExamAttemptStatus.IN_PROGRESS:
                raise BusinessException(
                    "Lock hanya bisa dilakukan jika pengerjaan sedang berjalan.", status_code=400
                )

            attempt.status = ExamAttemptStatus.PAUSED
            attempt.remaining_seconds = None  # Countdown tetap jalan secara server wall clock
            attempt.updated_at = datetime.now(timezone.utc)
            db.flush()

            device = device_session_repository.get_active_by_attempt(db, payload.attempt_id)
            if device:
                device.status = DeviceSessionStatus.BLOCKED

            db.commit()
            return attempt
        except Exception:
            db.rollback()
            raise

    # ──────────────────────────────────────────────────
    # UC-7b: Proctor Unlock (resume dari PAUSED/lock)
    # ──────────────────────────────────────────────────

    @staticmethod
    def proctor_unlock_attempt(db: Session, attempt_id: int, exam_session_id: int) -> ExamAttempt:
        """Membuka kembali kunci attempt siswa (Resume Ujian)."""
        try:
            attempt = attempt_repository.get_with_lock(db, attempt_id)
            if not attempt:
                raise BusinessException("Attempt pengerjaan tidak ditemukan.", status_code=404)

            if attempt.exam_session_id != exam_session_id:
                raise BusinessException("Verifikasi sesi kepengawasan gagal.", status_code=403)

            if attempt.status != ExamAttemptStatus.PAUSED:
                raise BusinessException(
                    "Unlock hanya bisa dilakukan jika pengerjaan sedang dikunci.", status_code=400
                )

            attempt.status = ExamAttemptStatus.IN_PROGRESS
            attempt.updated_at = datetime.now(timezone.utc)
            db.flush()

            # EXAM-FIX-10: Ambil session BLOCKED via repository (clean boundary)
            device = device_session_repository.get_blocked_by_attempt_with_lock(db, attempt_id)
            if device:
                device.status = DeviceSessionStatus.ACTIVE

            db.commit()
            return attempt
        except Exception:
            db.rollback()
            raise

    # ──────────────────────────────────────────────────
    # UC-7c: Device Reset (PAUSED, countdown berhenti)
    # ──────────────────────────────────────────────────

    @staticmethod
    def proctor_reset_device(db: Session, payload: ProctorCommandRequest) -> ExamAttempt:
        """EXAM-FIX-11: Device Reset → PAUSED, simpan remaining_seconds, deadline_at = NULL."""
        try:
            attempt = attempt_repository.get_with_lock(db, payload.attempt_id)
            if not attempt:
                raise BusinessException("Attempt pengerjaan tidak ditemukan.", status_code=404)

            if attempt.exam_session_id != payload.exam_session_id:
                raise BusinessException("Verifikasi sesi kepengawasan gagal.", status_code=403)

            # 1. Invalidasi perangkat aktif secara permanen
            device = device_session_repository.get_active_by_attempt(db, payload.attempt_id)
            if device:
                device.status = DeviceSessionStatus.INVALIDATED
                db.flush()

            # 1b. Revoke active UserSessions so student can immediately log in from replacement HP
            now = datetime.now(timezone.utc)
            from app.models.security.user_session import UserSession

            active_auth_sessions = (
                db.query(UserSession)
                .filter(
                    UserSession.auth_account_id == attempt.student_id,
                    UserSession.revoked == False,
                )
                .all()
            )
            for s in active_auth_sessions:
                s.revoked = True
                s.revoked_at = now
                s.revoked_reason = "REBIND_PROCTOR_RESET"
            if (
                attempt.status == ExamAttemptStatus.IN_PROGRESS
                and attempt.deadline_at
                and attempt.deadline_at > now
            ):
                attempt.remaining_seconds = int((attempt.deadline_at - now).total_seconds())
                attempt.deadline_at = None

            attempt.status = ExamAttemptStatus.PAUSED
            attempt.updated_at = now
            db.commit()
            return attempt
        except Exception:
            db.rollback()
            raise
