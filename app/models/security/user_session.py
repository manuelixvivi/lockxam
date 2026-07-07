from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserSession(Base):

    __tablename__ = "user_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True)

    auth_account_id: Mapped[int] = mapped_column(ForeignKey("auth_accounts.id", ondelete="CASCADE"))

    access_token_jti: Mapped[UUID]

    refresh_token_jti: Mapped[UUID]

    device_name: Mapped[str | None] = mapped_column(String(255))

    device_type: Mapped[str | None] = mapped_column(String(50))

    ip_address: Mapped[str | None]

    user_agent: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime]

    last_activity_at: Mapped[datetime]

    expires_at: Mapped[datetime]

    revoked: Mapped[bool]

    revoked_at: Mapped[datetime | None]

    revoked_reason: Mapped[str | None]
