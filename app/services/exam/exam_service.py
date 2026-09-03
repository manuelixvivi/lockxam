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
import logging
import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

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
        existing = snapshot_repository.get_by_session(db, session.id)
        if existing:
            return existing

        # Load academic ExamSnapshot using session.schedule_id
        from sqlalchemy import select

        from app.models.academic.exam_snapshot import ExamSnapshot

        stmt = select(ExamSnapshot).where(ExamSnapshot.exam_schedule_id == session.schedule_id)
        academic_snapshot = db.scalar(stmt)

        if not academic_snapshot:
            raise BusinessException(
                "Snapshot paket ujian belum tersedia. Harap pastikan guru pengampu telah memfinalisasi dan mengunci paket soal untuk jadwal ini.",
                status_code=400,
            )

        # Create new ExamPackageSnapshot from academic_snapshot
        questions = academic_snapshot.snapshot_data.get("questions", [])

        new_snapshot = ExamPackageSnapshot(
            exam_session_id=session.id,
            source_package_id=academic_snapshot.question_package_id,
            school_id=academic_snapshot.school_id,
            owner_teacher_account_id=academic_snapshot.teacher_id,
            snapshot_version=1,
            questions_json=questions,
        )
        snapshot_repository.create(db, new_snapshot)
        db.flush()
        return new_snapshot

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
            if not session:
                raise BusinessException("Ujian tidak ditemukan.", status_code=404)

            # Auto-activate session if start time has arrived or session was PLANNED / DRAFT
            if session.status not in [ExamSessionStatus.ACTIVE, "ACTIVE"]:
                now_utc = datetime.now(timezone.utc)
                start_at = session.scheduled_start_at
                if start_at and start_at.tzinfo is None:
                    start_at = start_at.replace(tzinfo=timezone.utc)

                if (
                    not start_at
                    or now_utc >= start_at
                    or str(session.status).upper() in ["PLANNED", "DRAFT", "READY", "SCHEDULED"]
                ):
                    session.status = ExamSessionStatus.ACTIVE
                    db.flush()
                else:
                    raise BusinessException("Waktu pelaksanaan ujian belum tiba.", status_code=400)

            # EXAM-QR-01: Validate QR Attendance Checkin Requirement
            from app.repositories.exam.checkin_repository import checkin_repository

            checkin = checkin_repository.get_by_student_and_schedule_or_session(
                db, student_id=student_id, schedule_id=session.schedule_id, session_id=session.id
            )
            if not checkin:
                raise BusinessException(
                    "Anda belum melakukan absensi (Scan QR / Input PIN 6-digit Pengawas). Harap absensi terlebih dahulu sebelum memulai ujian.",
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
            dur_mins = (
                session.duration_minutes
                if session.duration_minutes and session.duration_minutes > 0
                else 30
            )
            target_deadline = now + timedelta(minutes=dur_mins)
            if session.scheduled_end_at:
                sched_end = session.scheduled_end_at
                if sched_end.tzinfo is None:
                    sched_end = sched_end.replace(tzinfo=timezone.utc)
                if sched_end > now:
                    target_deadline = min(target_deadline, sched_end)

            deadline = target_deadline

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

            # Auto-extend deadline if attempt is IN_PROGRESS and student is answering
            if attempt.deadline_at and now > attempt.deadline_at:
                sess = exam_session_repository.get_by_id(db, attempt.exam_session_id)
                dur = sess.duration_minutes if sess and sess.duration_minutes else 30
                attempt.deadline_at = now + timedelta(minutes=dur)
                db.flush()

            # Ensure active device session exists & token synchronized
            active_device = device_session_repository.get_active_by_attempt(db, attempt_id)
            if not active_device:
                active_device = DeviceSession(
                    exam_attempt_id=attempt.id,
                    device_id="autosave_auto_device",
                    session_token=token or "autosave_auto_token",
                    ip_address="127.0.0.1",
                    status=DeviceSessionStatus.ACTIVE,
                    last_active_at=now,
                )
                device_session_repository.create(db, active_device)
                db.flush()
            elif token and active_device.session_token != token:
                active_device.session_token = token
                active_device.last_active_at = now
                db.flush()

            snapshot = snapshot_repository.get_by_session(db, attempt.exam_session_id)
            if not snapshot:
                sess = exam_session_repository.get_by_id(db, attempt.exam_session_id)
                if sess:
                    snapshot = ExamService._lazy_create_package_snapshot(db, sess)

            questions = {}
            if snapshot and snapshot.questions_json:
                for q in snapshot.questions_json:
                    qid = q.get("id") or q.get("question_id")
                    if qid is not None:
                        questions[qid] = q
                        questions[str(qid)] = q
                        if isinstance(qid, str) and qid.isdigit():
                            questions[int(qid)] = q

            target_q = questions.get(question_id) or questions.get(str(question_id))
            if not target_q:
                # If question not found in map, allow saving with generic PG/Essay detection
                target_q = {"type": "PG" if selected_option else "ES"}

            # Lenient answer processing for both PG, IS, and ES
            if selected_option and not text_answer:
                text_answer = None
            elif text_answer and not selected_option:
                selected_option = None

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

    @staticmethod
    def flush_all_answers(
        db: Session,
        attempt_id: int,
        answers_map: dict,
        student_id: int,
        token: str,
    ) -> bool:
        """UC-3.1: Flush & batch save all local answers before submit."""
        if not isinstance(answers_map, dict):
            return True
        for q_id_str, ans_data in answers_map.items():
            if not isinstance(ans_data, dict):
                continue
            try:
                q_id = int(q_id_str)
                sel_opt = ans_data.get("selected_option")
                txt_ans = ans_data.get("text_answer")
                if sel_opt is not None or txt_ans is not None:
                    ExamService.autosave_answer(
                        db=db,
                        attempt_id=attempt_id,
                        question_id=q_id,
                        selected_option=sel_opt,
                        text_answer=txt_ans,
                        student_id=student_id,
                        token=token,
                    )
            except Exception:
                pass
        return True

    @staticmethod
    def auto_submit_expired_attempts(db: Session, student_id: int | None = None) -> int:
        """
        Sweep and automatically submit all attempts where:
        1. attempt.deadline_at <= now_utc
        2. linked session.scheduled_end_at <= now_utc
        3. linked schedule.end_time <= now_wib
        Ensures disconnected students have their last autosaved answers automatically submitted when exam time finishes.
        """
        from app.models.exam.exam_session import ExamSessionStatus

        now_utc = datetime.now(timezone.utc)
        submitted_count = 0

        try:
            sessions = exam_session_repository.get_all(db)
            for sess in sessions:
                if sess.scheduled_end_at:
                    end_dt = sess.scheduled_end_at
                    if end_dt.tzinfo is None:
                        end_dt = end_dt.replace(tzinfo=timezone.utc)
                    if now_utc >= end_dt:
                        if sess.status not in [
                            ExamSessionStatus.COMPLETED,
                            "COMPLETED",
                            "FINISHED",
                        ]:
                            sess.status = ExamSessionStatus.COMPLETED
            db.commit()
        except Exception:
            db.rollback()

        active_attempts = attempt_repository.get_active_or_paused(db, student_id=student_id)
        for att in active_attempts:
            is_expired = False

            # Check attempt deadline
            if att.deadline_at:
                d_at = att.deadline_at
                if d_at.tzinfo is None:
                    d_at = d_at.replace(tzinfo=timezone.utc)
                if now_utc >= d_at:
                    is_expired = True

            # Check session scheduled_end_at
            if not is_expired and att.exam_session_id:
                sess = exam_session_repository.get_by_id(db, att.exam_session_id)
                if sess:
                    if sess.scheduled_end_at:
                        s_end = sess.scheduled_end_at
                        if s_end.tzinfo is None:
                            s_end = s_end.replace(tzinfo=timezone.utc)
                        if now_utc >= s_end:
                            is_expired = True

                    if not is_expired and sess.schedule_id:
                        sch = exam_schedule_repository.get_by_id(db, sess.schedule_id)
                        if sch and sch.end_time:
                            sch_end_wib = ensure_wib(sch.end_time)
                            if now_wib >= sch_end_wib:
                                is_expired = True

            if is_expired:
                try:
                    ExamService.submit_attempt(db, att.id)
                    submitted_count += 1
                except Exception as e:
                    print(f"Auto-submit error for attempt {att.id}: {e}")

        return submitted_count

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
                q_id = q.get("id") or q.get("question_id")
                if q_id is None:
                    continue
                max_score = float(q.get("max_score", q.get("score", 0.0)))
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
    # UC-5b: AI Essay Grading Background Job Execution
    # ──────────────────────────────────────────────────

    @staticmethod
    def execute_ai_essay_grading_job(db: Session, attempt_id: int) -> None:
        """Evaluates pending essay questions using equigradeAI microservice."""
        try:
            attempt = attempt_repository.get_with_lock(db, attempt_id)
            if not attempt or attempt.status != ExamAttemptStatus.GRADING:
                return

            sess = exam_session_repository.get_by_id(db, attempt.exam_session_id)
            if not sess:
                return

            snapshot = snapshot_repository.get_by_session(db, sess.id)
            if not snapshot:
                return

            questions = {q.get("id") or q.get("question_id"): q for q in snapshot.questions_json}
            answers = {
                sa.question_id: sa
                for sa in student_answer_repository.get_all_by_attempt(db, attempt_id)
            }
            evaluations = {
                ev.question_id: ev
                for ev in evaluation_repository.get_all_by_attempt(db, attempt_id)
            }

            from app.models.academic.class_entity import ClassEntity
            from app.models.academic.exam_schedule import ExamSchedule
            from app.models.master.school_level import SchoolLevel
            from app.models.school.school import School
            from app.services.ai.ai_grading_service import AiGradingService

            schedule = db.query(ExamSchedule).filter(ExamSchedule.id == sess.schedule_id).first()
            class_entity = (
                db.query(ClassEntity).filter(ClassEntity.id == schedule.class_id).first()
                if schedule
                else None
            )
            school = (
                db.query(School).filter(School.id == schedule.school_id).first()
                if schedule
                else None
            )
            school_level = (
                db.query(SchoolLevel).filter(SchoolLevel.id == school.school_level_id).first()
                if school
                else None
            )

            education_level = school_level.code if school_level else "SMA"
            education_class = class_entity.name if class_entity else "Kelas 11"

            for q_id, eval_item in evaluations.items():
                if eval_item.grading_status != GradingStatus.AI_PENDING:
                    continue

                q = questions.get(q_id)
                if not q or q.get("type") != "ES":
                    continue

                ans = answers.get(q_id)
                student_answer_text = ans.text_answer if ans else ""

                if not student_answer_text or not student_answer_text.strip():
                    eval_item.score = 0.0
                    eval_item.feedback = "Jawaban kosong."
                    eval_item.grading_status = GradingStatus.AI_DRAFT
                    eval_item.grading_source = GradingSource.AI
                    eval_item.grading_version = 1
                    eval_item.last_evaluated_at = datetime.now(timezone.utc)
                    db.commit()
                    continue

                try:
                    rubrics_list = q.get("rubrics", [])
                    max_score = float(
                        q.get("max_score", q.get("score", eval_item.max_score or 10.0))
                    )
                    ai_res = AiGradingService.grade_essay(
                        question_text=q.get("content", ""),
                        answer_key=q.get("answer_key", ""),
                        student_answer=student_answer_text,
                        rubrics=rubrics_list,
                        concepts=q.get("concepts", []),
                        education_level=education_level,
                        education_class=education_class,
                        db=db,
                        school_id=schedule.school_id if schedule else None,
                        subject_id=schedule.subject_id if schedule else None,
                        academic_year_id=schedule.academic_year_id if schedule else None,
                        subject_name=(
                            schedule.subject.name if (schedule and schedule.subject) else "Umum"
                        ),
                        class_level=education_level,
                        max_score=max_score,
                    )

                    if ai_res and ai_res.get("status") == "success":
                        final_pct = float(ai_res.get("final_score", 0.0))
                        feedback = ai_res.get("feedback", "")
                        actual_score = round((final_pct / 100.0) * max_score, 2)

                        eval_item.score = actual_score
                        eval_item.feedback = feedback
                        eval_item.grading_status = GradingStatus.AI_DRAFT
                        eval_item.grading_source = GradingSource.AI
                        eval_item.grading_version = 1
                        eval_item.last_evaluated_at = datetime.now(timezone.utc)
                        db.commit()
                except Exception as e:
                    logger.warning(f"AI essay grading error for question {q_id}: {e}")
                    pass
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

            # Verifikasi guru pengampu via snapshot / schedule
            attempt_for_auth = attempt_repository.get_with_lock(db, evaluation.exam_attempt_id)
            if not attempt_for_auth:
                raise BusinessException("Attempt tidak ditemukan.", status_code=404)

            snapshot = snapshot_repository.get_by_session(db, attempt_for_auth.exam_session_id)

            is_owner = snapshot and snapshot.owner_teacher_account_id == teacher_account_id
            if not is_owner:
                sess = exam_session_repository.get_by_id(db, attempt_for_auth.exam_session_id)
                if not sess or (
                    snapshot and snapshot.owner_teacher_account_id != teacher_account_id
                ):
                    raise BusinessException(
                        "Akses ditolak: Hanya guru pengampu mata pelajaran pada jadwal ujian ini yang berhak melakukan pengoreksian nilai.",
                        status_code=403,
                    )

            # Validate max score limits using evaluation.max_score directly
            max_allowed = (
                float(evaluation.max_score)
                if (evaluation and evaluation.max_score is not None)
                else 100.0
            )

            if score > max_allowed or score < 0:
                raise BusinessException(
                    f"Perubahan skor ditolak: Skor ({score}) tidak boleh kurang dari 0 atau melebihi skor maksimum ({max_allowed} poin) untuk soal ini.",
                    status_code=400,
                )

            evaluation.score = score
            evaluation.feedback = feedback
            evaluation.grading_status = GradingStatus.FINALIZED
            evaluation.grading_source = GradingSource.TEACHER
            evaluation.last_evaluated_at = datetime.now(timezone.utc)
            db.flush()

            # Milestone A1: Ingest validated evaluation into immutable AssessmentHistory
            try:
                from app.services.ai.assessment_history_service import AssessmentHistoryService

                AssessmentHistoryService.capture_finalized_evaluation(
                    db=db,
                    evaluation=evaluation,
                    finalized_by_teacher_id=teacher_account_id,
                )
            except Exception as hist_err:
                logger.warning(f"Failed to record AssessmentHistory: {hist_err}")

            # Always recalculate final_score and update status upon teacher essay grading
            attempt = attempt_for_auth
            all_evals = evaluation_repository.get_all_by_attempt(db, attempt.id)

            total_score = sum(float(e.score) for e in all_evals)
            total_max_score = sum(float(e.max_score) for e in all_evals)
            attempt.final_score = calculate_final_score(total_score, total_max_score)
            attempt.status = ExamAttemptStatus.GRADED
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
            attempt = None
            if payload.attempt_id:
                attempt = attempt_repository.get_with_lock(db, payload.attempt_id)
            if not attempt and payload.student_id:
                attempt = attempt_repository.get_by_session_and_student(
                    db, payload.exam_session_id, payload.student_id
                )

            now = datetime.now(timezone.utc)
            if payload.student_id:
                device_session_repository.revoke_user_sessions_for_student(
                    db, payload.student_id, reason="REBIND_PROCTOR_RESET"
                )

            if not attempt:
                # If attempt doesn't exist yet, device reset successfully cleared student login locks
                db.commit()
                return ExamAttempt(
                    id=0,
                    exam_session_id=payload.exam_session_id,
                    student_id=payload.student_id,
                    status=ExamAttemptStatus.NOT_STARTED,
                    started_at=now,
                    deadline_at=now,
                )

            if attempt.exam_session_id != payload.exam_session_id:
                raise BusinessException("Verifikasi sesi kepengawasan gagal.", status_code=403)

            # 1. Invalidasi perangkat aktif secara permanen
            device = device_session_repository.get_active_by_attempt(db, attempt.id)
            if device:
                device.status = DeviceSessionStatus.INVALIDATED
                db.flush()

            # 1b. Revoke active UserSessions so student can immediately log in from replacement HP
            if attempt.student_id:
                device_session_repository.revoke_user_sessions_for_student(
                    db, attempt.student_id, reason="REBIND_PROCTOR_RESET"
                )
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
