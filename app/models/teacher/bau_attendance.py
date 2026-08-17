from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common.timestamp import TimestampMixin
from app.models.teacher.enums import AttendanceStatus

if TYPE_CHECKING:
    from app.models.teacher.bau_document import BAUDocument


class BAUAttendance(TimestampMixin, Base):
    __tablename__ = "bau_attendances"
    __table_args__ = (UniqueConstraint("bau_document_id", "student_id", name="uq_bau_student"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    bau_document_id: Mapped[int] = mapped_column(
        ForeignKey("bau_documents.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(nullable=False)
    attendance_status: Mapped[AttendanceStatus] = mapped_column(
        String(50), default=AttendanceStatus.ALPA, nullable=False
    )
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    document: Mapped["BAUDocument"] = relationship("BAUDocument", back_populates="attendances")
