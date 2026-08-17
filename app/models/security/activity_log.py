from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ActivityLog(Base):

    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    auth_account_id: Mapped[int] = mapped_column(ForeignKey("auth_accounts.id", ondelete="CASCADE"))

    school_id: Mapped[int | None] = mapped_column(
        ForeignKey("schools.id", ondelete="SET NULL"), nullable=True
    )

    session_id: Mapped[UUID | None] = mapped_column(nullable=True)

    action_type: Mapped[str] = mapped_column(String(50))

    action_name: Mapped[str] = mapped_column(String(100))

    endpoint: Mapped[str | None] = mapped_column(String(255), nullable=True)

    method: Mapped[str | None] = mapped_column(String(10), nullable=True)

    ip_address: Mapped[str | None] = mapped_column(String(100), nullable=True)

    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    meta_data: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
