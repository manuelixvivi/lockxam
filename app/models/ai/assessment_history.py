from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common.public_id import PublicIdMixin
from app.models.common.timestamp import TimestampMixin


class AssessmentHistory(TimestampMixin, PublicIdMixin, Base):
    """
    Assessment History Domain Entity — Milestone A1

    Represents an immutable, teacher-validated assessment record.
    Acts as the authoritative ground-truth knowledge source for RAG and
    Transformer embedding generation.
    """

    __tablename__ = "assessment_histories"
    __table_args__ = (
        UniqueConstraint("evaluation_id", "version", name="uq_assessment_history_eval_version"),
        Index("ix_ah_tenant_subject", "school_id", "subject_id", "class_level"),
        Index(
            "ix_ah_rag_active_queue",
            "school_id",
            "embedding_status",
            "is_rag_eligible",
            "is_current",
        ),
        Index("ix_ah_lineage_lookup", "school_id", "question_id", "is_current"),
        Index("ix_ah_eval_version_chain", "evaluation_id", "version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # 1. Multi-Tenant & Academic Isolation (Authoritative IDs + Display Context)
    school_id: Mapped[int] = mapped_column(
        ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False
    )
    academic_year_id: Mapped[int] = mapped_column(
        ForeignKey("academic_years.id", ondelete="RESTRICT"), nullable=False
    )
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False
    )
    subject_name: Mapped[str] = mapped_column(String(255), nullable=False)
    class_level: Mapped[str] = mapped_column(String(50), nullable=False)

    # 2. Lineage Tracking & Evaluator Actors
    evaluation_id: Mapped[int] = mapped_column(
        ForeignKey("exam_answer_evaluations.id", ondelete="RESTRICT"), nullable=False
    )
    exam_attempt_id: Mapped[int] = mapped_column(
        ForeignKey("exam_attempts.id", ondelete="RESTRICT"), nullable=False
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False
    )
    exam_teacher_id: Mapped[int] = mapped_column(
        ForeignKey("auth_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    finalized_by_teacher_id: Mapped[int] = mapped_column(
        ForeignKey("auth_accounts.id", ondelete="RESTRICT"), nullable=False
    )

    # 3. Versioning & Immutability Lifecycle
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 4. Frozen Assessment Context (Extracted from ExamPackageSnapshot.questions_json)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(String(50), default="ES", nullable=False)
    answer_key: Mapped[str] = mapped_column(Text, nullable=False)
    rubrics_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    max_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)

    # 5. Student Submission (Verbatim text, PII strictly excluded)
    student_answer: Mapped[str] = mapped_column(Text, nullable=False)

    # 6. AI Assessment Provenance & Draft Data
    ai_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    ai_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ai_prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ai_rubric_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    ai_evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 7. Teacher Ground Truth & Correction Validation
    teacher_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    teacher_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    score_delta: Mapped[float] = mapped_column(Numeric(5, 2), default=0.0, nullable=False)

    # 8. RAG & Transformer Embedding State
    is_rag_eligible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    embedding_status: Mapped[str] = mapped_column(
        String(50), default="PENDING", nullable=False
    )  # PENDING, EMBEDDED, FAILED, SUPERSEDED
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    vector_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Relationships
    school = relationship("School", foreign_keys=[school_id])
    academic_year = relationship("AcademicYear", foreign_keys=[academic_year_id])
    subject = relationship("Subject", foreign_keys=[subject_id])
    evaluation = relationship("ExamAnswerEvaluation", foreign_keys=[evaluation_id])
    exam_attempt = relationship("ExamAttempt", foreign_keys=[exam_attempt_id])
    question = relationship("Question", foreign_keys=[question_id])
    exam_teacher = relationship("AuthAccount", foreign_keys=[exam_teacher_id])
    finalized_by_teacher = relationship("AuthAccount", foreign_keys=[finalized_by_teacher_id])
