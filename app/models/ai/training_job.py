from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common.timestamp import TimestampMixin


class TrainingJobStatus:
    QUEUED = "QUEUED"
    INITIALIZING = "INITIALIZING"
    PREFLIGHT_PASSED = "PREFLIGHT_PASSED"
    RUNNING = "RUNNING"
    EVALUATING = "EVALUATING"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    STALE = "STALE"
    RESUMING = "RESUMING"


class TrainingJob(TimestampMixin, Base):
    """
    Milestone A9.3: Training Job Orchestration Entity.
    Tracks declarative job configuration, run lifecycles, execution worker heartbeats,
    graceful cancellation, checkpoint paths, metrics, and multi-tenant isolation.
    """

    __tablename__ = "training_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    current_run_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    parent_run_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    experiment_id: Mapped[str] = mapped_column(
        String(64), index=True, default="E2_FineTuned_Base", nullable=False
    )

    # Lineage link to frozen DatasetVersion (RESTRICT on delete to protect authoritative lineage)
    dataset_version_id: Mapped[int] = mapped_column(
        ForeignKey("dataset_versions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    dataset_version_tag: Mapped[str] = mapped_column(String(64), nullable=False)
    dataset_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    base_model_name: Mapped[str] = mapped_column(String(128), nullable=False)

    # State Machine & Execution Mode
    status: Mapped[str] = mapped_column(
        String(32), default=TrainingJobStatus.QUEUED, index=True, nullable=False
    )
    execution_mode: Mapped[str] = mapped_column(String(32), default="CPU_TEST", nullable=False)
    worker_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failure_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Immutable Job Configuration & Artifact URI
    job_config_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    artifact_uri: Mapped[str] = mapped_column(String(255), nullable=False)

    # Real-Time Training Progress & Losses
    total_epochs: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    current_epoch: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    current_step: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_steps: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    train_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    eval_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    eval_perplexity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Checkpoint and Adapter Artifact Paths
    best_checkpoint_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    final_adapter_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Multi-Tenant & Actor Lineage
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("auth_accounts.id", ondelete="SET NULL"), nullable=True
    )
    school_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=True, index=True
    )

    # Execution Heartbeat & Timestamps
    last_heartbeat_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancel_requested_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationship to DatasetVersion
    dataset_version = relationship("DatasetVersion")
