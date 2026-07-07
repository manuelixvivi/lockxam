from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class School(Base):

    __tablename__ = "schools"

    id: Mapped[int] = mapped_column(primary_key=True)

    public_id: Mapped[UUID]

    code: Mapped[str] = mapped_column(String(20), unique=True)

    name: Mapped[str] = mapped_column(String(255))

    address: Mapped[str | None] = mapped_column(Text)

    phone: Mapped[str | None]

    email: Mapped[str | None]

    logo_url: Mapped[str | None]

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime]

    updated_at: Mapped[datetime]
