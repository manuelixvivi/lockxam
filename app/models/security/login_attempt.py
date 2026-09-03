from datetime import datetime, timezone

from sqlalchemy import Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LoginAttempt(Base):

    __tablename__ = "login_attempts"
    __table_args__ = (
        Index("ix_login_attempts_ip_user", "ip_address", "username"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ip_address: Mapped[str] = mapped_column(String(100), index=True)
    username: Mapped[str] = mapped_column(String(255), index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    blocked_until: Mapped[datetime | None] = mapped_column(nullable=True)
    last_attempt_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
