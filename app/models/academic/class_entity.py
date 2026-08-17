from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common.public_id import PublicIdMixin
from app.models.common.timestamp import TimestampMixin


class ClassEntity(TimestampMixin, PublicIdMixin, Base):
    __tablename__ = "classes"
    __table_args__ = (
        UniqueConstraint("school_id", "academic_year_id", "name", name="uq_school_academic_class_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    academic_year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(100))
    grade_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    school = relationship("School")
    academic_year = relationship("AcademicYear")
    enrollments = relationship("StudentClassEnrollment", back_populates="class_entity", cascade="all, delete-orphan")
    subject_teachers = relationship("ClassSubjectTeacher", back_populates="class_entity", cascade="all, delete-orphan")
