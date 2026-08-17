from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common.public_id import PublicIdMixin
from app.models.common.timestamp import TimestampMixin
from app.models.exam.enums import ExamSessionStatus

if TYPE_CHECKING:
    from app.models.exam.exam_attempt import ExamAttempt
    from app.models.exam.package_snapshot import ExamPackageSnapshot


class ExamSession(TimestampMixin, PublicIdMixin, Base):
    __tablename__ = "exam_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_id: Mapped[int] = mapped_column(Integer, nullable=False)
    package_id: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduled_start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scheduled_end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ExamSessionStatus] = mapped_column(
        SQLEnum(ExamSessionStatus, name="exam_session_status_enum"),
        default=ExamSessionStatus.PLANNED,
        nullable=False,
    )

    snapshot: Mapped["ExamPackageSnapshot"] = relationship(
        "ExamPackageSnapshot", back_populates="session", uselist=False
    )
    attempts: Mapped[list["ExamAttempt"]] = relationship(
        "ExamAttempt", back_populates="exam_session"
    )
