from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common.timestamp import TimestampMixin


class TrainingCandidate(TimestampMixin, Base):
    """
    Milestone A8: Training Candidate Entity.
    Stores curated, sanitized, and quality-scored assessment records eligible for model fine-tuning.
    Isolates raw immutable AssessmentHistory from curated LLM SFT datasets.
    """

    __tablename__ = "training_candidates"
    __table_args__ = (
        UniqueConstraint(
            "assessment_history_id", "history_version", name="uq_training_candidate_history_ver"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_history_id: Mapped[int] = mapped_column(
        ForeignKey("assessment_histories.id", ondelete="RESTRICT"), index=True
    )
    history_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Quality Gate Classification
    quality_status: Mapped[str] = mapped_column(
        String(30), default="NEEDS_REVIEW", index=True
    )  # 'ELIGIBLE', 'NEEDS_REVIEW', 'REJECTED'
    quality_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rejection_reasons: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)

    # Privacy & PII Sanitization
    pii_status: Mapped[str] = mapped_column(
        String(30), default="CLEAN", index=True
    )  # 'CLEAN', 'SANITIZED', 'FLAGGED'
    pii_entities_detected: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    sanitized_student_answer: Mapped[str] = mapped_column(Text, nullable=False)
    sanitized_teacher_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Leakage-Free Group Partitioning Key (Hash of Question Text + Answer Key)
    question_group_key: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    # Standardized SFT / PEFT Training Payload
    formatted_sft_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)

    # Academic Domain Metadata & Actor Lineage
    school_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    academic_year_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    subject_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    subject_name: Mapped[str] = mapped_column(String(100), nullable=False)
    class_level: Mapped[str] = mapped_column(String(50), nullable=False)

    # Relationships
    assessment_history = relationship("AssessmentHistory", foreign_keys=[assessment_history_id])
