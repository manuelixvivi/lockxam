from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.common.public_id import PublicIdMixin
from app.models.common.timestamp import TimestampMixin
from app.models.security.enums import UserRole


class AuthAccount(TimestampMixin, PublicIdMixin, Base):

    __tablename__ = "auth_accounts"
    __table_args__ = (
        Index("ix_auth_accounts_school_role", "school_id", "role"),
        Index("ix_auth_accounts_school_role_created", "school_id", "role", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    school_id: Mapped[int | None] = mapped_column(ForeignKey("schools.id"))

    username: Mapped[str] = mapped_column(String(255), unique=True)

    password_hash: Mapped[str]

    role: Mapped[str] = mapped_column(String(50), default=UserRole.ADMIN)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    last_login: Mapped[datetime | None] = mapped_column(nullable=True)

    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    # Student Profile Fields
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nis: Mapped[str | None] = mapped_column(String(50), nullable=True)
    nisn: Mapped[str | None] = mapped_column(String(50), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    class_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    registered_year: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Teacher Profile Fields (DEPRECATED/DERIVED: Read-only compatibility projection. TeacherSubject table is ONLY source of truth)
    nip: Mapped[str | None] = mapped_column(String(50), nullable=True)
    teacher_code: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    classes_taught: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    subjects_taught: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
