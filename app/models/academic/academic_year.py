from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.academic.enums import AcademicStatus
from app.models.common.public_id import PublicIdMixin
from app.models.common.timestamp import TimestampMixin


class AcademicYear(TimestampMixin, PublicIdMixin, Base):
    __tablename__ = "academic_years"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(50))
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(50), default=AcademicStatus.PLANNED.value)

    # Relationships
    school = relationship("School")
    semesters = relationship(
        "AcademicSemester", back_populates="academic_year", cascade="all, delete-orphan"
    )
