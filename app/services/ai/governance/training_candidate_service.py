import hashlib
import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.ai.training_candidate import TrainingCandidate
from app.repositories.ai.assessment_history_repository import assessment_history_repository
from app.repositories.ai.training_candidate_repository import training_candidate_repository
from app.services.ai.governance.pii_sanitization_service import PiiSanitizationService
from app.services.ai.governance.quality_gate_service import QualityGateService

logger = logging.getLogger(__name__)


class TrainingCandidateService:
    """
    Milestone A8: Training Candidate Ingestion & Curation Service.
    Transforms raw teacher-ground-truth AssessmentHistory into sanitized, quality-rated
    training candidates with deterministic group partitioning keys.
    """

    @classmethod
    def evaluate_and_ingest_history(
        cls, db: Session, history_id: int, created_by_user_id: Optional[int] = None
    ) -> Optional[TrainingCandidate]:
        """
        Processes a single AssessmentHistory record through PII sanitization,
        quality gate scoring, standardized SFT payload formatting, and actor tracking.
        """
        history = assessment_history_repository.get_by_id(db, history_id)
        if not history:
            logger.warning(f"AssessmentHistory with ID {history_id} not found.")
            return None

        # 1. PII Sanitization (Non-destructive to history)
        sanitized_ans, ans_pii, ans_pii_status = PiiSanitizationService.sanitize_text(
            history.student_answer, field_name="student_answer"
        )
        sanitized_fb, fb_pii, fb_pii_status = PiiSanitizationService.sanitize_text(
            history.teacher_feedback or "", field_name="teacher_feedback"
        )

        all_pii_entities = ans_pii + fb_pii
        overall_pii_status = (
            "SANITIZED"
            if (ans_pii_status == "SANITIZED" or fb_pii_status == "SANITIZED")
            else "CLEAN"
        )

        # 2. Quality Gate Evaluation
        quality_res = QualityGateService.evaluate_quality(
            student_answer=history.student_answer,
            teacher_feedback=history.teacher_feedback,
            teacher_score=float(history.final_score),
            max_score=float(history.max_score if history.max_score is not None else 10.0),
            rubrics=history.rubrics_json if isinstance(history.rubrics_json, list) else [],
        )

        # 3. Deterministic Canonical Question Group Key (Normalized Question + Answer Key + Subject)
        norm_q = " ".join(history.question_text.lower().split())
        norm_k = " ".join(history.answer_key.lower().split())
        group_raw = f"{norm_q}___{norm_k}___{history.subject_name.strip()}"
        group_key = hashlib.sha256(group_raw.encode("utf-8")).hexdigest()

        # 4. Standardized SFT / PEFT Training Example Formatting
        max_sc = float(history.max_score if history.max_score is not None else 10.0)
        final_sc = float(history.final_score)
        pct_sc = round((final_sc / max_sc * 100.0), 2) if max_sc > 0 else 0.0

        target_dict: Dict[str, Any] = {
            "score": final_sc,
            "final_percentage": pct_sc,
            "feedback": sanitized_fb,
        }

        sft_payload: Dict[str, Any] = {
            "task": "essay_grading",
            "subject": history.subject_name,
            "class_level": history.class_level,
            "question": history.question_text,
            "answer_key": history.answer_key,
            "rubric": history.rubrics_json,
            "max_score": max_sc,
            "student_answer": sanitized_ans,
            "target": target_dict,
        }

        # 5. Check Idempotency / Existing Candidate
        existing_candidate = training_candidate_repository.get_by_history_and_version(
            db, history.id, history.version
        )
        if existing_candidate:
            existing_candidate.quality_status = quality_res.quality_status
            existing_candidate.quality_score = quality_res.quality_score
            existing_candidate.rejection_reasons = quality_res.rejection_reasons
            existing_candidate.pii_status = overall_pii_status
            existing_candidate.pii_entities_detected = all_pii_entities
            existing_candidate.sanitized_student_answer = sanitized_ans
            existing_candidate.sanitized_teacher_feedback = sanitized_fb
            existing_candidate.formatted_sft_payload = sft_payload
            existing_candidate.academic_year_id = history.academic_year_id
            if created_by_user_id is not None:
                existing_candidate.created_by_user_id = created_by_user_id
            db.flush()
            return existing_candidate

        # 6. Create New Training Candidate
        new_candidate = TrainingCandidate(
            assessment_history_id=history.id,
            history_version=history.version,
            quality_status=quality_res.quality_status,
            quality_score=quality_res.quality_score,
            rejection_reasons=quality_res.rejection_reasons,
            pii_status=overall_pii_status,
            pii_entities_detected=all_pii_entities,
            sanitized_student_answer=sanitized_ans,
            sanitized_teacher_feedback=sanitized_fb,
            question_group_key=group_key,
            formatted_sft_payload=sft_payload,
            school_id=history.school_id,
            academic_year_id=history.academic_year_id,
            created_by_user_id=created_by_user_id,
            subject_id=history.subject_id,
            subject_name=history.subject_name,
            class_level=history.class_level,
        )

        training_candidate_repository.create(db, new_candidate)
        return new_candidate
