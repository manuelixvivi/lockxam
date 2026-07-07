from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LicenseType(Base):
    __tablename__ = "license_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    code: Mapped[str] = mapped_column(String(50), unique=True)
    duration_days: Mapped[int]
    max_users: Mapped[int]
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
