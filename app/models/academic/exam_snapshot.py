from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common.public_id import PublicIdMixin


class ExamSnapshot(PublicIdMixin, Base):
    __tablename__ = "exam_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    exam_schedule_id: Mapped[int] = mapped_column(ForeignKey("exam_schedules.id", ondelete="RESTRICT"), unique=True)
    question_package_id: Mapped[int] = mapped_column(ForeignKey("question_packages.id", ondelete="RESTRICT"))
    teacher_id: Mapped[int] = mapped_column(ForeignKey("auth_accounts.id", ondelete="RESTRICT"))
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id", ondelete="RESTRICT"))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="RESTRICT"))
    academic_year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id", ondelete="RESTRICT"))
    academic_semester_id: Mapped[int] = mapped_column(ForeignKey("academic_semesters.id", ondelete="RESTRICT"))

    # Frozen snapshot content (JSON: questions, options, correct_answers, points, rubrics, randomize_settings)
    snapshot_data: Mapped[dict[str, Any]] = mapped_column(JSON)
    total_questions: Mapped[int] = mapped_column(Integer)
    total_points: Mapped[int] = mapped_column(Integer, default=100)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    exam_schedule = relationship("ExamSchedule", back_populates="snapshot", foreign_keys=[exam_schedule_id])
    question_package = relationship("QuestionPackage", foreign_keys=[question_package_id])
    teacher = relationship("AuthAccount", foreign_keys=[teacher_id])
    class_entity = relationship("ClassEntity", foreign_keys=[class_id])
    subject = relationship("Subject", foreign_keys=[subject_id])
    academic_year = relationship("AcademicYear", foreign_keys=[academic_year_id])
    academic_semester = relationship("AcademicSemester", foreign_keys=[academic_semester_id])
    school = relationship("School", foreign_keys=[school_id])
