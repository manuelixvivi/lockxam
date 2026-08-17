from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common.public_id import PublicIdMixin
from app.models.common.soft_delete import SoftDeleteMixin
from app.models.common.timestamp import TimestampMixin

if TYPE_CHECKING:
    from app.models.school.school_setting import SchoolSetting


class School(TimestampMixin, PublicIdMixin, SoftDeleteMixin, Base):

    __tablename__ = "schools"

    id: Mapped[int] = mapped_column(primary_key=True)
    npsn: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    domain: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    school_level_id: Mapped[int] = mapped_column(ForeignKey("school_levels.id"))
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(50), default="PENDING_ACTIVATION")

    settings: Mapped["SchoolSetting"] = relationship(
        "SchoolSetting", back_populates="school", uselist=False, cascade="all, delete-orphan"
    )
