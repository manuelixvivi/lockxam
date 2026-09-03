
from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common.public_id import PublicIdMixin
from app.models.common.timestamp import TimestampMixin


class AssessmentEmbedding(TimestampMixin, PublicIdMixin, Base):
    """
    Assessment Embedding Entity — Milestone A3

    Represents the persistent 1024-dimensional dense vector embedding produced by
    the Transformer model (intfloat/multilingual-e5-large) for an immutable
    AssessmentHistory record.
    """

    __tablename__ = "assessment_embeddings"
    __table_args__ = (
        UniqueConstraint(
            "assessment_history_id", "version", name="uq_assessment_embedding_hist_ver"
        ),
        Index("ix_ae_tenant_subject", "school_id", "subject_id", "class_level"),
        Index("ix_ae_content_hash", "content_hash"),
        Index("ix_ae_active_lookup", "school_id", "is_current"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # Lineage & Version Coupling
    assessment_history_id: Mapped[int] = mapped_column(
        ForeignKey("assessment_histories.id", ondelete="RESTRICT"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # Tenant & Academic Metadata (Strictly zero student PII)
    school_id: Mapped[int] = mapped_column(
        ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False
    )
    academic_year_id: Mapped[int] = mapped_column(
        ForeignKey("academic_years.id", ondelete="RESTRICT"), nullable=False
    )
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False
    )
    class_level: Mapped[str] = mapped_column(String(50), nullable=False)

    # Embedding Model Metadata
    embedding_model: Mapped[str] = mapped_column(
        String(100), default="intfloat/multilingual-e5-large", nullable=False
    )
    dimension: Mapped[int] = mapped_column(Integer, default=1024, nullable=False)

    # Dense Vector Payload (L2-Normalized 1024-float array)
    vector_data: Mapped[list[float]] = mapped_column(JSON, nullable=False)

    # Relationships
    assessment_history = relationship("AssessmentHistory", foreign_keys=[assessment_history_id])
    school = relationship("School", foreign_keys=[school_id])
    academic_year = relationship("AcademicYear", foreign_keys=[academic_year_id])
    subject = relationship("Subject", foreign_keys=[subject_id])
