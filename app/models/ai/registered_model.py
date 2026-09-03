from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base

if TYPE_CHECKING:
    pass


class RegisteredModel(Base):
    """
    EquiGrade RegisteredModel — Milestone A9.4.1
    Top-level logical model entity in the Model Registry.
    Tracks canonical model identity, metadata, tenant boundaries, and active deployment pointers
    (production and staging versions).
    """

    __tablename__ = "registered_models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), index=True, nullable=False)
    display_name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    task_type = Column(String(64), nullable=False, default="essay_grading")

    # Multi-tenant isolation: NULL means platform-wide default model, non-NULL means school-specific model
    school_id = Column(
        Integer, ForeignKey("schools.id", ondelete="RESTRICT"), nullable=True, index=True
    )

    # Active deployment pointers (decoupled from individual version state)
    active_production_version_id = Column(
        Integer,
        ForeignKey(
            "model_versions.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_registered_model_production_version",
        ),
        nullable=True,
    )
    active_staged_version_id = Column(
        Integer,
        ForeignKey(
            "model_versions.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_registered_model_staged_version",
        ),
        nullable=True,
    )

    created_by_user_id = Column(
        Integer, ForeignKey("auth_accounts.id", ondelete="RESTRICT"), nullable=True
    )
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    versions = relationship(
        "ModelVersion",
        back_populates="model",
        foreign_keys="ModelVersion.model_id",
        cascade="save-update, merge",
        passive_deletes=True,
        order_by="ModelVersion.version_number.desc()",
    )
    active_production_version = relationship(
        "ModelVersion",
        foreign_keys=[active_production_version_id],
        post_update=True,
    )
    active_staged_version = relationship(
        "ModelVersion",
        foreign_keys=[active_staged_version_id],
        post_update=True,
    )

    __table_args__ = (
        UniqueConstraint("name", "school_id", name="uq_registered_models_name_school"),
    )

    def __repr__(self) -> str:
        return f"<RegisteredModel id={self.id} name='{self.name}' school_id={self.school_id}>"
