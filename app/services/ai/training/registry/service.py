import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.ai.model_version import ModelVersion, ModelVersionStatus
from app.models.ai.training_job import TrainingJob, TrainingJobStatus
from app.repositories.ai.model_version_repository import model_version_repository
from app.repositories.ai.registered_model_repository import registered_model_repository
from app.services.ai.training.registry.artifact_builder import ModelArtifactBuilder
from app.services.ai.training.registry.schemas import ModelArtifactManifest
from app.services.ai.training.registry.validation_gate import ModelValidationGate

logger = logging.getLogger(__name__)


class ModelRegistryService:
    """
    Milestone A9.4.3: Model Registry Service.
    Authoritative service managing the complete lifecycle of RegisteredModel entities and
    immutable ModelVersion artifacts: registration, cryptographic validation gates, staging,
    production promotion, and zero-downtime rollback.
    """

    def register_model_version(
        self,
        db: Session,
        model_name: str,
        training_job_id: int,
        base_artifact_dir: str,
        school_id: Optional[int] = None,
        created_by_user_id: Optional[int] = None,
        artifact_uri: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
    ) -> ModelVersion:
        """
        Registers a completed TrainingJob as an immutable ModelVersion under the canonical RegisteredModel.
        Handles version numbering concurrency and builds the cryptographic Merkle-style manifest.
        """
        # 1. Verify TrainingJob
        job = db.query(TrainingJob).filter(TrainingJob.id == training_job_id).first()
        if not job:
            raise FileNotFoundError(f"TrainingJob with ID {training_job_id} not found.")

        if school_id is not None and job.school_id != school_id:
            raise PermissionError(
                f"Tenant isolation violation: Job school_id ({job.school_id}) does not match caller school_id ({school_id})."
            )

        if job.status != TrainingJobStatus.COMPLETED:
            raise ValueError(
                f"Cannot register TrainingJob with status '{job.status}'. Only COMPLETED training jobs can be registered."
            )

        # 2. Retrieve or create parent RegisteredModel
        model = registered_model_repository.get_by_name(db, model_name, school_id=school_id)
        if not model:
            model = registered_model_repository.create(
                db=db,
                name=model_name,
                display_name=model_name.replace("-", " ").title(),
                school_id=school_id,
                created_by_user_id=created_by_user_id,
            )
            db.commit()

        # 3. Concurrency retry loop for sequential version generation
        for attempt in range(max_retries):
            try:
                next_version_num = model_version_repository.get_next_version_number(db, model.id)
                version_str = f"v{next_version_num}"

                # Extract tokenizer & model revision from training provenance or job configuration
                resolved_tokenizer = getattr(job, "tokenizer_name_or_path", None) or getattr(
                    job, "tokenizer_name", None
                )
                resolved_revision = getattr(job, "base_model_revision", None)

                if hasattr(job, "training_config") and isinstance(job.training_config, dict):
                    if not resolved_tokenizer:
                        resolved_tokenizer = job.training_config.get(
                            "tokenizer_name"
                        ) or job.training_config.get("tokenizer_name_or_path")
                    if not resolved_revision:
                        resolved_revision = job.training_config.get(
                            "base_model_revision"
                        ) or job.training_config.get("model_revision")

                prov_path = os.path.join(base_artifact_dir, "training_provenance.json")
                if os.path.exists(prov_path):
                    try:
                        with open(prov_path, "r", encoding="utf-8") as pf:
                            p_data = json.load(pf)
                            if not resolved_tokenizer:
                                resolved_tokenizer = p_data.get("tokenizer_name") or p_data.get(
                                    "tokenizer_name_or_path"
                                )
                            if not resolved_revision:
                                resolved_revision = p_data.get("base_model_revision") or p_data.get(
                                    "model_revision"
                                )
                    except Exception:
                        pass

                if not resolved_tokenizer:
                    resolved_tokenizer = job.base_model_name

                # Build cryptographic manifest
                manifest: ModelArtifactManifest = ModelArtifactBuilder.build_manifest(
                    model_name=model.name,
                    version=version_str,
                    version_number=next_version_num,
                    training_job_id=job.job_id,
                    training_run_id=job.current_run_id,
                    experiment_id=job.experiment_id,
                    dataset_version_tag=job.dataset_version_tag,
                    dataset_hash=job.dataset_hash,
                    base_model_name=job.base_model_name,
                    base_model_revision=resolved_revision,
                    tokenizer_name_or_path=resolved_tokenizer,
                    adapter_type="LORA",
                    artifact_dir=base_artifact_dir,
                    artifact_uri=artifact_uri or base_artifact_dir.replace("\\", "/"),
                    metadata=metadata or {},
                )

                # Persist model_manifest.json in artifact directory
                ModelArtifactBuilder.save_manifest_to_artifact_dir(manifest, base_artifact_dir)

                model_version = ModelVersion(
                    model_id=model.id,
                    version=version_str,
                    version_number=next_version_num,
                    status=ModelVersionStatus.REGISTERED.value,
                    training_job_id=job.id,
                    training_run_id=job.current_run_id,
                    experiment_id=job.experiment_id,
                    dataset_version_tag=job.dataset_version_tag,
                    dataset_hash=job.dataset_hash,
                    base_model_name=job.base_model_name,
                    base_model_revision=resolved_revision,
                    tokenizer_name_or_path=resolved_tokenizer,
                    adapter_type="LORA",
                    adapter_config_hash=manifest.adapter_config_hash,
                    artifact_uri=manifest.artifact_uri,
                    artifact_manifest_hash=manifest.artifact_manifest_hash,
                    model_manifest_payload=manifest.model_dump(mode="json"),
                    school_id=school_id,
                    created_by_user_id=created_by_user_id,
                )

                created_version = model_version_repository.create(db, model_version)
                db.commit()
                db.refresh(created_version)
                logger.info(
                    f"Successfully registered ModelVersion '{created_version.version}' (ID={created_version.id}) for model '{model.name}'."
                )
                return created_version
            except IntegrityError as e:
                db.rollback()
                if attempt == max_retries - 1:
                    raise RuntimeError(
                        f"Failed to allocate sequential version for model '{model.name}' after {max_retries} attempts: {e}"
                    )
                logger.warning(f"Version race condition on attempt {attempt + 1}, retrying...")

        raise RuntimeError(f"Unexpected termination during registration of model '{model.name}'.")

    def validate_model_version(
        self,
        db: Session,
        model_version_id: int,
        artifact_dir: str,
        school_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> Tuple[bool, ModelVersion]:
        """
        Executes the ModelValidationGate suite on the registered artifact.
        Transitions status: REGISTERED -> VALIDATING -> VALIDATED (or REJECTED).
        """
        version = model_version_repository.get_by_id(db, model_version_id, school_id=school_id)
        if not version:
            raise FileNotFoundError(f"ModelVersion with ID {model_version_id} not found.")

        # Transition to VALIDATING
        model_version_repository.update_status(
            db=db,
            version_id=version.id,
            new_status=ModelVersionStatus.VALIDATING,
            user_id=user_id,
            reason="Starting automated validation gate checks",
        )
        db.commit()

        # Run Validation Gate
        passed, report, error_msg = ModelValidationGate.validate_artifact(
            artifact_dir=artifact_dir,
            expected_manifest_hash=version.artifact_manifest_hash,
            adapter_type=version.adapter_type,
        )

        final_status = ModelVersionStatus.VALIDATED if passed else ModelVersionStatus.REJECTED
        reason = (
            "Passed all automated validation gate checks"
            if passed
            else f"Validation failed: {error_msg}"
        )

        version.validation_report_payload = report
        model_version_repository.update_status(
            db=db,
            version_id=version.id,
            new_status=final_status,
            user_id=user_id,
            reason=reason,
        )
        db.commit()
        db.refresh(version)

        logger.info(
            f"ModelVersion {version.id} validation finished: status={version.status}, passed={passed}"
        )
        return passed, version

    def promote_to_staged(
        self,
        db: Session,
        model_version_id: int,
        reason: str,
        user_id: Optional[int] = None,
        school_id: Optional[int] = None,
    ) -> ModelVersion:
        """
        Promotes a VALIDATED model version to STAGED and updates the RegisteredModel pointer.
        Ensures strict parent-child tenant consistency.
        """
        version = model_version_repository.get_by_id(db, model_version_id, school_id=school_id)
        if not version:
            raise FileNotFoundError(f"ModelVersion with ID {model_version_id} not found.")

        if version.status not in (
            ModelVersionStatus.VALIDATED.value,
            ModelVersionStatus.STAGED.value,
        ):
            raise ValueError(
                f"Cannot promote ModelVersion with status '{version.status}' to STAGED. Must be in VALIDATED state."
            )

        model = registered_model_repository.get_by_id(db, version.model_id, school_id=school_id)
        if not model:
            raise FileNotFoundError(f"Parent RegisteredModel with ID {version.model_id} not found.")

        # Ensure parent-child ownership
        if model.id != version.model_id:
            raise ValueError(
                f"ModelVersion {version.id} does not belong to RegisteredModel {model.id}."
            )

        # Update version status
        model_version_repository.update_status(
            db=db,
            version_id=version.id,
            new_status=ModelVersionStatus.STAGED,
            user_id=user_id,
            reason=reason,
        )

        # Update staged pointer on parent model
        registered_model_repository.update_pointers(
            db=db,
            model_id=model.id,
            active_staged_version_id=version.id,
            update_staged=True,
        )
        db.commit()
        db.refresh(version)
        return version

    def promote_to_production(
        self,
        db: Session,
        model_version_id: int,
        reason: str,
        user_id: Optional[int] = None,
        school_id: Optional[int] = None,
    ) -> ModelVersion:
        """
        Promotes a VALIDATED or STAGED model version to active PRODUCTION.
        Demotes previous active production version to ARCHIVED and updates RegisteredModel pointer.
        """
        version = model_version_repository.get_by_id(db, model_version_id, school_id=school_id)
        if not version:
            raise FileNotFoundError(f"ModelVersion with ID {model_version_id} not found.")

        if version.status not in (
            ModelVersionStatus.VALIDATED.value,
            ModelVersionStatus.STAGED.value,
            ModelVersionStatus.PRODUCTION.value,
        ):
            raise ValueError(
                f"Cannot promote ModelVersion with status '{version.status}' to PRODUCTION. Must be in VALIDATED or STAGED state."
            )

        model = registered_model_repository.get_by_id(db, version.model_id, school_id=school_id)
        if not model:
            raise FileNotFoundError(f"Parent RegisteredModel with ID {version.model_id} not found.")

        # Ensure parent-child ownership
        if model.id != version.model_id:
            raise ValueError(
                f"ModelVersion {version.id} does not belong to RegisteredModel {model.id}."
            )

        # Demote previous production version if different
        if model.active_production_version_id and model.active_production_version_id != version.id:
            prev_prod_id = model.active_production_version_id
            model_version_repository.update_status(
                db=db,
                version_id=prev_prod_id,
                new_status=ModelVersionStatus.ARCHIVED,
                user_id=user_id,
                reason=f"Superseded by {version.version} in production promotion",
            )

        # Update version status and promoted_at
        version.promoted_at = datetime.now(timezone.utc)
        model_version_repository.update_status(
            db=db,
            version_id=version.id,
            new_status=ModelVersionStatus.PRODUCTION,
            user_id=user_id,
            reason=reason,
        )

        # Update production pointer on parent model
        registered_model_repository.update_pointers(
            db=db,
            model_id=model.id,
            active_production_version_id=version.id,
            update_production=True,
        )
        db.commit()
        db.refresh(version)
        return version

    def rollback_production(
        self,
        db: Session,
        model_id: int,
        target_version_str: str,
        reason: str,
        user_id: Optional[int] = None,
        school_id: Optional[int] = None,
    ) -> ModelVersion:
        """
        Executes atomic zero-downtime rollback to a previous ModelVersion without altering immutable weights.
        Enforces strict parent-child relationship: target version MUST belong to the same RegisteredModel.
        """
        model = registered_model_repository.get_by_id(db, model_id, school_id=school_id)
        if not model:
            raise FileNotFoundError(f"RegisteredModel with ID {model_id} not found.")

        target_version = model_version_repository.get_by_model_and_version(
            db=db, model_id=model.id, version=target_version_str, school_id=school_id
        )
        if not target_version:
            raise FileNotFoundError(
                f"Target version '{target_version_str}' does not exist for model '{model.name}'."
            )

        # Verify parent-child relationship
        if target_version.model_id != model.id:
            raise PermissionError(
                f"Ownership violation: Target version {target_version.id} does not belong to model {model.id}."
            )

        # Target version must not be REJECTED or REGISTERED (unvalidated)
        if target_version.status in (
            ModelVersionStatus.REJECTED.value,
            ModelVersionStatus.REGISTERED.value,
        ):
            raise ValueError(
                f"Cannot rollback to version '{target_version_str}' with invalid status '{target_version.status}'."
            )

        # Demote current production version if different
        if (
            model.active_production_version_id
            and model.active_production_version_id != target_version.id
        ):
            curr_prod_id = model.active_production_version_id
            model_version_repository.update_status(
                db=db,
                version_id=curr_prod_id,
                new_status=ModelVersionStatus.ARCHIVED,
                user_id=user_id,
                reason=f"Demoted during rollback to {target_version_str}",
            )

        # Promote target version to PRODUCTION
        target_version.promoted_at = datetime.now(timezone.utc)
        model_version_repository.update_status(
            db=db,
            version_id=target_version.id,
            new_status=ModelVersionStatus.PRODUCTION,
            user_id=user_id,
            reason=f"Rollback to {target_version_str}: {reason}",
        )

        # Atomically switch production pointer to target version
        registered_model_repository.update_pointers(
            db=db,
            model_id=model.id,
            active_production_version_id=target_version.id,
            update_production=True,
        )
        db.commit()
        db.refresh(target_version)
        logger.info(
            f"Successfully rolled back model '{model.name}' to version '{target_version_str}'."
        )
        return target_version


model_registry_service = ModelRegistryService()
