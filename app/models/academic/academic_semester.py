from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.academic.enums import AcademicStatus
from app.models.common.public_id import PublicIdMixin
from app.models.common.timestamp import TimestampMixin


class AcademicSemester(TimestampMixin, PublicIdMixin, Base):
    __tablename__ = "academic_semesters"

    id: Mapped[int] = mapped_column(primary_key=True)
    academic_year_id: Mapped[int] = mapped_column(
        ForeignKey("academic_years.id", ondelete="CASCADE")
    )
    code: Mapped[str] = mapped_column(String(50))  # ODD, EVEN
    display_name: Mapped[str] = mapped_column(String(100))  # Ganjil, Genap
    status: Mapped[str] = mapped_column(String(50), default=AcademicStatus.PLANNED.value)

    # Relationships
    academic_year = relationship("AcademicYear", back_populates="semesters")
