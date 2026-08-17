from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common.public_id import PublicIdMixin
from app.models.common.timestamp import TimestampMixin
from app.models.teacher.enums import QuestionType

if TYPE_CHECKING:
    from app.models.teacher.package_item import QuestionPackageItem


class Question(TimestampMixin, PublicIdMixin, Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_teacher_account_id: Mapped[int] = mapped_column(
        ForeignKey("auth_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    type: Mapped[QuestionType] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    answer_key: Mapped[str] = mapped_column(Text, nullable=False)
    rubrics: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    class_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ai_grading: Mapped[bool] = mapped_column(default=False, nullable=False)

    package_links: Mapped[list["QuestionPackageItem"]] = relationship(
        "QuestionPackageItem", back_populates="question"
    )
