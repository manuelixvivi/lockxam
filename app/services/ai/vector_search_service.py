import logging
import math
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.repositories.ai.assessment_embedding_repository import (
    assessment_embedding_repository,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SimilarAssessmentResult:
    """
    Structured, anonymized result of a semantic similarity search against
    the historical assessment knowledge base.
    Strictly excludes all student PII (no names, NISN, emails, or device IPs).
    """

    assessment_history_id: int
    version: int
    school_id: int
    subject_id: int
    class_level: str
    similarity_score: float
    question_text: str
    answer_key: str
    rubrics_json: list[dict[str, Any]] | None
    student_answer: str
    teacher_feedback: str
    final_score: float
    max_score: float
    content_hash: str


class VectorSearchService:
    """
    Vector Similarity Search Service — Milestone A5

    Executes tenant-isolated, exact cosine similarity searches over
    the pre-filtered candidate pool of active, RAG-eligible historical assessments.
    """

    EXPECTED_DIMENSION = 1024
    MIN_TOP_K = 1
    MAX_TOP_K = 50

    @classmethod
    def validate_vector(cls, vector: list[float]) -> None:
        """
        Validates that a vector is a non-empty, finite 1024-dimensional float array.
        Raises ValueError on malformed, wrong-dimension, NaN, or Inf values.
        """
        if not isinstance(vector, (list, tuple)):
            raise ValueError(
                f"Query vector must be a list/tuple of floats, got {type(vector).__name__}."
            )

        if len(vector) != cls.EXPECTED_DIMENSION:
            raise ValueError(
                f"Query vector dimension mismatch: expected {cls.EXPECTED_DIMENSION}, got {len(vector)}."
            )

        for idx, val in enumerate(vector):
            if not isinstance(val, (int, float)):
                raise ValueError(f"Vector contains non-numeric value at index {idx}: {val}")
            if math.isnan(val):
                raise ValueError(f"Vector contains NaN at index {idx}.")
            if math.isinf(val):
                raise ValueError(f"Vector contains Inf at index {idx}.")

    @classmethod
    def compute_cosine_similarity(cls, vec_a: list[float], vec_b: list[float]) -> float:
        """
        Calculates the exact dot product over L2-normalized vectors.
        Mathematical range: [-1.0, 1.0].
        """
        return sum(a * b for a, b in zip(vec_a, vec_b, strict=False))

    @classmethod
    def search_similar_assessments(
        cls,
        db: Session,
        query_vector: list[float],
        school_id: int,
        subject_id: int,
        academic_year_id: int,
        class_level: str | None = None,
        top_k: int = 3,
        similarity_threshold: float = 0.70,
    ) -> list[SimilarAssessmentResult]:
        """
        Executes tenant-safe, relational pre-filtered similarity retrieval.

        Steps:
        1. Validate query vector (1024-dim, finite floats).
        2. Validate top_k (1 <= top_k <= 50) and similarity_threshold (-1.0 <= threshold <= 1.0).
        3. SQL Pre-filter: Fetch only candidates matching (school_id, subject_id, academic_year_id, is_current=True, is_rag_eligible=True).
        4. Compute exact dot product similarity against each candidate vector.
        5. Filter candidates where similarity_score >= similarity_threshold.
        6. Deterministically sort by similarity_score DESC, secondary key assessment_history_id ASC.
        7. Return top_k results.
        """
        # Step 1: Validate Query Vector
        cls.validate_vector(query_vector)

        # Step 2: Validate Parameters
        if not isinstance(top_k, int) or top_k < cls.MIN_TOP_K or top_k > cls.MAX_TOP_K:
            raise ValueError(
                f"Invalid top_k: {top_k}. Must be an integer between {cls.MIN_TOP_K} and {cls.MAX_TOP_K}."
            )

        if (
            not isinstance(similarity_threshold, (int, float))
            or similarity_threshold < -1.0
            or similarity_threshold > 1.0
        ):
            raise ValueError(
                f"Invalid similarity_threshold: {similarity_threshold}. Must be a float between -1.0 and 1.0."
            )

        # Step 3: SQL Relational Pre-Filter (Enforced at Database Layer)
        candidates = assessment_embedding_repository.get_rag_candidates(
            db=db,
            school_id=school_id,
            subject_id=subject_id,
            academic_year_id=academic_year_id,
            class_level=class_level,
        )

        if not candidates:
            logger.debug(
                f"No RAG candidates found for school_id={school_id}, subject_id={subject_id}, year_id={academic_year_id}"
            )
            return []

        # Step 4 & 5: Compute Exact Dot Product & Threshold Filter
        scored_results: list[SimilarAssessmentResult] = []

        for embedding_record, history_record in candidates:
            doc_vector = embedding_record.vector_data
            if not doc_vector or len(doc_vector) != cls.EXPECTED_DIMENSION:
                logger.warning(
                    f"Skipping malformed stored embedding id={embedding_record.id} (len={len(doc_vector) if doc_vector else 0})"
                )
                continue

            sim_score = cls.compute_cosine_similarity(query_vector, doc_vector)

            if sim_score >= similarity_threshold:
                scored_results.append(
                    SimilarAssessmentResult(
                        assessment_history_id=history_record.id,
                        version=history_record.version,
                        school_id=history_record.school_id,
                        subject_id=history_record.subject_id,
                        class_level=history_record.class_level,
                        similarity_score=float(sim_score),
                        question_text=history_record.question_text,
                        answer_key=history_record.answer_key,
                        rubrics_json=history_record.rubrics_json,
                        student_answer=history_record.student_answer,
                        teacher_feedback=history_record.teacher_feedback,
                        final_score=float(history_record.final_score),
                        max_score=float(history_record.max_score),
                        content_hash=embedding_record.content_hash,
                    )
                )

        # Step 6: Deterministic Ordering (Primary: similarity DESC, Secondary: history_id ASC)
        scored_results.sort(key=lambda item: (-item.similarity_score, item.assessment_history_id))

        # Step 7: Top-K Slicing
        return scored_results[:top_k]
