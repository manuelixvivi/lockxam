import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from app.services.ai.training.registry.schemas import (
    FileChecksum,
    IntegrityVerificationResult,
    ModelArtifactManifest,
)

logger = logging.getLogger(__name__)


class ModelArtifactBuilder:
    """
    Milestone A9.4.2: Model Artifact Builder & Cryptographic Manifest Generator.
    Builds reproducible, tamper-evident ModelArtifactManifest payloads with deterministic
    Merkle tree hashing across all model weights, adapter configs, and tokenizer artifacts.
    """

    EXCLUDE_FILE_NAMES: Set[str] = {
        ".ds_store",
        "thumbs.db",
        "desktop.ini",
        ".gitkeep",
        "model_manifest.json",  # Excluded from tree hash to avoid circular dependency
    }

    EXCLUDE_EXTENSIONS: Set[str] = {
        ".tmp",
        ".pyc",
        ".pyo",
        ".log",
    }

    EXCLUDE_DIR_NAMES: Set[str] = {
        "__pycache__",
        ".pytest_cache",
        ".git",
        ".idea",
        ".vscode",
    }

    @classmethod
    def compute_file_sha256(cls, file_path: str) -> str:
        """
        Computes streaming SHA-256 hash for an individual file.
        Returns format 'sha256:<hex>'.
        """
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return f"sha256:{hasher.hexdigest()}"

    @classmethod
    def scan_and_hash_directory(
        cls, root_dir: str
    ) -> Tuple[List[FileChecksum], str, Optional[str]]:
        """
        Scans an artifact directory, filters out OS/transient noise, normalizes paths to canonical
        forward slashes, sorts alphabetically, computes individual file SHA-256 checksums,
        and generates the cumulative Merkle tree hash.

        Returns:
            (sorted_file_checksums, cumulative_merkle_tree_hash, adapter_config_hash)
        """
        if not os.path.exists(root_dir) or not os.path.isdir(root_dir):
            raise FileNotFoundError(
                f"Artifact directory '{root_dir}' does not exist or is not a directory."
            )

        file_records: List[FileChecksum] = []
        adapter_config_hash: Optional[str] = None

        for current_root, dirs, files in os.walk(root_dir):
            # Prune excluded directories in-place
            dirs[:] = [
                d for d in dirs if d.lower() not in cls.EXCLUDE_DIR_NAMES and not d.startswith(".")
            ]

            for file_name in files:
                file_lower = file_name.lower()
                ext_lower = os.path.splitext(file_name)[1].lower()

                if file_lower in cls.EXCLUDE_FILE_NAMES or ext_lower in cls.EXCLUDE_EXTENSIONS:
                    continue

                full_path = os.path.join(current_root, file_name)
                canonical_rel_path = os.path.relpath(full_path, root_dir).replace("\\", "/")
                file_size = os.path.getsize(full_path)
                file_hash = cls.compute_file_sha256(full_path)

                checksum_record = FileChecksum(
                    relative_path=canonical_rel_path,
                    file_size_bytes=file_size,
                    sha256_hash=file_hash,
                )
                file_records.append(checksum_record)

                if canonical_rel_path == "adapter_config.json":
                    adapter_config_hash = file_hash

        if not file_records:
            raise ValueError(f"Artifact directory '{root_dir}' contains no valid model files.")

        # Canonical deterministic alphabetical sort by relative path
        sorted_records = sorted(file_records, key=lambda x: x.relative_path)

        # Compute cumulative Merkle tree hash
        cumulative_payload = "\n".join(
            f"{item.relative_path}:{item.sha256_hash}:{item.file_size_bytes}"
            for item in sorted_records
        )
        merkle_tree_hash = (
            f"sha256:{hashlib.sha256(cumulative_payload.encode('utf-8')).hexdigest()}"
        )

        return sorted_records, merkle_tree_hash, adapter_config_hash

    @classmethod
    def build_manifest(
        cls,
        model_name: str,
        version: str,
        version_number: int,
        training_job_id: str,
        training_run_id: str,
        experiment_id: str,
        dataset_version_tag: str,
        dataset_hash: str,
        base_model_name: str,
        base_model_revision: Optional[str],
        tokenizer_name_or_path: str,
        adapter_type: str,
        artifact_dir: str,
        artifact_uri: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ModelArtifactManifest:
        """
        Scans the artifact directory, generates cryptographic checksums, and constructs
        a complete immutable ModelArtifactManifest instance.
        """
        file_records, merkle_hash, adapter_cfg_hash = cls.scan_and_hash_directory(artifact_dir)

        # Enforce adapter_config.json presence for LoRA/QLoRA artifacts
        if adapter_type.upper() in ("LORA", "QLORA") and not adapter_cfg_hash:
            raise FileNotFoundError(
                f"Missing required 'adapter_config.json' for {adapter_type} model artifact in '{artifact_dir}'."
            )

        final_adapter_cfg_hash = adapter_cfg_hash or merkle_hash

        manifest = ModelArtifactManifest(
            model_name=model_name,
            version=version,
            version_number=version_number,
            training_job_id=training_job_id,
            training_run_id=training_run_id,
            experiment_id=experiment_id,
            dataset_version_tag=dataset_version_tag,
            dataset_hash=dataset_hash,
            base_model_name=base_model_name,
            base_model_revision=base_model_revision,
            tokenizer_name_or_path=tokenizer_name_or_path,
            adapter_type=adapter_type,
            adapter_config_hash=final_adapter_cfg_hash,
            artifact_uri=artifact_uri or artifact_dir.replace("\\", "/"),
            artifact_manifest_hash=merkle_hash,
            file_manifest=file_records,
            created_at=datetime.now(timezone.utc),
            metadata=metadata or {},
        )

        return manifest

    @classmethod
    def save_manifest_to_artifact_dir(
        cls, manifest: ModelArtifactManifest, artifact_dir: str
    ) -> str:
        """
        Serializes and saves `model_manifest.json` into the artifact directory.
        Returns the absolute path of the written manifest.
        """
        os.makedirs(artifact_dir, exist_ok=True)
        manifest_path = os.path.join(artifact_dir, "model_manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write(manifest.model_dump_json(indent=2))
        logger.info(
            f"Saved model manifest to '{manifest_path}' with Merkle hash '{manifest.artifact_manifest_hash}'."
        )
        return manifest_path

    @classmethod
    def verify_artifact_integrity(
        cls,
        artifact_dir: str,
        expected_manifest_hash: str,
        expected_file_manifest: Optional[List[FileChecksum]] = None,
    ) -> IntegrityVerificationResult:
        """
        Verifies the cryptographic integrity of an artifact directory against expected Merkle tree hash
        and optional individual file checksums. Detects bit rot, file deletion, modification, and tampering.
        """
        try:
            current_records, current_merkle_hash, _ = cls.scan_and_hash_directory(artifact_dir)
        except Exception as e:
            return IntegrityVerificationResult(
                is_valid=False,
                artifact_manifest_hash="",
                expected_manifest_hash=expected_manifest_hash,
                total_files_checked=0,
                error_message=f"Failed to scan artifact directory: {e}",
            )

        current_map = {item.relative_path: item for item in current_records}
        mismatched_files: List[str] = []
        missing_files: List[str] = []
        unauthorized_files: List[str] = []

        if expected_file_manifest:
            expected_map = {item.relative_path: item for item in expected_file_manifest}

            # Check expected files against current files
            for rel_path, exp_item in expected_map.items():
                if rel_path not in current_map:
                    missing_files.append(rel_path)
                else:
                    curr_item = current_map[rel_path]
                    if (
                        curr_item.sha256_hash != exp_item.sha256_hash
                        or curr_item.file_size_bytes != exp_item.file_size_bytes
                    ):
                        mismatched_files.append(rel_path)

            # Check for unauthorized extra files
            for rel_path in current_map:
                if rel_path not in expected_map:
                    unauthorized_files.append(rel_path)

        hash_matches = current_merkle_hash == expected_manifest_hash
        has_errors = bool(
            mismatched_files or missing_files or unauthorized_files or not hash_matches
        )

        error_msg = None
        if has_errors:
            reasons = []
            if not hash_matches:
                reasons.append(
                    f"Merkle hash mismatch (expected '{expected_manifest_hash}', computed '{current_merkle_hash}')"
                )
            if mismatched_files:
                reasons.append(f"Modified/corrupted files: {mismatched_files}")
            if missing_files:
                reasons.append(f"Missing files: {missing_files}")
            if unauthorized_files:
                reasons.append(f"Unauthorized extra files: {unauthorized_files}")
            error_msg = "; ".join(reasons)

        return IntegrityVerificationResult(
            is_valid=not has_errors,
            artifact_manifest_hash=current_merkle_hash,
            expected_manifest_hash=expected_manifest_hash,
            total_files_checked=len(current_records),
            mismatched_files=mismatched_files,
            missing_files=missing_files,
            unauthorized_files=unauthorized_files,
            error_message=error_msg,
        )
