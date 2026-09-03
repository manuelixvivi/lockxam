from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base

if TYPE_CHECKING:
    pass


class ModelVersionStatus(str, Enum):
    """
    EquiGrade Model Version Lifecycle States — Milestone A9.4
    """

    REGISTERED = "REGISTERED"
    VALIDATING = "VALIDATING"
    VALIDATED = "VALIDATED"
    STAGED = "STAGED"
    PRODUCTION = "PRODUCTION"
    ARCHIVED = "ARCHIVED"
    REJECTED = "REJECTED"


class ModelVersion(Base):
    """
    EquiGrade ModelVersion — Milestone A9.4.1
    Immutable model artifact version entity in the Model Registry.
    Tracks lineage (TrainingJob, Run, Dataset, Base Model, Tokenizer),
    cryptographic manifest hash, lifecycle states, and promotion audit trail.
    """

    __tablename__ = "model_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(
        Integer, ForeignKey("registered_models.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    version = Column(String(32), nullable=False)  # e.g., "v1", "v2", "v3"
    version_number = Column(Integer, nullable=False)  # 1, 2, 3...
    status = Column(
        String(32), default=ModelVersionStatus.REGISTERED.value, nullable=False, index=True
    )

    # Lineage Links
    training_job_id = Column(
        Integer, ForeignKey("training_jobs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    training_run_id = Column(String(128), nullable=False)
    experiment_id = Column(String(128), nullable=False)
    dataset_version_tag = Column(String(128), nullable=False)
    dataset_hash = Column(String(128), nullable=False)
    base_model_name = Column(String(255), nullable=False)
    base_model_revision = Column(String(128), nullable=True)
    tokenizer_name_or_path = Column(String(255), nullable=False)
    adapter_type = Column(String(32), default="LORA", nullable=False)
    adapter_config_hash = Column(String(128), nullable=False)

    # Storage & Cryptographic Verification
    artifact_uri = Column(String(512), nullable=False)
    artifact_manifest_hash = Column(
        String(128), nullable=False
    )  # SHA-256 Merkle-style cumulative hash
    model_manifest_payload = Column(JSON, nullable=False)
    validation_report_payload = Column(JSON, nullable=True)
    promotion_history = Column(JSON, nullable=False, default=list)

    # Multi-tenant isolation
    school_id = Column(
        Integer, ForeignKey("schools.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    created_by_user_id = Column(
        Integer, ForeignKey("auth_accounts.id", ondelete="RESTRICT"), nullable=True
    )

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    promoted_at = Column(DateTime(timezone=True), nullable=True)
    archived_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    model = relationship("RegisteredModel", back_populates="versions", foreign_keys=[model_id])
    training_job = relationship("TrainingJob", foreign_keys=[training_job_id])

    __table_args__ = (
        UniqueConstraint("model_id", "version", name="uq_model_versions_model_version"),
        UniqueConstraint(
            "model_id", "version_number", name="uq_model_versions_model_version_number"
        ),
    )

    def __repr__(self) -> str:
        return f"<ModelVersion id={self.id} model_id={self.model_id} version='{self.version}' status='{self.status}'>"


IMMUTABLE_MODEL_VERSION_FIELDS = {
    "version",
    "version_number",
    "training_job_id",
    "training_run_id",
    "experiment_id",
    "dataset_version_tag",
    "dataset_hash",
    "base_model_name",
    "base_model_revision",
    "tokenizer_name_or_path",
    "adapter_type",
    "adapter_config_hash",
    "artifact_uri",
    "artifact_manifest_hash",
    "model_manifest_payload",
    "model_id",
    "school_id",
    "created_by_user_id",
    "created_at",
}


from sqlalchemy import event
from sqlalchemy.orm.attributes import get_history


@event.listens_for(ModelVersion, "before_update")
def enforce_model_version_immutability(mapper, connection, target: ModelVersion):
    """
    Enforces that artifact identity and historical lineage fields on ModelVersion cannot be mutated.
    Only lifecycle fields (status, validation_report_payload, promotion_history, promoted_at, archived_at)
    may be updated during model evaluation and promotion.
    """
    for field in IMMUTABLE_MODEL_VERSION_FIELDS:
        hist = get_history(target, field)
        if hist.has_changes():
            raise ValueError(
                f"Mutation prohibited: ModelVersion field '{field}' is immutable and cannot be updated after registration."
            )
