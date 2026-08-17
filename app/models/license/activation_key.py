from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common.public_id import PublicIdMixin
from app.models.common.timestamp import TimestampMixin


class ActivationKey(TimestampMixin, PublicIdMixin, Base):
    __tablename__ = "activation_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    license_type_id: Mapped[int] = mapped_column(ForeignKey("license_types.id"))
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"))
    generated_by_id: Mapped[int] = mapped_column(ForeignKey("auth_accounts.id"))

    used_by_id: Mapped[int | None] = mapped_column(ForeignKey("auth_accounts.id"), nullable=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    cancelled_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("auth_accounts.id"), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(50), default="GENERATED")

    # Relationships
    license_type = relationship("LicenseType")
    school = relationship("School", foreign_keys=[school_id])
    generated_by = relationship("AuthAccount", foreign_keys=[generated_by_id])
    used_by = relationship("AuthAccount", foreign_keys=[used_by_id])
    cancelled_by = relationship("AuthAccount", foreign_keys=[cancelled_by_id])
