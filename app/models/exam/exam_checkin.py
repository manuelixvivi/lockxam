"""ExamCheckin — Rekaman absensi siswa via QR sebelum ujian dimulai.

Satu record per (schedule_id, student_id). Jika siswa re-scan,
device_id diupdate (rebind pre-exam).
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.common.timestamp import TimestampMixin


class ExamCheckin(TimestampMixin, Base):
    __tablename__ = "exam_checkins"
    __table_args__ = (
        Index("ix_exam_checkins_student_schedule", "student_id", "schedule_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("exam_schedules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True
    )
    device_id: Mapped[str] = mapped_column(String(255), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    checked_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
