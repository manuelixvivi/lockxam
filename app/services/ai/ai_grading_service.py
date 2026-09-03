import logging
from typing import Any, Dict, List, Optional

from app.services.ai.grading.grading_schema import GradingEvaluateRequest
from app.services.ai.grading.grading_service import GradingService
from app.services.ai.rubric.rubric_schema import RubricGenerateRequest
from app.services.ai.rubric.rubric_service import RubricService
from app.services.ai.shared.config import AiConfig
from app.services.ai.shared.llm_client import LlmClient
from app.services.ai.validation.validation_schema import RubricValidateRequest
from app.services.ai.validation.validation_service import ValidationService

logger = logging.getLogger(__name__)


class AiGradingService:
    """
    Backward Compatibility Adapter / Facade connecting legacy callers
    to the modularized Three-Capability EquiGrade AI Architecture:
      1. Rubric Generation AI (RubricService)
      2. Rubric & Answer Key Validation AI (ValidationService)
      3. Grading AI with optional RAG (GradingService)
    """

    @staticmethod
    def is_rag_enabled() -> bool:
        """Checks if RAG-augmented AI grading is enabled."""
        return AiConfig.is_rag_enabled()

    @staticmethod
    def check_ai_health() -> Dict[str, Any]:
        """Check overall AI health and engine status."""
        return LlmClient.check_health()

    @staticmethod
    def generate_rubric(
        question_text: str,
        answer_key: str,
        education_level: str = "SMA",
        education_class: str = "Kelas 11",
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Legacy wrapper for Rubric Generation.
        Delegates to RubricService.generate_rubric().
        """
        req = RubricGenerateRequest(
            question=question_text,
            question_text=question_text,
            answer_key=answer_key,
            grade_level=education_level,
            education_level=education_level,
            education_class=education_class,
            api_key=api_key,
        )
        res = RubricService.generate_rubric(req)
        return {
            "status": res.status,
            "question_type": res.question_type,
            "bloom_level": res.bloom_level,
            "complexity_score": res.complexity_score,
            "concepts": res.concepts,
            "rubrics": res.rubric,
            "learning_outcomes": res.learning_outcomes,
            "model": res.model,
            "prompt_version": res.prompt_version,
            "execution_time_seconds": res.execution_time_seconds,
        }

    @staticmethod
    def validate_rubric(
        question_text: str,
        answer_key: str = "",
        rubric: Optional[Any] = None,
        education_level: str = "SMA",
        education_class: str = "Kelas 11",
        subject: str = "Umum",
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Wrapper for Rubric & Answer Key Validation.
        Delegates to ValidationService.validate_rubric_and_key().
        """
        req = RubricValidateRequest(
            question=question_text,
            question_text=question_text,
            answer_key=answer_key,
            rubric=rubric,
            grade_level=education_level,
            education_level=education_level,
            education_class=education_class,
            subject=subject,
            api_key=api_key,
        )
        res = ValidationService.validate_rubric_and_key(req)
        return res.model_dump()

    @staticmethod
    def grade_essay(
        question_text: str,
        answer_key: str,
        student_answer: str,
        rubrics: Optional[List[Dict[str, Any]]] = None,
        concepts: Optional[List[str]] = None,
        education_level: str = "SMA",
        education_class: str = "Kelas 11",
        api_key: Optional[str] = None,
        # RAG Augmentation Parameters
        db: Optional[Any] = None,
        school_id: Optional[int] = None,
        subject_id: Optional[int] = None,
        academic_year_id: Optional[int] = None,
        subject_name: Optional[str] = None,
        class_level: Optional[str] = None,
        rag_context: Optional[str] = None,
        max_score: float = 10.0,
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Legacy wrapper for Essay Grading with optional RAG.
        Delegates to GradingService.evaluate().
        """
        req = GradingEvaluateRequest(
            question=question_text,
            question_text=question_text,
            answer_key=answer_key,
            student_answer=student_answer,
            rubrics=rubrics or [],
            concepts=concepts or [],
            question_type="essay",
            grade_level=education_level,
            education_level=education_level,
            education_class=education_class,
            school_id=school_id,
            subject_id=subject_id,
            academic_year_id=academic_year_id,
            subject_name=subject_name,
            class_level=class_level,
            rag_context=rag_context,
            max_score=max_score,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            api_key=api_key,
        )
        res = GradingService.evaluate(payload=req, db=db)
        return {
            "status": res.status,
            "final_score": res.final_score,
            "score": res.score,
            "decision": res.decision,
            "metrics": res.metrics,
            "feedback": res.feedback,
            "rubric_scores": res.rubric_scores,
            "matched_items": res.matched_items,
            "rag_metadata": res.rag_metadata,
            "model": res.model,
            "prompt_version": res.prompt_version,
            "latency_ms": res.latency_ms,
        }
