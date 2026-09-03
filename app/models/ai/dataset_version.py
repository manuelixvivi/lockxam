from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.common.timestamp import TimestampMixin


class DatasetVersion(TimestampMixin, Base):
    """
    Milestone A8: Dataset Version Registry.
    Tracks curated training dataset releases with full data lineage, cryptographic SHA-256 identity,
    immutable frozen SFT payloads, leakage-free group split manifests, and quality score filters.
    """

    __tablename__ = "dataset_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    version_tag: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    task_type: Mapped[str] = mapped_column(
        String(50), default="ESSAY_GRADING", nullable=False
    )  # 'ESSAY_GRADING', 'RUBRIC_GENERATION', 'VALIDATION'
    split_strategy: Mapped[str] = mapped_column(
        String(50), default="QUESTION_GROUP_SPLIT", nullable=False
    )

    # Cryptographic Dataset Fingerprint for Scientific Reproducibility
    dataset_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    manifest_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # Sample Counts per Split
    total_samples: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    train_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    val_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    test_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Filter & Quality Parameters
    quality_threshold_applied: Mapped[float] = mapped_column(Float, default=0.70, nullable=False)

    # Manifest of Candidate IDs partitioned by split: {"train": [1, 2, ...], "val": [...], "test": [...]}
    split_manifest: Mapped[Dict[str, List[int]]] = mapped_column(JSON, nullable=False)
    candidate_ids: Mapped[List[int]] = mapped_column(JSON, nullable=False)

    # True Immutable Snapshot: Frozen SFT JSON Payloads per Split (Byte-exact Reproducibility)
    frozen_split_payloads: Mapped[Dict[str, List[Dict[str, Any]]]] = mapped_column(
        JSON, nullable=False
    )

    # Lineage & Tenant Isolation Metadata
    school_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    academic_year_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Statistical & Lineage Metadata
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
