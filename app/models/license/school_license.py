from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common.public_id import PublicIdMixin
from app.models.common.timestamp import TimestampMixin


class SchoolLicense(TimestampMixin, PublicIdMixin, Base):
    __tablename__ = "school_licenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    license_type_id: Mapped[int] = mapped_column(ForeignKey("license_types.id"))
    activation_key_id: Mapped[int | None] = mapped_column(
        ForeignKey("activation_keys.id"), nullable=True, unique=True
    )

    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    max_users: Mapped[int]
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE")

    # Relationships
    school = relationship("School")
    license_type = relationship("LicenseType")
    activation_key = relationship("ActivationKey")
