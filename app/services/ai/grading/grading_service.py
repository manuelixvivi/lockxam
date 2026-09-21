import logging
import re
import time
from typing import Any, Dict, List, Optional

from app.services.ai.grading.grading_prompt import (
    GRADING_PROMPT_VERSION,
    GRADING_SYSTEM_PROMPT,
    build_essay_grading_prompt,
    build_short_answer_grading_prompt,
)
from app.services.ai.grading.grading_schema import (
    GradingEvaluateRequest,
    GradingEvaluateResponse,
)
from app.services.ai.shared.config import AiConfig
from app.services.ai.shared.llm_client import LlmClient

logger = logging.getLogger(__name__)


class GradingService:
    """
    Dedicated AI Grading Service for EquiGrade.
    Responsibilities:
      - Evaluates student answers against official questions and rubrics.
      - Produces objective percentage scores, scaled scores, and pedagogical feedback.
      - Operates with optional Retrieval-Augmented Generation (RAG) using dense multilingual embeddings.
      - Guarantees fail-safe fallback (RAG failures never break the grading pipeline).
      - Handles both Essay (procedural) and Short Answer (factual/enumeration) items.
    """

    @classmethod
    def is_rag_enabled(cls, override: Optional[bool] = None) -> bool:
        """Checks if RAG augmentation is enabled via parameter override or environment flag."""
        return AiConfig.is_rag_enabled(override)

    @classmethod
    def evaluate(
        cls,
        payload: GradingEvaluateRequest,
        db: Optional[Any] = None,
    ) -> GradingEvaluateResponse:
        """
        Executes complete AI grading pipeline for essay or short answer submissions.
        """
        start_time = time.time()
        question = payload.get_effective_question()
        answer_key = (payload.answer_key or "").strip()
        student_answer = (payload.student_answer or "").strip()
        rubrics = payload.get_effective_rubrics()
        grade_level = payload.get_effective_grade_level()
        education_class = payload.education_class or "Kelas 11"
        max_score = float(payload.max_score or 10.0)
        q_type = (payload.question_type or "essay").lower()

        # Handle empty student answer early and deterministically
        if not student_answer:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            academic_rationale = "Jawaban siswa kosong. Tidak ada poin yang dapat dinilai."
            return GradingEvaluateResponse(
                status="success",
                score=0.0,
                final_score=0.0,
                max_score=max_score,
                feedback="Jawaban siswa kosong. Tidak ada poin yang dapat dinilai.",
                decision={
                    "status": "EMPTY_ANSWER",
                    "confidence": 1.0,
                    "confidence_level": "HIGH",
                    "review_required": False,
                    "quality_indicator": 1.0,
                    "academic_rationale": academic_rationale,
                    "explainability": "Jawaban kosong",
                },
                metrics={"concept": 0, "semantic": 0, "logic": 0, "reasoning": 0},
                rubric_scores=(
                    [
                        {
                            "ku_id": r.get("ku_id", f"C{i+1}"),
                            "text": r.get("text", ""),
                            "weight": r.get("weight", 0),
                            "achieved": 0,
                        }
                        for i, r in enumerate(rubrics)
                    ]
                    if rubrics
                    else []
                ),
                model=AiConfig.EVAL_MODEL_NAME,
                prompt_version=GRADING_PROMPT_VERSION,
                rag_enabled=False,
                latency_ms=elapsed_ms,
                confidence=1.0,
                confidence_level="HIGH",
                review_required=False,
                academic_rationale=academic_rationale,
            )

        # -------------------------------------------------------------
        # 1. RAG Context Retrieval & Fail-Safe Fallback Pipeline
        # -------------------------------------------------------------
        rag_enabled = cls.is_rag_enabled(payload.rag_enabled)
        rag_metadata: Dict[str, Any] = {
            "rag_enabled": rag_enabled,
            "fallback_used": False,
            "retrieved_count": 0,
            "included_count": 0,
            "similarity_scores": [],
        }
        retrieved_cases: List[Dict[str, Any]] = []
        rag_context_tokens = 0
        effective_rag_context = payload.rag_context

        if rag_enabled and effective_rag_context is None:
            if (
                db is not None
                and payload.school_id is not None
                and payload.subject_id is not None
                and payload.academic_year_id is not None
            ):
                try:
                    from app.services.ai.rag_context_service import RagContextService

                    rag_payload = RagContextService.assemble_rag_context(
                        db=db,
                        school_id=payload.school_id,
                        subject_id=payload.subject_id,
                        academic_year_id=payload.academic_year_id,
                        subject_name=payload.subject_name or payload.subject or "Umum",
                        class_level=payload.class_level,
                        question_text=question,
                        answer_key=answer_key,
                        rubrics_json=rubrics,
                        max_score=max_score,
                        student_answer=student_answer,
                        top_k=payload.top_k,
                        similarity_threshold=payload.similarity_threshold,
                    )
                    effective_rag_context = rag_payload.formatted_context_block
                    rag_metadata.update(rag_payload.metadata)
                    rag_metadata["rag_enabled"] = True
                    rag_metadata["fallback_used"] = False
                    retrieved_cases = [
                        {
                            "case_id": c.assessment_history_id,
                            "similarity": round(c.similarity_score, 4),
                            "canonical_text": f"Question: {c.question_text}\nAnswer: {c.student_answer}",
                        }
                        for c in rag_payload.reference_cases
                    ]
                    rag_context_tokens = int(rag_payload.metadata.get("tokens_consumed", 0))
                except Exception as e:
                    # Fail-Safe Invariant: Never let RAG failure crash the grading flow
                    logger.warning(
                        f"RAG context assembly failed, falling back gracefully to standard grading: {e}"
                    )
                    rag_metadata["fallback_used"] = True
                    rag_metadata["fallback_reason"] = f"RAG error: {e}"
                    effective_rag_context = ""
            else:
                rag_metadata["fallback_used"] = True
                rag_metadata["fallback_reason"] = (
                    "RAG enabled but database or tenant context parameters missing"
                )
                effective_rag_context = ""

        # Default fallback rubrics if empty
        if not rubrics:
            rubrics = [
                {
                    "ku_id": "C1",
                    "text": "Kesesuaian dan ketepatan jawaban terhadap kunci jawaban resmi",
                    "weight": 100.0,
                }
            ]

        # -------------------------------------------------------------
        # 2. Construct Prompt (Essay vs Short Answer) & Microservice Bridge
        # -------------------------------------------------------------
        if q_type in ("short_answer", "shortanswer", "is"):
            user_prompt = build_short_answer_grading_prompt(
                question=question or "Jawablah pertanyaan berikut dengan singkat.",
                answer_key=answer_key or question,
                student_answer=student_answer,
                concepts=payload.concepts or [],
                education_level=grade_level,
                education_class=education_class,
            )
        else:
            user_prompt = build_essay_grading_prompt(
                question=question or "Jawablah pertanyaan esai berikut secara komprehensif.",
                answer_key=answer_key or question,
                student_answer=student_answer,
                rubrics=rubrics,
                education_level=grade_level,
                education_class=education_class,
                rag_context=effective_rag_context,
            )

        # -------------------------------------------------------------
        # 3. LLM / Microservice Dispatch via Unified LlmClient
        # -------------------------------------------------------------
        extra_payload = {
            "question_text": question,
            "answer_key": answer_key,
            "student_answer": student_answer,
            "rubrics": rubrics,
            "concepts": payload.concepts or [],
            "education_level": grade_level,
            "education_class": education_class,
            "rag_context": effective_rag_context or "",
        }

        llm_response = LlmClient.call_chat_completion(
            system_prompt=GRADING_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model=AiConfig.get_effective_eval_model(db=db),
            temperature=0.2,
            extra_payload=extra_payload,
        )

        data = llm_response.get("data", {})
        model_used = llm_response.get("model", AiConfig.EVAL_MODEL_NAME)

        feedback = data.get("feedback", "Penilaian otomatis selesai.")
        matched_items = data.get("matched_items")

        # -------------------------------------------------------------
        # 4. Programmatic Score Calculation (Prevent LLM Math Hallucination)
        # -------------------------------------------------------------
        raw_rubric_scores = data.get("rubric_scores", [])
        achieved_map: Dict[str, float] = {}

        if isinstance(raw_rubric_scores, list):
            for item in raw_rubric_scores:
                if isinstance(item, dict):
                    ku_id = str(item.get("ku_id", "")).strip()
                    try:
                        achieved_map[ku_id] = float(item.get("achieved", 0))
                    except (ValueError, TypeError):
                        achieved_map[ku_id] = 0.0

        combined_rubrics: List[Dict[str, Any]] = []
        missing_criteria: List[str] = []

        for i, r in enumerate(rubrics):
            ku_id = str(r.get("ku_id", f"C{i+1}")).strip()
            weight = float(r.get("weight", 100.0 / max(1, len(rubrics))))
            achieved = achieved_map.get(ku_id)

            if achieved is None:
                # Try fallback matching by standard key aliases (e.g. "C1", "1", "ku_1")
                for candidate in [f"C{i+1}", f"ku_{i+1}", str(i + 1), str(i)]:
                    if candidate in achieved_map:
                        achieved = achieved_map[candidate]
                        break

            if achieved is None:
                # If short answer matched items are present, compute achieved proportionally
                if matched_items is not None and isinstance(matched_items, list):
                    achieved = 100.0 if len(matched_items) > 0 else 0.0
                else:
                    # Strict Academic Integrity: Missing rubric evaluation scores 0.0 (Unfulfilled)
                    # Never fabricate arbitrary default grades (e.g. 75/50)
                    achieved = 0.0
                    missing_criteria.append(ku_id)

            combined_rubrics.append(
                {
                    "ku_id": ku_id,
                    "text": r.get("text") or r.get("criterion_text", ""),
                    "weight": weight,
                    "achieved": max(0.0, min(100.0, achieved)),
                }
            )

        total_weight = sum(item["weight"] for item in combined_rubrics) or 100.0
        pct_score = (
            sum((item["achieved"] * item["weight"]) for item in combined_rubrics) / total_weight
        )
        pct_score = round(max(0.0, min(100.0, pct_score)), 2)

        actual_score = round((pct_score / 100.0) * max_score, 2)
        elapsed_ms = round((time.time() - start_time) * 1000, 2)

        # Local metrics calculation
        concept_pct = cls._calc_concept_coverage(student_answer, payload.concepts or [])
        semantic_pct = cls._calc_jaccard_similarity(student_answer, answer_key)

        # Genuine quality / reliability metric: Penalize if criteria were missing from LLM response
        eval_completeness = 1.0 - (len(missing_criteria) / max(1, len(rubrics)))
        quality_indicator = round(
            max(0.0, min(1.0, eval_completeness * (0.85 + (concept_pct / 1000.0)))), 2
        )

        # R5: AI Confidence Level Elevation
        # Read confidence directly from LLM output, otherwise default to high (0.95) if missing but eval is complete
        llm_conf = data.get("confidence")
        if llm_conf is not None:
            try:
                confidence = float(llm_conf)
            except (ValueError, TypeError):
                confidence = 0.95
        else:
            confidence = 0.95 if eval_completeness == 1.0 else 0.85
            
        confidence = round(max(0.0, min(1.0, confidence)), 2)
        
        # Read confidence_level directly from LLM, otherwise classify
        llm_conf_level = data.get("confidence_level")
        if llm_conf_level and isinstance(llm_conf_level, str):
            confidence_level = llm_conf_level.upper()
            review_required = confidence_level != "HIGH"
        else:
            if confidence >= 0.90:
                confidence_level = "HIGH"
                review_required = False
            elif confidence >= 0.75:
                confidence_level = "MEDIUM"
                review_required = True
            else:
                confidence_level = "LOW"
                review_required = True

        academic_rationale = (
            data.get("academic_rationale")
            or data.get("rationale")
            or f"Evaluasi berbasis {len(combined_rubrics)} kriteria rubrik dengan tingkat kesesuaian konsep {concept_pct}% dan kemiripan semantik {semantic_pct}%. Skor akhir: {pct_score}% ({actual_score}/{max_score})."
        )

        metrics = {
            "concept": concept_pct,
            "semantic": semantic_pct,
            "logic": pct_score,
            "reasoning": pct_score,
            "evaluation_completeness": round(eval_completeness * 100, 1),
        }

        decision = {
            "status": "EVALUATED" if not missing_criteria else "PARTIAL_EVALUATED",
            "final_score": pct_score,
            "quality_indicator": quality_indicator,
            "confidence": confidence,
            "confidence_level": confidence_level,
            "review_required": review_required,
            "academic_rationale": academic_rationale,
            "explainability": f"Score: {pct_score} (Concept: {concept_pct}%, Semantic: {semantic_pct}%, Completeness: {round(eval_completeness * 100)}%)",
        }

        return GradingEvaluateResponse(
            status="success",
            score=actual_score,
            final_score=pct_score,
            max_score=max_score,
            feedback=feedback,
            decision=decision,
            metrics=metrics,
            rubric_scores=combined_rubrics,
            matched_items=matched_items,
            model=model_used,
            prompt_version=GRADING_PROMPT_VERSION,
            rag_enabled=rag_enabled,
            retrieved_cases=retrieved_cases,
            rag_context_tokens=rag_context_tokens,
            rag_metadata=rag_metadata,
            latency_ms=elapsed_ms,
            confidence=confidence,
            confidence_level=confidence_level,
            review_required=review_required,
            academic_rationale=academic_rationale,
        )

    @staticmethod
    def _calc_concept_coverage(student_ans: str, concepts: List[str]) -> int:
        if not concepts:
            return 100
        student_lower = student_ans.lower()
        matched = sum(1 for c in concepts if c.lower() in student_lower)
        return round((matched / len(concepts)) * 100)

    @staticmethod
    def _calc_jaccard_similarity(student_ans: str, answer_key: str) -> int:
        stopwords = {"dan", "atau", "yang", "untuk", "pada", "ke", "dari", "ini", "itu", "adalah"}
        w1 = {
            w for w in re.findall(r"\b[a-zA-Z0-9]{3,}\b", student_ans.lower()) if w not in stopwords
        }
        w2 = {
            w for w in re.findall(r"\b[a-zA-Z0-9]{3,}\b", answer_key.lower()) if w not in stopwords
        }
        if not w1 or not w2:
            return 0
        intersection = w1.intersection(w2)
        union = w1.union(w2)
        return round((len(intersection) / len(union)) * 100)
