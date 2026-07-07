from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuthAccount(Base):

    __tablename__ = "auth_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)

    public_id: Mapped[UUID]

    school_id: Mapped[int | None] = mapped_column(ForeignKey("schools.id"))

    username: Mapped[str] = mapped_column(String(255), unique=True)

    password_hash: Mapped[str]

    role: Mapped[str]

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    last_login: Mapped[datetime | None]

    created_at: Mapped[datetime]

    updated_at: Mapped[datetime]
