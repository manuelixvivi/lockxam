from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common.public_id import PublicIdMixin
from app.models.common.timestamp import TimestampMixin
from app.models.teacher.enums import PackageStatus

if TYPE_CHECKING:
    from app.models.teacher.package_item import QuestionPackageItem


class QuestionPackage(TimestampMixin, PublicIdMixin, Base):
    __tablename__ = "question_packages"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(
        ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    class_level: Mapped[str] = mapped_column(String(50), nullable=False)
    owner_teacher_account_id: Mapped[int] = mapped_column(
        ForeignKey("auth_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    target_counts: Mapped[dict] = mapped_column(
        JSON, nullable=False
    )  # {"PG": 30, "IS": 5, "ES": 5}
    status: Mapped[PackageStatus] = mapped_column(
        String(50), default=PackageStatus.INCOMPLETE, nullable=False
    )
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)

    items: Mapped[list["QuestionPackageItem"]] = relationship(
        "QuestionPackageItem", back_populates="package", cascade="all, delete-orphan"
    )
