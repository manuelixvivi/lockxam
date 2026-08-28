from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common.public_id import PublicIdMixin
from app.models.common.timestamp import TimestampMixin


class ExamSchedulePackage(TimestampMixin, PublicIdMixin, Base):
    __tablename__ = "exam_schedule_packages"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    academic_year_id: Mapped[int] = mapped_column(
        ForeignKey("academic_years.id", ondelete="RESTRICT")
    )
    title: Mapped[str] = mapped_column(String(255))
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    school = relationship("School", foreign_keys=[school_id])
    academic_year = relationship("AcademicYear", foreign_keys=[academic_year_id])
    schedules = relationship(
        "ExamSchedule",
        back_populates="package",
        cascade="all, delete-orphan",
        foreign_keys="[ExamSchedule.package_id]",
    )
