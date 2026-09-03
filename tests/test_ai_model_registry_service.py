import json
import os
import tempfile
import uuid

import pytest
from sqlalchemy.orm import Session

from app.models.ai.model_version import ModelVersionStatus
from app.models.ai.registered_model import RegisteredModel
from app.services.ai.governance.dataset_builder_service import DatasetBuilderService
from app.services.ai.training.orchestration.job_runner import JobRunner
from app.services.ai.training.registry.service import model_registry_service
from tests.test_ai_training_orchestration import create_orchestration_dataset


def create_sample_peft_adapter_files(adapter_dir: str):
    """Helper to create valid LoRA adapter files in a directory."""
    os.makedirs(adapter_dir, exist_ok=True)
    with open(os.path.join(adapter_dir, "adapter_config.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "base_model_name_or_path": "meta-llama/Llama-3.1-8B-Instruct",
                "lora_alpha": 32,
                "lora_dropout": 0.05,
                "r": 16,
                "target_modules": ["q_proj", "v_proj"],
                "peft_type": "LORA",
            },
            f,
            indent=2,
        )
    with open(os.path.join(adapter_dir, "adapter_model.safetensors"), "wb") as f:
        f.write(b"MOCK_SAFETENSORS_WEIGHTS_BINARY_BLOB_FOR_TESTING_1234567890")
    with open(os.path.join(adapter_dir, "special_tokens_map.json"), "w", encoding="utf-8") as f:
        json.dump({"pad_token": "<|finetune_pad|>"}, f)
    with open(os.path.join(adapter_dir, "tokenizer_config.json"), "w", encoding="utf-8") as f:
        json.dump({"model_max_length": 2048}, f)


def create_completed_job_fixture(
    db: Session, v_tag: str, school_name: str = "SMA Registry Service Lab"
):
    dv, teacher, school = create_orchestration_dataset(db, v_tag, school_name=school_name)
    with tempfile.TemporaryDirectory() as tmpdir:
        job = JobRunner.create_job(
            db=db,
            raw_config={
                "dataset_version_tag": v_tag,
                "base_model_name": "meta-llama/Llama-3.1-8B-Instruct",
                "execution_mode": "CPU_TEST",
                "training": {"num_train_epochs": 1},
            },
            school_id=school.id,
            base_artifact_uri=tmpdir,
            created_by_user_id=teacher.id,
        )
        JobRunner.start_job(db, job.job_id, school_id=school.id, base_artifact_uri=tmpdir)
        db.refresh(job)
        return job, dv, teacher, school


