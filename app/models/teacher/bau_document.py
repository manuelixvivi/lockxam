from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common.timestamp import TimestampMixin
from app.models.teacher.enums import BAUStatus

if TYPE_CHECKING:
    from app.models.teacher.bau_attendance import BAUAttendance


class BAUDocument(TimestampMixin, Base):
    __tablename__ = "bau_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    proctor_assignment_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    status: Mapped[BAUStatus] = mapped_column(String(50), default=BAUStatus.DRAFT, nullable=False)
    proctor_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    attendances: Mapped[list["BAUAttendance"]] = relationship(
        "BAUAttendance", back_populates="document", cascade="all, delete-orphan"
    )
