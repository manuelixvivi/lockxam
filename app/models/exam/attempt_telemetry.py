from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AttemptTelemetry(Base):
    __tablename__ = "attempt_telemetry"

    attempt_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("exam_attempts.id", ondelete="CASCADE"), primary_key=True
    )
    battery_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_charging: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ping_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_offline: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    violation_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    violation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
