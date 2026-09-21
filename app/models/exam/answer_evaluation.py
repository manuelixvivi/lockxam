from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, Text, UniqueConstraint, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.exam.enums import GradingSource, GradingStatus

if TYPE_CHECKING:
    from app.models.exam.exam_attempt import ExamAttempt


class ExamAnswerEvaluation(Base):
    __tablename__ = "exam_answer_evaluations"
    __table_args__ = (
        UniqueConstraint("exam_attempt_id", "question_id", name="uq_eval_attempt_question"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_attempt_id: Mapped[int] = mapped_column(
        ForeignKey("exam_attempts.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float] = mapped_column(Numeric(5, 2), default=0.0, nullable=False)
    max_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    grading_status: Mapped[GradingStatus] = mapped_column(
        SQLEnum(GradingStatus, name="grading_status_enum"),
        default=GradingStatus.AI_PENDING,
        nullable=False,
    )
    grading_source: Mapped[GradingSource] = mapped_column(
        SQLEnum(GradingSource, name="grading_source_enum"),
        default=GradingSource.SYSTEM,
        nullable=False,
    )
    grading_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    confidence_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_evaluated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    attempt: Mapped["ExamAttempt"] = relationship("ExamAttempt", back_populates="evaluations")
