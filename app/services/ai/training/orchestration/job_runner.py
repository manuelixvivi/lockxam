import logging
import math
import os
import uuid
from typing import Any, Dict, Optional, Union

from sqlalchemy.orm import Session

from app.models.ai.training_job import TrainingJob, TrainingJobStatus
from app.repositories.ai.dataset_version_repository import dataset_version_repository
from app.repositories.ai.training_job_repository import training_job_repository
from app.services.ai.training.datasets.loader import DatasetLoader
from app.services.ai.training.datasets.validator import (
    DatasetValidator,
    TrainingPreflightError,
)
from app.services.ai.training.lora.training_engine import (
    SftTrainingEngine,
    TrainingCancelledError,
    TrainingStepCalculator,
)
from app.services.ai.training.orchestration.artifact_store import (
    ArtifactSyncError,
    get_artifact_store,
)
from app.services.ai.training.orchestration.job_config import JobConfigParser
from app.services.ai.training.orchestration.manifest_builder import ManifestBuilder
from app.services.ai.training.orchestration.metrics_logger import MetricsLogger
from app.services.ai.training.schemas import JobConfigModel
from app.services.ai.training.tokenization.tokenization_config import (
    ExecutionMode,
    TokenizationConfig,
)

logger = logging.getLogger(__name__)


