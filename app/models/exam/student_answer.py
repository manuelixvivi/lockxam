from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.exam.exam_attempt import ExamAttempt


class StudentAnswer(Base):
    __tablename__ = "student_answers"
    __table_args__ = (
        UniqueConstraint("exam_attempt_id", "question_id", name="uq_attempt_question"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_attempt_id: Mapped[int] = mapped_column(
        ForeignKey("exam_attempts.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[int] = mapped_column(Integer, nullable=False)
    selected_option: Mapped[str | None] = mapped_column(String(10), nullable=True)
    text_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    attempt: Mapped["ExamAttempt"] = relationship("ExamAttempt", back_populates="answers")
