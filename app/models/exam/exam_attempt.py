from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common.public_id import PublicIdMixin
from app.models.common.timestamp import TimestampMixin
from app.models.exam.enums import ExamAttemptStatus

if TYPE_CHECKING:
    from app.models.exam.answer_evaluation import ExamAnswerEvaluation
    from app.models.exam.device_session import DeviceSession
    from app.models.exam.exam_session import ExamSession
    from app.models.exam.student_answer import StudentAnswer


class ExamAttempt(TimestampMixin, PublicIdMixin, Base):
    __tablename__ = "exam_attempts"
    __table_args__ = (UniqueConstraint("exam_session_id", "student_id", name="uq_session_student"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_session_id: Mapped[int] = mapped_column(
        ForeignKey("exam_sessions.id", ondelete="RESTRICT"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[ExamAttemptStatus] = mapped_column(
        SQLEnum(ExamAttemptStatus, name="exam_attempt_status_enum"),
        default=ExamAttemptStatus.NOT_STARTED,
        nullable=False,
    )
    randomized_order: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remaining_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    final_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    exam_session: Mapped["ExamSession"] = relationship("ExamSession", back_populates="attempts")
    device_sessions: Mapped[list["DeviceSession"]] = relationship(
        "DeviceSession", back_populates="attempt", cascade="all, delete-orphan"
    )
    evaluations: Mapped[list["ExamAnswerEvaluation"]] = relationship(
        "ExamAnswerEvaluation",
        back_populates="attempt",
        cascade="all, delete-orphan",
    )
    answers: Mapped[list["StudentAnswer"]] = relationship(
        "StudentAnswer", back_populates="attempt", cascade="all, delete-orphan"
    )
