import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.database import Base
from app.models.academic.enums import GradingRunStatus
from app.models.common.timestamp import TimestampMixin


class GradingRun(TimestampMixin, Base):
    """
    Persistent record tracking a post-exam batch grading execution.
    Provides execution lineage, idempotency, and cancelation guarantees
    when exams are reopened or rescheduled.
    """

    __tablename__ = "grading_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exam_schedule_id: Mapped[int] = mapped_column(
        ForeignKey("exam_schedules.id", ondelete="CASCADE"), index=True
    )
    exam_snapshot_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default=GradingRunStatus.QUEUED.value, index=True
    )

    total_questions: Mapped[int] = mapped_column(Integer, default=0)
    total_submissions: Mapped[int] = mapped_column(Integer, default=0)
    total_batches: Mapped[int] = mapped_column(Integer, default=0)
    processed_batches: Mapped[int] = mapped_column(Integer, default=0)
    failed_batches: Mapped[int] = mapped_column(Integer, default=0)

    model_used: Mapped[str] = mapped_column(String(100), default="openai/gpt-oss-120b")
    prompt_version: Mapped[str] = mapped_column(String(50), default="batch_grading_v2.0")
    rag_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    exam_schedule = relationship("ExamSchedule", foreign_keys=[exam_schedule_id])
