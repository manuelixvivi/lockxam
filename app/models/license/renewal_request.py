from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common.public_id import PublicIdMixin
from app.models.common.timestamp import TimestampMixin


class RenewalRequest(TimestampMixin, PublicIdMixin, Base):
    __tablename__ = "renewal_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    requested_by_id: Mapped[int] = mapped_column(ForeignKey("auth_accounts.id"))
    license_type_id: Mapped[int] = mapped_column(ForeignKey("license_types.id"))

    status: Mapped[str] = mapped_column(String(50), default="REQUESTED")
    payment_proof_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    superadmin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    processed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("auth_accounts.id"), nullable=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    school = relationship("School")
    requested_by = relationship("AuthAccount", foreign_keys=[requested_by_id])
    license_type = relationship("LicenseType")
    processed_by = relationship("AuthAccount", foreign_keys=[processed_by_id])
