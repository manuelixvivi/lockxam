from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common.public_id import PublicIdMixin


class ClassSubjectTeacher(PublicIdMixin, Base):
    __tablename__ = "class_subject_teachers"
    __table_args__ = (
        UniqueConstraint("class_id", "subject_id", name="uq_class_subject_teacher"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id", ondelete="CASCADE"))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"))
    teacher_id: Mapped[int] = mapped_column(ForeignKey("auth_accounts.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    class_entity = relationship("ClassEntity", back_populates="subject_teachers", foreign_keys=[class_id])
    subject = relationship("Subject", foreign_keys=[subject_id])
    teacher = relationship("AuthAccount", foreign_keys=[teacher_id])
    school = relationship("School", foreign_keys=[school_id])
