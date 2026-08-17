from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.academic.enums import ExamScheduleStatus
from app.models.common.public_id import PublicIdMixin
from app.models.common.timestamp import TimestampMixin


class ExamSchedule(TimestampMixin, PublicIdMixin, Base):
    __tablename__ = "exam_schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    package_id: Mapped[int | None] = mapped_column(ForeignKey("exam_schedule_packages.id", ondelete="CASCADE"), nullable=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    academic_year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id", ondelete="RESTRICT"))
    academic_semester_id: Mapped[int] = mapped_column(ForeignKey("academic_semesters.id", ondelete="RESTRICT"))
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id", ondelete="RESTRICT"))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="RESTRICT"))
    teacher_id: Mapped[int] = mapped_column(ForeignKey("auth_accounts.id", ondelete="RESTRICT"))  # Guru Pengampu
    proctor_id: Mapped[int | None] = mapped_column(ForeignKey("auth_accounts.id", ondelete="SET NULL"), nullable=True)  # Pengawas Ujian
    
    title: Mapped[str] = mapped_column(String(255))
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_minutes: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(50), default=ExamScheduleStatus.DRAFT.value)

    # Exam Configuration Options
    lock_browser: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    eyd_language_evaluation: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    randomize_per_type: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")

    # Make-up / Remedial Target Flags
    target_type: Mapped[str] = mapped_column(String(20), default="ALL_CLASS")
    allowed_student_ids: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)

    # Relationships
    package = relationship("ExamSchedulePackage", back_populates="schedules", foreign_keys=[package_id])
    school = relationship("School", foreign_keys=[school_id])
    academic_year = relationship("AcademicYear", foreign_keys=[academic_year_id])
    academic_semester = relationship("AcademicSemester", foreign_keys=[academic_semester_id])
    class_entity = relationship("ClassEntity", foreign_keys=[class_id])
    subject = relationship("Subject", foreign_keys=[subject_id])
    teacher = relationship("AuthAccount", foreign_keys=[teacher_id])
    proctor = relationship("AuthAccount", foreign_keys=[proctor_id])
    snapshot = relationship("ExamSnapshot", back_populates="exam_schedule", uselist=False)
