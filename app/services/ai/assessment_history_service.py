import logging

from sqlalchemy.orm import Session

from app.models.academic.exam_schedule import ExamSchedule
from app.models.academic.subject import Subject
from app.models.ai.assessment_history import AssessmentHistory
from app.models.exam.answer_evaluation import ExamAnswerEvaluation
from app.models.exam.enums import GradingSource, GradingStatus
from app.repositories.ai.assessment_history_repository import (
    assessment_history_repository,
)
from app.repositories.exam.attempt_repository import attempt_repository
from app.repositories.exam.exam_session_repository import exam_session_repository
from app.repositories.exam.snapshot_repository import snapshot_repository
from app.repositories.exam.student_answer_repository import student_answer_repository
from app.services.ai.shared.config import AiConfig

logger = logging.getLogger(__name__)


class AssessmentHistoryService:
    """
    Assessment History Service — Milestone A1

    Orchestrates the immutable archival of teacher-validated essay grading records.
    Enforces the RAG Trust Boundary, strict append-only versioning, and snapshot-derived
    data integrity.
    """

    @classmethod
    def capture_finalized_evaluation(
        cls,
        db: Session,
        evaluation: ExamAnswerEvaluation,
        finalized_by_teacher_id: int,
    ) -> AssessmentHistory | None:
        """
        Captures a teacher-finalized evaluation into the authoritative AssessmentHistory dataset.

        Trust Boundary Invariants:
        1. grading_status == FINALIZED
        2. grading_source == TEACHER
        3. question_type == 'ES'
        4. student_answer.strip() != ""
        """
        # 1. Verify RAG Trust Boundary
        if (
            evaluation.grading_status != GradingStatus.FINALIZED
            or evaluation.grading_source != GradingSource.TEACHER
        ):
            return None

        # 2. Retrieve Exam Attempt & Session
        attempt = attempt_repository.get_by_id(db, evaluation.exam_attempt_id)
        if not attempt:
            return None

        session = exam_session_repository.get_by_id(db, attempt.exam_session_id)
        if not session:
            return None

        # 3. Retrieve Frozen Snapshot as the Absolute Source of Truth for Question Content
        snapshot = snapshot_repository.get_by_session(db, session.id)
        if not snapshot or not snapshot.questions_json:
            return None

        # Find question matching evaluation.question_id inside snapshot
        q_data = next(
            (
                q
                for q in snapshot.questions_json
                if (q.get("id") or q.get("question_id")) == evaluation.question_id
            ),
            None,
        )
        if not q_data:
            return None

        # Verify Question Type is Essay
        if q_data.get("type") != "ES":
            return None

        # 4. Retrieve Student Answer Verbatim
        student_ans = student_answer_repository.get_by_attempt_and_question(
            db, attempt.id, evaluation.question_id
        )
        student_answer_text = (
            student_ans.text_answer if student_ans and student_ans.text_answer else ""
        )
        if not student_answer_text.strip():
            # Empty student answers are not eligible for RAG knowledge
            return None

        # 5. Extract Academic Context
        schedule = db.query(ExamSchedule).filter(ExamSchedule.id == session.schedule_id).first()
        if not schedule:
            return None

        subject = db.query(Subject).filter(Subject.id == schedule.subject_id).first()
        subject_name = subject.name if subject else (q_data.get("subject") or "Mata Pelajaran")
        class_level = q_data.get("class_level") or "Kelas"

        # 6. Extract Frozen Question Payload from Snapshot
        question_text = q_data.get("content", "")
        answer_key = q_data.get("answer_key", "")
        rubrics_json = q_data.get("rubrics", [])
        max_score = float(
            evaluation.max_score
            if evaluation.max_score is not None
            else q_data.get("max_score", 10.0)
        )

        # 7. Extract AI Provenance Metadata
        ai_model_name = getattr(evaluation, "model_name", None) or AiConfig.EVAL_MODEL_NAME
        ai_prompt_version = "v2.1-rubric-grounded"
        ai_rubric_version = getattr(snapshot, "snapshot_version", 1)
        ai_evaluated_at = evaluation.last_evaluated_at

        # Prior AI draft score & feedback if available
        ai_score = None
        ai_feedback = None

        # 8. Append-Only Versioning & Idempotency Handling
        existing_history = assessment_history_repository.get_current_by_evaluation(
            db, evaluation.id
        )

        if existing_history:
            # Check Idempotency: exact same teacher finalization called again without changes
            if (
                float(existing_history.final_score) == float(evaluation.score)
                and (existing_history.teacher_feedback or "") == (evaluation.feedback or "")
                and existing_history.finalized_by_teacher_id == finalized_by_teacher_id
            ):
                return existing_history

            # Teacher has modified score/feedback: mark previous version superseded
            assessment_history_repository.mark_superseded(db, existing_history.id)
            next_version = existing_history.version + 1
            ai_score = existing_history.ai_score
            ai_feedback = existing_history.ai_feedback
        else:
            next_version = 1

        # Calculate score delta between final score and AI score
        score_delta = 0.0
        if ai_score is not None:
            score_delta = float(evaluation.score) - float(ai_score)

        # 9. Instantiate Immutable Historical Record
        history_record = AssessmentHistory(
            school_id=schedule.school_id,
            academic_year_id=schedule.academic_year_id,
            subject_id=schedule.subject_id,
            subject_name=subject_name,
            class_level=class_level,
            evaluation_id=evaluation.id,
            exam_attempt_id=attempt.id,
            question_id=evaluation.question_id,
            exam_teacher_id=schedule.teacher_id,
            finalized_by_teacher_id=finalized_by_teacher_id,
            version=next_version,
            is_current=True,
            superseded_at=None,
            question_text=question_text,
            question_type="ES",
            answer_key=answer_key,
            rubrics_json=rubrics_json,
            max_score=max_score,
            student_answer=student_answer_text,
            ai_score=ai_score,
            ai_feedback=ai_feedback,
            ai_model_name=ai_model_name,
            ai_prompt_version=ai_prompt_version,
            ai_rubric_version=ai_rubric_version,
            ai_evaluated_at=ai_evaluated_at,
            teacher_score=float(evaluation.score),
            teacher_feedback=evaluation.feedback,
            final_score=float(evaluation.score),
            score_delta=score_delta,
            is_rag_eligible=True,
            embedding_status="PENDING",
        )

        persisted = assessment_history_repository.create(db, history_record)

        # 10. Automatic Embedding Pipeline (Milestone A3/A6 integration)
        # Immediately vectorize finalized exemplar into 1024D dense embedding
        try:
            from app.services.ai.embedding_service import EmbeddingService

            EmbeddingService.embed_and_persist_history(db, persisted)
        except Exception as embed_err:
            logger.warning(
                f"Auto-embedding failed for history_id={persisted.id} (status remains PENDING): {embed_err}"
            )

        return persisted
