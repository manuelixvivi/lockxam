from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.school.school import School


class SchoolSetting(Base):

    __tablename__ = "school_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), unique=True
    )
    timezone: Mapped[str] = mapped_column(String(100), default="Asia/Jakarta")
    language: Mapped[str] = mapped_column(String(10), default="id-ID")

    school: Mapped["School"] = relationship("School", back_populates="settings")
