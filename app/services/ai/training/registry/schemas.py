from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class FileChecksum(BaseModel):
    """
    Cryptographic SHA-256 Checksum record for an individual artifact file.
    """

    model_config = ConfigDict(frozen=True)

    relative_path: str = Field(
        ..., description="Canonical relative path with forward slashes (e.g. 'adapter_config.json')"
    )
    file_size_bytes: int = Field(..., description="Exact file size in bytes")
    sha256_hash: str = Field(..., description="SHA-256 hash formatted as 'sha256:<hex>'")


class ModelArtifactManifest(BaseModel):
    """
    Milestone A9.4.2: Comprehensive Cryptographic Model Artifact Manifest.
    Guarantees 100% deterministic reproducibility, provenance tracking, and tampering detection.
    """

    model_config = ConfigDict(frozen=True)

    manifest_version: str = Field(default="1.0.0", description="Schema version of this manifest")
    model_name: str = Field(
        ..., description="Canonical RegisteredModel name (e.g. 'equigrade-essay-grader')"
    )
    version: str = Field(..., description="Version string identifier (e.g. 'v1')")
    version_number: int = Field(..., description="Sequential integer version counter (e.g. 1)")

    # Provenance Lineage
    training_job_id: str = Field(..., description="Canonical TrainingJob ID from A9.3")
    training_run_id: str = Field(..., description="Training run ID")
    experiment_id: str = Field(
        ..., description="Experiment condition ID (e.g. 'E2_FineTuned_Base')"
    )
    dataset_version_tag: str = Field(..., description="Frozen DatasetVersion tag from A8")
    dataset_hash: str = Field(..., description="Cryptographic dataset hash from A8")
    base_model_name: str = Field(..., description="Base pretrained model name/identifier")
    base_model_revision: Optional[str] = Field(
        default=None, description="Base model git revision or commit hash"
    )
    tokenizer_name_or_path: str = Field(..., description="Tokenizer identifier")
    adapter_type: str = Field(
        default="LORA", description="Fine-tuning adapter architecture (LORA/QLORA)"
    )
    adapter_config_hash: str = Field(..., description="SHA-256 of adapter_config.json")

    # Storage & Cryptographic Merkle Tree Hash
    artifact_uri: str = Field(..., description="Root URI/path where artifact files are located")
    artifact_manifest_hash: str = Field(
        ..., description="Deterministic cumulative SHA-256 Merkle tree hash of all artifact files"
    )
    file_manifest: List[FileChecksum] = Field(
        ..., description="Alphabetically sorted list of all file checksums"
    )

    # Timestamps & Metadata
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="UTC creation timestamp"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional custom metadata")


class IntegrityVerificationResult(BaseModel):
    """
    Output of cryptographic artifact integrity verification.
    """

    is_valid: bool = Field(
        ..., description="True if all files exist with matching hashes and no tampering is detected"
    )
    artifact_manifest_hash: str = Field(..., description="Computed Merkle tree hash")
    expected_manifest_hash: str = Field(
        ..., description="Expected Merkle tree hash from registered manifest"
    )
    total_files_checked: int = Field(..., description="Number of verified files")
    mismatched_files: List[str] = Field(
        default_factory=list, description="List of corrupted files with hash mismatches"
    )
    missing_files: List[str] = Field(
        default_factory=list, description="List of expected files missing on disk"
    )
    unauthorized_files: List[str] = Field(
        default_factory=list, description="List of unexpected files found in artifact directory"
    )
    error_message: Optional[str] = Field(
        default=None, description="Detailed diagnostic error message if invalid"
    )
