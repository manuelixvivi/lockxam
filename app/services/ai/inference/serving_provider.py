import logging
import os
from typing import Optional

from sqlalchemy.orm import Session

from app.models.ai.model_version import ModelVersion, ModelVersionStatus
from app.models.ai.registered_model import RegisteredModel
from app.repositories.ai.model_version_repository import model_version_repository
from app.repositories.ai.registered_model_repository import registered_model_repository
from app.services.ai.inference.bundle import InferenceBundle, ServingExecutionContract
from app.services.ai.training.registry.schemas import FileChecksum

logger = logging.getLogger(__name__)


class ModelServingProvider:
    """
    Milestone A9.4.4: Model Serving Provider.
    Resolves active PRODUCTION and STAGED InferenceBundles from RegisteredModel pointers,
    enforces dynamic base model provenance, and guarantees cryptographic integrity checks
    before any inference runtime is initialized.
    """

    def get_active_model_bundle(
        self,
        db: Session,
        model_name: str,
        school_id: Optional[int] = None,
        stage: str = "PRODUCTION",
        local_artifact_root: Optional[str] = None,
        contract: Optional[ServingExecutionContract] = None,
    ) -> InferenceBundle:
        """
        Resolves the currently active PRODUCTION or STAGED model version pointer
        and returns a cryptographically verified InferenceBundle ready for serving.
        """
        stage_upper = stage.upper()
        if stage_upper not in ("PRODUCTION", "STAGED"):
            raise ValueError(f"Invalid serving stage '{stage}'. Must be 'PRODUCTION' or 'STAGED'.")

        model = registered_model_repository.get_by_name(db, model_name, school_id=school_id)
        if not model:
            raise FileNotFoundError(
                f"RegisteredModel '{model_name}' not found for school_id={school_id}."
            )

        version_id = (
            model.active_production_version_id
            if stage_upper == "PRODUCTION"
            else model.active_staged_version_id
        )
        if not version_id:
            raise ValueError(
                f"No active {stage_upper} version configured for model '{model_name}'."
            )

        version = model_version_repository.get_by_id(db, version_id, school_id=school_id)
        if not version:
            raise FileNotFoundError(
                f"Active {stage_upper} ModelVersion with ID {version_id} not found."
            )

        # Enforce parent-child ownership
        if version.model_id != model.id:
            raise PermissionError(
                f"Pointer corruption: Version {version.id} does not belong to Model {model.id}."
            )

        return self._build_and_verify_bundle(
            model=model,
            version=version,
            local_artifact_root=local_artifact_root,
            contract=contract,
        )

    def get_version_bundle(
        self,
        db: Session,
        model_name: str,
        version_str: str,
        school_id: Optional[int] = None,
        local_artifact_root: Optional[str] = None,
        contract: Optional[ServingExecutionContract] = None,
    ) -> InferenceBundle:
        """
        Resolves a specific version (e.g. 'v1', 'v2') of a registered model for benchmark evaluation.
        """
        model = registered_model_repository.get_by_name(db, model_name, school_id=school_id)
        if not model:
            raise FileNotFoundError(
                f"RegisteredModel '{model_name}' not found for school_id={school_id}."
            )

        version = model_version_repository.get_by_model_and_version(
            db=db, model_id=model.id, version=version_str, school_id=school_id
        )
        if not version:
            raise FileNotFoundError(
                f"ModelVersion '{version_str}' not found for model '{model_name}'."
            )

        if version.status in (
            ModelVersionStatus.REJECTED.value,
            ModelVersionStatus.REGISTERED.value,
        ):
            raise ValueError(
                f"Cannot serve unvalidated or rejected version '{version_str}' (status: {version.status})."
            )

        return self._build_and_verify_bundle(
            model=model,
            version=version,
            local_artifact_root=local_artifact_root,
            contract=contract,
        )

    def _build_and_verify_bundle(
        self,
        model: RegisteredModel,
        version: ModelVersion,
        local_artifact_root: Optional[str] = None,
        contract: Optional[ServingExecutionContract] = None,
    ) -> InferenceBundle:
        """Helper to parse manifest file records, construct InferenceBundle, and verify integrity."""
        raw_manifest = version.model_manifest_payload or {}
        raw_file_manifest = raw_manifest.get("file_manifest", [])
        file_manifest = [
            FileChecksum(
                relative_path=item["relative_path"],
                file_size_bytes=item["file_size_bytes"],
                sha256_hash=item["sha256_hash"],
            )
            for item in raw_file_manifest
        ]

        adapter_dir = local_artifact_root or version.artifact_uri
        bundle = InferenceBundle(
            model_name=model.name,
            version=version.version,
            version_number=version.version_number,
            status=version.status,
            base_model_name=version.base_model_name,
            base_model_revision=version.base_model_revision,
            tokenizer_name_or_path=version.tokenizer_name_or_path,
            adapter_type=version.adapter_type,
            adapter_dir=adapter_dir,
            artifact_manifest_hash=version.artifact_manifest_hash,
            file_manifest=file_manifest,
            contract=contract or ServingExecutionContract(),
            metadata=raw_manifest.get("metadata", {}),
        )

        # Real-time cryptographic integrity verification
        if os.path.exists(adapter_dir) and os.path.isdir(adapter_dir):
            integrity_res = bundle.verify_integrity()
            if not integrity_res.is_valid:
                raise ValueError(
                    f"InferenceBundle startup rejected: Cryptographic verification failed for model '{model.name}' {version.version}: {integrity_res.error_message}"
                )

        logger.info(
            f"Successfully resolved InferenceBundle for model '{model.name}' {version.version} "
            f"(base_model={version.base_model_name}, status={version.status})."
        )
        return bundle


model_serving_provider = ModelServingProvider()