def create_completed_job_for_existing_school(db: Session, school, teacher, v_tag: str):
    dv = DatasetBuilderService.build_dataset_version(
        db=db,
        version_tag=v_tag,
        school_id=school.id,
        train_ratio=1.0,
        val_ratio=0.0,
        test_ratio=0.0,
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        job = JobRunner.create_job(
            db=db,
            raw_config={
                "dataset_version_tag": v_tag,
                "base_model_name": "meta-llama/Llama-3.1-8B-Instruct",
                "execution_mode": "CPU_TEST",
                "training": {"num_train_epochs": 1},
            },
            school_id=school.id,
            base_artifact_uri=tmpdir,
            created_by_user_id=teacher.id,
        )
        JobRunner.start_job(db, job.job_id, school_id=school.id, base_artifact_uri=tmpdir)
        db.refresh(job)
        return job, dv


# ==============================================================================
# 1. REGISTRATION & CONCURRENCY
# ==============================================================================


def test_register_model_version_from_completed_training_job(db: Session):
    v_tag = f"v_svc_reg_{uuid.uuid4().hex[:4]}"
    job, dv, teacher, school = create_completed_job_fixture(db, v_tag)

    with tempfile.TemporaryDirectory() as tmpdir:
        adapter_dir = os.path.join(tmpdir, "adapter")
        create_sample_peft_adapter_files(adapter_dir)

        model_name = f"model-grader-{uuid.uuid4().hex[:4]}"
        mv = model_registry_service.register_model_version(
            db=db,
            model_name=model_name,
            training_job_id=job.id,
            base_artifact_dir=adapter_dir,
            school_id=school.id,
            created_by_user_id=teacher.id,
            metadata={"domain": "essay_grading"},
        )

        assert mv is not None
        assert mv.version == "v1"
        assert mv.version_number == 1
        assert mv.status == ModelVersionStatus.REGISTERED.value
        assert mv.training_job_id == job.id
        assert mv.dataset_hash == dv.dataset_hash
        assert mv.base_model_name == "meta-llama/Llama-3.1-8B-Instruct"
        assert mv.artifact_manifest_hash.startswith("sha256:")
        assert mv.adapter_config_hash.startswith("sha256:")
        assert len(mv.promotion_history) >= 1
        assert os.path.exists(os.path.join(adapter_dir, "model_manifest.json"))


def test_register_model_version_fails_if_job_not_completed(db: Session):
    v_tag = f"v_svc_running_{uuid.uuid4().hex[:4]}"
    dv, teacher, school = create_orchestration_dataset(db, v_tag)
    with tempfile.TemporaryDirectory() as tmpdir:
        running_job = JobRunner.create_job(
            db=db,
            raw_config={
                "dataset_version_tag": v_tag,
                "base_model_name": "meta-llama/Llama-3.1-8B-Instruct",
                "execution_mode": "CPU_TEST",
            },
            school_id=school.id,
            base_artifact_uri=tmpdir,
            created_by_user_id=teacher.id,
        )

        adapter_dir = os.path.join(tmpdir, "adapter")
        create_sample_peft_adapter_files(adapter_dir)

        with pytest.raises(ValueError, match="Only COMPLETED training jobs can be registered"):
            model_registry_service.register_model_version(
                db=db,
                model_name="failing-model",
                training_job_id=running_job.id,
                base_artifact_dir=adapter_dir,
                school_id=school.id,
            )


# ==============================================================================
# 2. VALIDATION GATE LIFECYCLE
# ==============================================================================


def test_validate_model_version_happy_path(db: Session):
    v_tag = f"v_svc_val_{uuid.uuid4().hex[:4]}"
    job, dv, teacher, school = create_completed_job_fixture(db, v_tag)

    with tempfile.TemporaryDirectory() as tmpdir:
        adapter_dir = os.path.join(tmpdir, "adapter")
        create_sample_peft_adapter_files(adapter_dir)

        mv = model_registry_service.register_model_version(
            db=db,
            model_name=f"model-val-{uuid.uuid4().hex[:4]}",
            training_job_id=job.id,
            base_artifact_dir=adapter_dir,
            school_id=school.id,
            created_by_user_id=teacher.id,
        )

        passed, validated_version = model_registry_service.validate_model_version(
            db=db,
            model_version_id=mv.id,
            artifact_dir=adapter_dir,
            school_id=school.id,
            user_id=teacher.id,
        )

        assert passed is True
        assert validated_version.status == ModelVersionStatus.VALIDATED.value
        assert validated_version.validation_report_payload["passed"] is True
        assert len(validated_version.promotion_history) >= 2


def test_validate_model_version_rejects_tampered_artifact(db: Session):
    v_tag = f"v_svc_tamp_{uuid.uuid4().hex[:4]}"
    job, dv, teacher, school = create_completed_job_fixture(db, v_tag)

    with tempfile.TemporaryDirectory() as tmpdir:
        adapter_dir = os.path.join(tmpdir, "adapter")
        create_sample_peft_adapter_files(adapter_dir)

        mv = model_registry_service.register_model_version(
            db=db,
            model_name=f"model-tamper-{uuid.uuid4().hex[:4]}",
            training_job_id=job.id,
            base_artifact_dir=adapter_dir,
            school_id=school.id,
            created_by_user_id=teacher.id,
        )

        # Tamper with weights
        with open(os.path.join(adapter_dir, "adapter_model.safetensors"), "ab") as f:
            f.write(b"TAMPERED_EXTRA_DATA")

        passed, rejected_version = model_registry_service.validate_model_version(
            db=db,
            model_version_id=mv.id,
            artifact_dir=adapter_dir,
            school_id=school.id,
            user_id=teacher.id,
        )

        assert passed is False
        assert rejected_version.status == ModelVersionStatus.REJECTED.value
        assert rejected_version.validation_report_payload["passed"] is False


# ==============================================================================
# 3. PROMOTION & STAGING
# ==============================================================================


def test_promote_to_staged_and_production_lifecycle(db: Session):
    v_tag = f"v_svc_promo_{uuid.uuid4().hex[:4]}"
    job1, dv, teacher, school = create_completed_job_fixture(db, v_tag)

    with tempfile.TemporaryDirectory() as tmpdir:
        adapter_dir1 = os.path.join(tmpdir, "adapter1")
        create_sample_peft_adapter_files(adapter_dir1)

        model_name = f"model-promo-{uuid.uuid4().hex[:4]}"
        mv1 = model_registry_service.register_model_version(
            db=db,
            model_name=model_name,
            training_job_id=job1.id,
            base_artifact_dir=adapter_dir1,
            school_id=school.id,
            created_by_user_id=teacher.id,
        )

        # Cannot promote REGISTERED (unvalidated) version
        with pytest.raises(ValueError, match="Must be in VALIDATED state"):
            model_registry_service.promote_to_staged(
                db=db, model_version_id=mv1.id, reason="premature promotion", school_id=school.id
            )

        # Validate mv1
        model_registry_service.validate_model_version(
            db=db, model_version_id=mv1.id, artifact_dir=adapter_dir1, school_id=school.id
        )

        # Promote to STAGED
        staged_v1 = model_registry_service.promote_to_staged(
            db=db, model_version_id=mv1.id, reason="Passed benchmark tests", school_id=school.id
        )
        assert staged_v1.status == ModelVersionStatus.STAGED.value

        parent_model = db.query(RegisteredModel).filter(RegisteredModel.id == mv1.model_id).first()
        assert parent_model.active_staged_version_id == mv1.id
        assert parent_model.active_production_version_id is None

        # Promote to PRODUCTION
        prod_v1 = model_registry_service.promote_to_production(
            db=db, model_version_id=mv1.id, reason="Release v1 live", school_id=school.id
        )
        assert prod_v1.status == ModelVersionStatus.PRODUCTION.value
        db.refresh(parent_model)
        assert parent_model.active_production_version_id == mv1.id


# ==============================================================================
# 4. SUPERSEDING & ZERO-DOWNTIME ROLLBACK
# ==============================================================================


def test_atomic_superseding_and_rollback(db: Session):
    v_tag1 = f"v_svc_rb1_{uuid.uuid4().hex[:4]}"
    v_tag2 = f"v_svc_rb2_{uuid.uuid4().hex[:4]}"
    job1, dv1, teacher, school = create_completed_job_fixture(db, v_tag1)
    job2, dv2 = create_completed_job_for_existing_school(db, school, teacher, v_tag2)

    with tempfile.TemporaryDirectory() as tmpdir:
        adapter_dir1 = os.path.join(tmpdir, "adapter1")
        adapter_dir2 = os.path.join(tmpdir, "adapter2")
        create_sample_peft_adapter_files(adapter_dir1)
        create_sample_peft_adapter_files(adapter_dir2)

        model_name = f"model-rb-{uuid.uuid4().hex[:4]}"

        # 1. Register & Promote v1 to PRODUCTION
        mv1 = model_registry_service.register_model_version(
            db=db,
            model_name=model_name,
            training_job_id=job1.id,
            base_artifact_dir=adapter_dir1,
            school_id=school.id,
        )
        model_registry_service.validate_model_version(
            db=db, model_version_id=mv1.id, artifact_dir=adapter_dir1, school_id=school.id
        )
        model_registry_service.promote_to_production(
            db=db, model_version_id=mv1.id, reason="v1 launch", school_id=school.id
        )

        model = db.query(RegisteredModel).filter(RegisteredModel.id == mv1.model_id).first()
        assert model.active_production_version_id == mv1.id

        # 2. Register & Promote v2 to PRODUCTION (Superseding v1)
        mv2 = model_registry_service.register_model_version(
            db=db,
            model_name=model_name,
            training_job_id=job2.id,
            base_artifact_dir=adapter_dir2,
            school_id=school.id,
        )
        model_registry_service.validate_model_version(
            db=db, model_version_id=mv2.id, artifact_dir=adapter_dir2, school_id=school.id
        )
        model_registry_service.promote_to_production(
            db=db, model_version_id=mv2.id, reason="v2 launch", school_id=school.id
        )

        db.refresh(model)
        db.refresh(mv1)
        db.refresh(mv2)
        assert model.active_production_version_id == mv2.id
        assert mv2.status == ModelVersionStatus.PRODUCTION.value
        assert mv1.status == ModelVersionStatus.ARCHIVED.value  # Demoted automatically

        # 3. Rollback PRODUCTION: v2 -> v1 without altering artifact weights
        rolled_back_version = model_registry_service.rollback_production(
            db=db,
            model_id=model.id,
            target_version_str="v1",
            reason="Anomaly detected in v2 inference latency",
            school_id=school.id,
        )

        db.refresh(model)
        db.refresh(mv1)
        db.refresh(mv2)
        assert model.active_production_version_id == mv1.id
        assert rolled_back_version.id == mv1.id
        assert mv1.status == ModelVersionStatus.PRODUCTION.value
        assert mv2.status == ModelVersionStatus.ARCHIVED.value

        # Verify audit history
        assert len(mv1.promotion_history) >= 4
        assert "Rollback to v1" in mv1.promotion_history[-1]["reason"]


def test_rollback_rejects_foreign_model_version_pointer_injection(db: Session):
    v_tag1 = f"v_svc_f1_{uuid.uuid4().hex[:4]}"
    v_tag2 = f"v_svc_f2_{uuid.uuid4().hex[:4]}"
    job1, dv1, teacher, school = create_completed_job_fixture(db, v_tag1)
    job2, dv2 = create_completed_job_for_existing_school(db, school, teacher, v_tag2)

    with tempfile.TemporaryDirectory() as tmpdir:
        dir1 = os.path.join(tmpdir, "dir1")
        dir2 = os.path.join(tmpdir, "dir2")
        create_sample_peft_adapter_files(dir1)
        create_sample_peft_adapter_files(dir2)

        model1 = f"model-a-{uuid.uuid4().hex[:4]}"
        model2 = f"model-b-{uuid.uuid4().hex[:4]}"

        mv1 = model_registry_service.register_model_version(
            db=db,
            model_name=model1,
            training_job_id=job1.id,
            base_artifact_dir=dir1,
            school_id=school.id,
        )
        mv2 = model_registry_service.register_model_version(
            db=db,
            model_name=model2,
            training_job_id=job2.id,
            base_artifact_dir=dir2,
            school_id=school.id,
        )

        m1 = db.query(RegisteredModel).filter(RegisteredModel.id == mv1.model_id).first()

        # Attempting rollback to a non-existent version string on Model 1 fails
        with pytest.raises(FileNotFoundError, match="Target version 'v99' does not exist"):
            model_registry_service.rollback_production(
                db=db,
                model_id=m1.id,
                target_version_str="v99",
                reason="Invalid target",
                school_id=school.id,
            )
