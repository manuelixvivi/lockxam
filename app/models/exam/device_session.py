from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common.timestamp import TimestampMixin
from app.models.exam.enums import DeviceSessionStatus

if TYPE_CHECKING:
    from app.models.exam.exam_attempt import ExamAttempt


class DeviceSession(TimestampMixin, Base):
    __tablename__ = "device_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_attempt_id: Mapped[int] = mapped_column(
        ForeignKey("exam_attempts.id", ondelete="CASCADE"), nullable=False
    )
    device_id: Mapped[str] = mapped_column(String(255), nullable=False)
    session_token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    status: Mapped[DeviceSessionStatus] = mapped_column(
        SQLEnum(DeviceSessionStatus, name="device_session_status_enum"),
        default=DeviceSessionStatus.ACTIVE,
        nullable=False,
    )
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    attempt: Mapped["ExamAttempt"] = relationship("ExamAttempt", back_populates="device_sessions")


# Partial Unique Index: Memaksakan aturan Single Active Device secara keras di tingkat database
Index(
    "uq_active_device_per_attempt",
    DeviceSession.exam_attempt_id,
    unique=True,
    postgresql_where=(DeviceSession.status == DeviceSessionStatus.ACTIVE),
)
