from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.teacher.enums import ProctorEventType


class ProctorAuditEvent(Base):
    __tablename__ = "proctor_audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    proctor_assignment_id: Mapped[int] = mapped_column(
        nullable=False
    )  # Sesi Ujian / Kelas (Exam Domain Link)
    student_id: Mapped[int] = mapped_column(nullable=False)
    event_type: Mapped[ProctorEventType] = mapped_column(String(50), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    proctor_id: Mapped[int] = mapped_column(ForeignKey("auth_accounts.id"), nullable=False)
    action_taken: Mapped[str] = mapped_column(String(255), nullable=False)
