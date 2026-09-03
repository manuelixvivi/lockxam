import logging
import time
from typing import Any, Callable, Dict, List, Optional

from app.services.ai.rubric.rubric_prompt import (
    RUBRIC_PROMPT_VERSION,
    RUBRIC_SYSTEM_PROMPT,
    build_rubric_prompt,
)
from app.services.ai.rubric.rubric_schema import (
    RubricGenerateRequest,
    RubricGenerateResponse,
)
from app.services.ai.shared.config import AiConfig
from app.services.ai.shared.llm_client import LlmClient

logger = logging.getLogger(__name__)


class RubricService:
    """
    Dedicated AI Rubric Generation Service.
    Responsibilities:
      - Analyzes exam questions and official teacher keys to construct structured rubrics.
      - Never evaluates student answers, never computes scores, never produces student feedback.
      - RAG is disabled by default (operates as pure question-to-rubric generation).
      - Provides an explicit extension point for historical rubric retrieval if needed in future.
    """

    @classmethod
    def generate_rubric(
        cls,
        payload: RubricGenerateRequest,
        historical_rubric_provider: Optional[Callable[..., List[Dict[str, Any]]]] = None,
    ) -> RubricGenerateResponse:
        """
        Generates structured assessment rubrics from question text and answer key.
        """
        start_time = time.time()
        question = payload.get_effective_question()
        answer_key = (payload.answer_key or "").strip()
        grade_level = payload.get_effective_grade_level()
        education_class = payload.education_class or "Kelas 11"
        subject = payload.subject or "Umum"

        if not question and not answer_key:
            raise ValueError(
                "Either 'question' or 'answer_key' must be provided for rubric generation."
            )

        # Extension point: Check if a historical rubric reference provider was explicitly injected
        additional_context = payload.additional_context
        if historical_rubric_provider is not None:
            try:
                hist_rubrics = historical_rubric_provider(question=question, subject=subject)
                if hist_rubrics:
                    additional_context = (
                        additional_context or ""
                    ) + f"\nHistorical Rubric Exemplars: {hist_rubrics}"
            except Exception as e:
                logger.warning(f"Historical rubric provider error: {e}")

        user_prompt = build_rubric_prompt(
            question=question or "Jelaskan konsep berikut sesuai kunci jawaban.",
            answer_key=answer_key or question,
            question_type=payload.question_type or "essay",
            subject=subject,
            grade_level=grade_level,
            education_class=education_class,
            additional_context=additional_context,
        )

        llm_response = LlmClient.call_chat_completion(
            system_prompt=RUBRIC_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model=(
                AiConfig.RUBRIC_MODEL_NAME
                if hasattr(AiConfig, "RUBRIC_MODEL_NAME")
                else AiConfig.MODEL_NAME
            ),
            temperature=0.2,
        )

        data = llm_response.get("data", {})
        rubric_list = data.get("rubric", [])
        concepts = data.get("concepts", [])
        question_type = data.get("question_type", "PROSEDURAL")
        bloom_level = data.get("bloom_level", "C2")
        complexity_score = int(data.get("complexity_score", 50))

        # Fallback if LLM returned empty rubric list
        if not rubric_list:
            rubric_list = [
                {
                    "ku_id": "C1",
                    "text": "Menjelaskan konsep utama secara lengkap dan tepat",
                    "weight": 100.0,
                    "bloom_level": bloom_level,
                    "required_concepts": concepts if concepts else ["konsep utama"],
                    "acceptable_variations": [],
                    "partial_credit_rules": [],
                }
            ]

        # Normalize weights to ensure exact sum = 100.0
        normalized_rubrics = cls._normalize_and_validate_rubrics(rubric_list)

        learning_outcomes = [
            f"{r['text']} [{r.get('bloom_level', 'C2')}]" for r in normalized_rubrics
        ]

        elapsed = round(time.time() - start_time, 3)

        return RubricGenerateResponse(
            status="success",
            question_type=question_type,
            bloom_level=bloom_level,
            complexity_score=complexity_score,
            concepts=concepts,
            rubric=normalized_rubrics,
            learning_outcomes=learning_outcomes,
            model=llm_response.get("model", AiConfig.MODEL_NAME),
            prompt_version=RUBRIC_PROMPT_VERSION,
            execution_time_seconds=elapsed,
        )

    @staticmethod
    def _normalize_and_validate_rubrics(rubrics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicates criteria, assigns unique IDs, and normalizes weights to sum to 100."""
        seen_texts = set()
        unique = []
        for i, r in enumerate(rubrics):
            text = (r.get("text") or r.get("criterion_text") or "").strip()
            if not text:
                continue
            norm_key = text.lower()
            if norm_key in seen_texts:
                continue
            seen_texts.add(norm_key)

            ku_id = r.get("ku_id") or f"C{i+1}"
            try:
                raw_weight = float(r.get("weight", 0))
            except (ValueError, TypeError):
                raw_weight = 0.0

            unique.append(
                {
                    "ku_id": ku_id,
                    "text": text,
                    "weight": max(1.0, raw_weight),
                    "bloom_level": r.get("bloom_level", "C2"),
                    "required_concepts": r.get("required_concepts", []),
                    "acceptable_variations": r.get("acceptable_variations", []),
                    "partial_credit_rules": r.get("partial_credit_rules", []),
                }
            )

        if not unique:
            return [
                {
                    "ku_id": "C1",
                    "text": "Menjelaskan konsep utama secara lengkap dan tepat",
                    "weight": 100.0,
                    "bloom_level": "C2",
                    "required_concepts": [],
                    "acceptable_variations": [],
                    "partial_credit_rules": [],
                }
            ]

        total_weight = sum(item["weight"] for item in unique)
        if total_weight <= 0:
            even_weight = round(100.0 / len(unique), 2)
            for item in unique:
                item["weight"] = even_weight
        else:
            for item in unique:
                item["weight"] = round((item["weight"] / total_weight) * 100.0, 2)

        # Fix minor rounding discrepancies on last item
        current_sum = sum(item["weight"] for item in unique)
        diff = round(100.0 - current_sum, 2)
        if diff != 0:
            unique[-1]["weight"] = round(unique[-1]["weight"] + diff, 2)

        return unique
