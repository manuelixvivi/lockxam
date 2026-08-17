from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.academic.enums import EnrollmentStatus
from app.models.common.public_id import PublicIdMixin
from app.models.common.timestamp import TimestampMixin


class StudentClassEnrollment(TimestampMixin, PublicIdMixin, Base):
    __tablename__ = "student_class_enrollments"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    student_id: Mapped[int] = mapped_column(ForeignKey("auth_accounts.id", ondelete="CASCADE"))
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id", ondelete="CASCADE"))
    academic_year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(20), default=EnrollmentStatus.ACTIVE.value)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    student = relationship("AuthAccount", foreign_keys=[student_id])
    class_entity = relationship("ClassEntity", back_populates="enrollments", foreign_keys=[class_id])
    academic_year = relationship("AcademicYear", foreign_keys=[academic_year_id])
    school = relationship("School", foreign_keys=[school_id])