class JobRunner:
    """
    Milestone A9.3: Training Job Lifecycle & Orchestration Engine.
    Manages declarative job creation, pre-flight gate invocation, background execution,
    real-time stream metrics logging, accurate total_steps progress calculation,
    EVALUATING <-> RUNNING lifecycle transitions, remote checkpoint hydration,
    and strict cloud synchronization failure handling.
    """

    @classmethod
    def create_job(
        cls,
        db: Session,
        raw_config: Union[str, Dict[str, Any]],
        created_by_user_id: Optional[int] = None,
        school_id: Optional[int] = None,
        base_artifact_uri: str = "./runs",
    ) -> TrainingJob:
        """
        Parses configuration and creates a new TrainingJob in QUEUED state with tenant isolation.
        """
        job_config = JobConfigParser.parse_and_validate(raw_config)

        # Verify target dataset exists and matches tenant
        dv = dataset_version_repository.get_by_version_tag(db, job_config.dataset_version_tag)
        if not dv:
            raise ValueError(
                f"Target DatasetVersion '{job_config.dataset_version_tag}' does not exist."
            )

        if school_id is not None and dv.school_id is not None and dv.school_id != school_id:
            raise PermissionError(
                "Cross-tenant access violation: DatasetVersion belongs to a different school."
            )

        job_uuid = f"job_{uuid.uuid4().hex[:12]}"
        run_uuid = f"run_{uuid.uuid4().hex[:8]}"

        artifact_store = get_artifact_store(base_artifact_uri, job_uuid, run_uuid)

        # Save initial job config artifact to local working directory
        try:
            artifact_store.save_json("job_config.json", job_config.model_dump())
        except ArtifactSyncError:
            # Staged in local compute buffer; strict synchronization occurs during job execution
            pass

        job = TrainingJob(
            job_id=job_uuid,
            current_run_id=run_uuid,
            parent_run_id=None,
            experiment_id=job_config.experiment_id,
            dataset_version_id=dv.id,
            dataset_version_tag=dv.version_tag,
            dataset_hash=dv.dataset_hash,
            base_model_name=job_config.base_model_name,
            status=TrainingJobStatus.QUEUED,
            execution_mode=job_config.execution_mode,
            job_config_payload=job_config.model_dump(),
            artifact_uri=artifact_store.get_root_uri(),
            total_epochs=job_config.training.num_train_epochs,
            created_by_user_id=created_by_user_id,
            school_id=school_id,
        )

        saved_job = training_job_repository.create(db, job)
        logger.info(
            f"Created TrainingJob '{job_uuid}' (Run '{run_uuid}') for dataset '{dv.version_tag}'."
        )
        return saved_job

    @classmethod
    def start_job(
        cls,
        db: Session,
        job_id: str,
        school_id: Optional[int] = None,
        worker_id: Optional[str] = None,
        base_artifact_uri: str = "./runs",
    ) -> TrainingJob:
        """
        Executes complete training lifecycle: Pre-Flight Gate -> RUNNING -> EVALUATING -> RUNNING -> COMPLETED.
        """
        job = training_job_repository.get_by_job_id(db, job_id, school_id=school_id)
        if not job:
            raise ValueError(f"TrainingJob '{job_id}' not found or access denied.")

        # 0. Check if cancellation was requested before launch
        if job.status == TrainingJobStatus.CANCEL_REQUESTED:
            training_job_repository.update_status(
                db,
                job.job_id,
                TrainingJobStatus.CANCELLED,
                school_id=school_id,
                error_message="Cancelled by user before training launch.",
            )
            return job

        worker = worker_id or f"worker_{uuid.uuid4().hex[:6]}"

        # 1. State Transition: INITIALIZING with Atomic Concurrency Claim Lock
        claimed_job = training_job_repository.claim_and_initialize_job(
            db, job.job_id, worker_id=worker, school_id=school_id
        )
        if not claimed_job:
            raise RuntimeError(
                f"Concurrency conflict: TrainingJob '{job_id}' is in state '{job.status}' (already claimed by worker '{job.worker_id}')."
            )
        job = claimed_job
        job_config = JobConfigModel(**job.job_config_payload)
        artifact_store = get_artifact_store(base_artifact_uri, job.job_id, job.current_run_id)

        # Fetch DatasetVersion
        dv = dataset_version_repository.get_by_version_tag(db, job.dataset_version_tag)
        if not dv:
            training_job_repository.update_status(
                db,
                job.job_id,
                TrainingJobStatus.FAILED,
                school_id=school_id,
                error_message="DatasetVersion not found.",
                failure_code="DATASET_NOT_FOUND",
            )
            return job

        try:
            # 2. Build Training Manifest
            ManifestBuilder.build_and_save_manifest(
                job_id=job.job_id,
                run_id=job.current_run_id,
                job_config=job_config,
                dataset_version=dv,
                artifact_store=artifact_store,
                worker_id=worker,
                parent_run_id=job.parent_run_id,
                status=TrainingJobStatus.INITIALIZING,
            )

            # 3. Pre-Flight Gate Check (Milestone A9.1 Invariant)
            token_cfg = TokenizationConfig(
                model_name_or_path=job_config.base_model_name,
                execution_mode=job_config.execution_mode,
                use_real_tokenizer=(job_config.execution_mode != ExecutionMode.CPU_TEST),
            )
            DatasetValidator.assert_training_ready(db, dv.version_tag, token_cfg)
            training_job_repository.update_status(
                db, job.job_id, TrainingJobStatus.PREFLIGHT_PASSED, school_id=school_id
            )
        except TrainingPreflightError as pe:
            err_msg = f"Pre-flight gate failed: {pe}"
            logger.error(err_msg)
            training_job_repository.update_status(
                db,
                job.job_id,
                TrainingJobStatus.FAILED,
                school_id=school_id,
                error_message=err_msg,
                failure_code="PREFLIGHT_GATE_REJECTED",
            )
            return job
        except ArtifactSyncError as se:
            err_msg = f"Durable cloud artifact synchronization failure: {se}"
            logger.error(err_msg)
            training_job_repository.update_status(
                db,
                job.job_id,
                TrainingJobStatus.FAILED,
                school_id=school_id,
                error_message=err_msg,
                failure_code="ARTIFACT_SYNC_FAILED",
            )
            return job
        except Exception as ex:
            err_msg = f"Unexpected pre-flight exception: {ex}"
            logger.error(err_msg)
            training_job_repository.update_status(
                db,
                job.job_id,
                TrainingJobStatus.FAILED,
                school_id=school_id,
                error_message=err_msg,
                failure_code="PREFLIGHT_SYSTEM_ERROR",
            )
            return job

        # 4. Check for Graceful Cancellation Request before Launch
        if training_job_repository.is_cancellation_requested(db, job.job_id, school_id=school_id):
            training_job_repository.update_status(
                db,
                job.job_id,
                TrainingJobStatus.CANCELLED,
                school_id=school_id,
                error_message="Cancelled by user before training launch.",
            )
            return job

        # 5. State Transition: RUNNING
        training_job_repository.update_status(
            db, job.job_id, TrainingJobStatus.RUNNING, school_id=school_id
        )
        training_job_repository.update_heartbeat(
            db, job.job_id, worker_id=worker, school_id=school_id
        )

        # 6. Prepare Metrics Logger & Compute Exact Total Steps Ahead of Execution
        metrics_logger = MetricsLogger(artifact_store=artifact_store)

        training_run_output_dir = artifact_store.get_local_working_dir()
        training_args = job_config.training
        training_args.output_dir = training_run_output_dir

        # Calculate exact total training steps via shared TrainingStepCalculator
        train_samples_count = 0
        try:
            split_payloads = DatasetLoader.load_from_database(db, dv.version_tag, verify_hash=False)
            train_samples_count = len(split_payloads.get("train", []))
        except Exception:
            train_samples_count = getattr(dv, "train_samples_count", 0) or 10

        steps_per_epoch, total_calculated_steps = TrainingStepCalculator.calculate_steps(
            sample_count=train_samples_count,
            per_device_batch_size=training_args.per_device_train_batch_size,
            gradient_accumulation_steps=training_args.gradient_accumulation_steps,
            epochs=training_args.num_train_epochs,
        )

        # 7. Setup Live Callbacks
        def cancellation_checker() -> bool:
            return training_job_repository.is_cancellation_requested(
                db, job.job_id, school_id=school_id
            )

        def on_step_callback(
            step: int,
            epoch: float,
            train_loss: float,
            eval_loss: Optional[float],
            lr: float,
            grad_norm: Optional[float] = None,
            tokens_processed: Optional[int] = None,
            elapsed_seconds: Optional[float] = None,
        ):
            eval_ppl = round(math.exp(min(eval_loss, 20.0)), 4) if eval_loss is not None else None
            # Stream to metrics.jsonl
            metrics_logger.log_step(
                step=step,
                epoch=epoch,
                train_loss=train_loss,
                eval_loss=eval_loss,
                eval_perplexity=eval_ppl,
                learning_rate=lr,
                grad_norm=grad_norm,
                tokens_processed=tokens_processed,
                elapsed_seconds=elapsed_seconds,
            )
            # Update DB Progress & Heartbeat with pre-calculated total_steps
            training_job_repository.update_progress(
                db=db,
                job_id=job.job_id,
                current_epoch=epoch,
                current_step=step,
                total_steps=total_calculated_steps,
                school_id=school_id,
                train_loss=train_loss,
                eval_loss=eval_loss,
                eval_perplexity=eval_ppl,
            )

        def on_eval_start_callback(step: int, epoch: float):
            training_job_repository.update_status(
                db, job.job_id, TrainingJobStatus.EVALUATING, school_id=school_id
            )

        def on_eval_end_callback(step: int, epoch: float):
            training_job_repository.update_status(
                db, job.job_id, TrainingJobStatus.RUNNING, school_id=school_id
            )

        # 8. Execute A9.2 Training Engine with Hooks
        try:
            provenance = SftTrainingEngine.run_training(
                db=db,
                version_tag=dv.version_tag,
                base_model_name=job_config.base_model_name,
                lora_params=job_config.lora,
                quant_config=job_config.quantization,
                training_args=training_args,
                token_config=token_cfg,
                experiment_id=job_config.experiment_id,
                cancellation_check=cancellation_checker,
                step_callback=on_step_callback,
                eval_start_callback=on_eval_start_callback,
                eval_end_callback=on_eval_end_callback,
            )

            # 9. Update Final Progress & Artifact Metrics
            final_eval_ppl = (
                round(math.exp(min(provenance.final_eval_loss, 20.0)), 4)
                if provenance.final_eval_loss is not None
                else None
            )
            training_job_repository.update_progress(
                db=db,
                job_id=job.job_id,
                current_epoch=float(job_config.training.num_train_epochs),
                current_step=total_calculated_steps,
                total_steps=total_calculated_steps,
                school_id=school_id,
                train_loss=provenance.final_train_loss,
                eval_loss=provenance.final_eval_loss,
                eval_perplexity=final_eval_ppl,
                best_checkpoint_path=provenance.best_checkpoint_path,
                final_adapter_path=os.path.join(training_run_output_dir, "final_adapter"),
            )

            # 10. Durable Artifact Storage Synchronization (S3 / Remote Storage)
            # Strict cloud durability: only mark COMPLETED after durable sync is confirmed
            artifact_store.sync_to_remote()

            # 11. State Transition: COMPLETED
            training_job_repository.update_status(
                db, job.job_id, TrainingJobStatus.COMPLETED, school_id=school_id
            )
            logger.info(
                f"TrainingJob '{job.job_id}' (Run '{job.current_run_id}') COMPLETED & synced successfully."
            )
            return job

        except TrainingCancelledError as ce:
            logger.info(f"TrainingJob '{job.job_id}' cancelled during loop: {ce}")
            try:
                artifact_store.sync_to_remote()
                training_job_repository.update_status(
                    db,
                    job.job_id,
                    TrainingJobStatus.CANCELLED,
                    school_id=school_id,
                    error_message=str(ce),
                )
            except ArtifactSyncError as se:
                err_msg = f"Training cancelled by user, but durable artifact sync failed: {se}"
                logger.error(err_msg)
                training_job_repository.update_status(
                    db,
                    job.job_id,
                    TrainingJobStatus.FAILED,
                    school_id=school_id,
                    error_message=err_msg,
                    failure_code="ARTIFACT_SYNC_FAILED",
                )
            return job

        except ArtifactSyncError as se:
            err_msg = f"Durable cloud artifact synchronization failure: {se}"
            logger.error(err_msg)
            training_job_repository.update_status(
                db,
                job.job_id,
                TrainingJobStatus.FAILED,
                school_id=school_id,
                error_message=err_msg,
                failure_code="ARTIFACT_SYNC_FAILED",
            )
            return job

        except Exception as e:
            err_msg = f"Training execution error: {e}"
            logger.error(err_msg)
            training_job_repository.update_status(
                db,
                job.job_id,
                TrainingJobStatus.FAILED,
                school_id=school_id,
                error_message=err_msg,
                failure_code="TRAINING_ENGINE_ERROR",
            )
            try:
                artifact_store.sync_to_remote()
            except Exception:
                pass
            return job

    @classmethod
    def request_cancellation(
        cls,
        db: Session,
        job_id: str,
        school_id: Optional[int] = None,
        reason: str = "User cancellation",
    ) -> TrainingJob:
        """
        Sets status to CANCEL_REQUESTED for cooperative graceful termination by the runner.
        """
        job = training_job_repository.request_cancellation(db, job_id, school_id=school_id)
        if not job:
            raise ValueError(f"TrainingJob '{job_id}' not found or cannot be cancelled.")
        logger.info(f"Cancellation requested for TrainingJob '{job_id}': {reason}")
        return job

    @classmethod
    def resume_job(
        cls,
        db: Session,
        job_id: str,
        school_id: Optional[int] = None,
        checkpoint_path: Optional[str] = None,
        additional_epochs: Optional[int] = None,
        worker_id: Optional[str] = None,
        base_artifact_uri: str = "./runs",
    ) -> TrainingJob:
        """
        Resumes a FAILED, CANCELLED, or STALE job by spawning a new run_id linked to parent_run_id,
        hydrating remote S3 checkpoints down to local staging if necessary, and explicitly wiring
        the checkpoint into training_args.resume_from_checkpoint.
        """
        job = training_job_repository.get_by_job_id(db, job_id, school_id=school_id)
        if not job:
            raise ValueError(f"TrainingJob '{job_id}' not found or access denied.")

        if job.status not in [
            TrainingJobStatus.FAILED,
            TrainingJobStatus.CANCELLED,
            TrainingJobStatus.STALE,
        ]:
            raise ValueError(
                f"Cannot resume job in status '{job.status}'. Must be FAILED, CANCELLED, or STALE."
            )

        new_run_id = f"run_{uuid.uuid4().hex[:8]}"

        # 1. Resolve Resume Checkpoint & Enforce Namespace Authorization
        if checkpoint_path:
            if job_id not in str(checkpoint_path):
                raise PermissionError(
                    f"Security violation: Checkpoint URI '{checkpoint_path}' does not belong to job namespace '{job_id}'."
                )
        resolved_ckpt = checkpoint_path or job.best_checkpoint_path
        if not resolved_ckpt:
            parent_run_dir = get_artifact_store(
                base_artifact_uri, job.job_id, job.current_run_id
            ).get_local_working_dir()
            if os.path.exists(parent_run_dir):
                ckpts = [
                    os.path.join(parent_run_dir, d)
                    for d in os.listdir(parent_run_dir)
                    if d.startswith("checkpoint-")
                ]
                if ckpts:
                    resolved_ckpt = sorted(ckpts)[-1]

        # 2. Remote Checkpoint Hydration (S3 -> Local Staging)
        if resolved_ckpt and str(resolved_ckpt).startswith("s3://"):
            staging_store = get_artifact_store(base_artifact_uri, job.job_id, new_run_id)
            target_local_ckpt_dir = os.path.join(
                staging_store.get_local_working_dir(), "checkpoints", "hydrated_resume"
            )
            resolved_ckpt = staging_store.download_checkpoint(resolved_ckpt, target_local_ckpt_dir)

        # 3. Update Job Configuration Payload with Resume Checkpoint & Additional Epochs
        job_config_dict = dict(job.job_config_payload)
        if "training" not in job_config_dict:
            job_config_dict["training"] = {}
        if resolved_ckpt:
            job_config_dict["training"]["resume_from_checkpoint"] = resolved_ckpt

        if additional_epochs and additional_epochs > 0:
            current_epochs = job_config_dict["training"].get("num_train_epochs", job.total_epochs)
            job_config_dict["training"]["num_train_epochs"] = current_epochs + additional_epochs
            job.total_epochs = job_config_dict["training"]["num_train_epochs"]

        job.parent_run_id = job.current_run_id
        job.current_run_id = new_run_id
        job.retry_count += 1
        job.job_config_payload = job_config_dict
        job.status = TrainingJobStatus.RESUMING
        db.flush()

        logger.info(
            f"Resuming TrainingJob '{job_id}': Spawning Run '{new_run_id}' (Parent: '{job.parent_run_id}', Checkpoint: '{resolved_ckpt}')."
        )
        return cls.start_job(
            db,
            job_id,
            school_id=school_id,
            worker_id=worker_id,
            base_artifact_uri=base_artifact_uri,
        )
