from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common.timestamp import TimestampMixin

if TYPE_CHECKING:
    from app.models.teacher.question import Question
    from app.models.teacher.question_package import QuestionPackage


class QuestionPackageItem(TimestampMixin, Base):
    __tablename__ = "question_package_items"
    __table_args__ = (
        UniqueConstraint("package_id", "question_id", name="uq_package_question"),
        UniqueConstraint("package_id", "canonical_order", name="uq_package_order"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    package_id: Mapped[int] = mapped_column(
        ForeignKey("question_packages.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False
    )
    canonical_order: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float] = mapped_column(default=0.0, nullable=False)

    package: Mapped["QuestionPackage"] = relationship("QuestionPackage", back_populates="items")
    question: Mapped["Question"] = relationship("Question", back_populates="package_links")
