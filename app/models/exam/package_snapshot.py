from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.exam.exam_session import ExamSession


class ExamPackageSnapshot(Base):
    __tablename__ = "exam_package_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_session_id: Mapped[int] = mapped_column(
        ForeignKey("exam_sessions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    source_package_id: Mapped[int] = mapped_column(Integer, nullable=False)
    school_id: Mapped[int] = mapped_column(Integer, nullable=False)
    owner_teacher_account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    questions_json: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    session: Mapped["ExamSession"] = relationship("ExamSession", back_populates="snapshot")
