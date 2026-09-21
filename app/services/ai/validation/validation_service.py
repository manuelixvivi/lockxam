import logging
import time
from typing import List, Optional, Any

from app.services.ai.shared.config import AiConfig
from app.services.ai.shared.llm_client import LlmClient
from app.services.ai.validation.validation_prompt import (
    VALIDATION_PROMPT_VERSION,
    VALIDATION_SYSTEM_PROMPT,
    build_validation_prompt,
)
from app.services.ai.validation.validation_schema import (
    RubricValidateRequest,
    RubricValidateResponse,
    ValidationIssue,
    ValidationStatus,
)

logger = logging.getLogger(__name__)


class ValidationService:
    """
    AI-Assisted Rubric and Answer Key Consistency Validation Service.
    Responsibilities:
      - Validates consistency between Question, Teacher Answer Key, and Rubric.
      - Provides advisory review signals: VALID, SUSPICIOUS, or INVALID.
      - Never mutates teacher data (teacher remains the final pedagogical authority).
      - RAG is disabled by default (operates as pure semantic consistency verification).
    """

    @classmethod
    def validate_rubric_and_key(cls, payload: RubricValidateRequest, db: Optional[Any] = None) -> RubricValidateResponse:
        """
        Executes semantic consistency analysis between question, answer key, and rubric.
        """
        start_time = time.time()
        question = payload.get_effective_question()
        answer_key = (payload.answer_key or "").strip()
        rubric = payload.rubric
        subject = payload.subject or "Umum"
        grade_level = payload.get_effective_grade_level()

        if not question:
            raise ValueError("The 'question' field is required for rubric/key validation.")

        if not answer_key and not rubric:
            return RubricValidateResponse(
                status=ValidationStatus.SUSPICIOUS,
                confidence=0.90,
                reason="Baik kunci jawaban maupun rubrik tidak disertakan. Disarankan guru mengisi panduan penilaian.",
                issues=[
                    ValidationIssue(
                        severity="WARNING",
                        category="MISSING_REQUIREMENT",
                        description="Kunci jawaban dan rubrik penilaian kosong.",
                        suggestion="Tambahkan kunci jawaban resmi atau kriteria rubrik agar AI grading dapat beroperasi secara optimal.",
                    )
                ],
                suggested_review=True,
                model=AiConfig.get_effective_eval_model(db=db),
                prompt_version=VALIDATION_PROMPT_VERSION,
                execution_time_seconds=round(time.time() - start_time, 3),
            )

        user_prompt = build_validation_prompt(
            question=question,
            answer_key=answer_key,
            rubric=rubric,
            question_type=payload.question_type or "essay",
            subject=subject,
            grade_level=grade_level,
            additional_context=payload.additional_context,
        )

        llm_response = LlmClient.call_chat_completion(
            system_prompt=VALIDATION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model=AiConfig.get_effective_eval_model(db=db),
            temperature=0.1,
        )

        data = llm_response.get("data", {})
        raw_status = str(data.get("status", "SUSPICIOUS")).upper()

        if raw_status in ("VALID", "SUSPICIOUS", "INVALID"):
            status_enum = ValidationStatus(raw_status)
        else:
            status_enum = ValidationStatus.SUSPICIOUS

        confidence = float(data.get("confidence", 0.85))
        confidence = max(0.0, min(1.0, confidence))
        reason = data.get(
            "reason",
            "Analisis konsistensi selesai. Tinjauan menyeluruh terhadap butir soal dan kunci telah dilakukan.",
        )

        raw_issues = data.get("issues", [])
        parsed_issues: List[ValidationIssue] = []
        for issue_item in raw_issues:
            if isinstance(issue_item, dict):
                parsed_issues.append(
                    ValidationIssue(
                        severity=issue_item.get("severity", "WARNING"),
                        category=issue_item.get("category", "AMBIGUITY"),
                        description=issue_item.get(
                            "description", "Temuan ketidaksesuaian terdeteksi."
                        ),
                        suggestion=issue_item.get("suggestion"),
                    )
                )

        suggested_review = bool(data.get("suggested_review", status_enum != ValidationStatus.VALID))
        elapsed = round(time.time() - start_time, 3)

        return RubricValidateResponse(
            status=status_enum,
            confidence=confidence,
            reason=reason,
            issues=parsed_issues,
            suggested_review=suggested_review,
            model=llm_response.get("model", AiConfig.VALIDATION_MODEL_NAME),
            prompt_version=VALIDATION_PROMPT_VERSION,
            execution_time_seconds=elapsed,
        )
