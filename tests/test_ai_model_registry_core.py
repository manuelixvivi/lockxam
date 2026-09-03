import tempfile
import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.ai.model_version import ModelVersion, ModelVersionStatus
from app.repositories.ai.model_version_repository import model_version_repository
from app.repositories.ai.registered_model_repository import registered_model_repository
from app.services.ai.training.orchestration.job_runner import JobRunner
from tests.test_ai_training_orchestration import create_orchestration_dataset


def create_completed_training_job(db: Session, v_tag: str, school_name: str = "SMA Registry Lab"):
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


# ==============================================================================
# 1. REGISTERED MODEL CREATION & UNIQUE CONSTRAINTS
# ==============================================================================


def test_registered_model_creation_and_attributes(db: Session):
    v_tag = f"v_reg_model_{uuid.uuid4().hex[:4]}"
    job, dv, teacher, school = create_completed_training_job(db, v_tag)

    model = registered_model_repository.create(
        db=db,
        name="equigrade-essay-grader-bio",
        display_name="EquiGrade Biologi Essay Grader",
        description="Fine-tuned LoRA model for high school biology essay assessment.",
        task_type="essay_grading",
        school_id=school.id,
        created_by_user_id=teacher.id,
    )

    assert model.id is not None
    assert model.name == "equigrade-essay-grader-bio"
    assert model.task_type == "essay_grading"
    assert model.school_id == school.id
    assert model.active_production_version_id is None
    assert model.active_staged_version_id is None
    assert model.created_at is not None


def test_registered_model_unique_name_per_school_constraint(db: Session):
    v_tag = f"v_reg_uniq_{uuid.uuid4().hex[:4]}"
    job, dv, teacher, school = create_completed_training_job(db, v_tag)

    model_name = f"model-dup-{uuid.uuid4().hex[:4]}"

    registered_model_repository.create(
        db=db,
        name=model_name,
        display_name="First Instance",
        school_id=school.id,
    )

    # Attempt to create duplicate name within the same school must raise IntegrityError
    with pytest.raises(IntegrityError):
        registered_model_repository.create(
            db=db,
            name=model_name,
            display_name="Duplicate Instance",
            school_id=school.id,
        )
    db.rollback()


# ==============================================================================
# 2. MODEL VERSION CREATION & LINEAGE FIELDS
# ==============================================================================


def test_model_version_creation_and_lineage_fields(db: Session):
    v_tag = f"v_mv_lineage_{uuid.uuid4().hex[:4]}"
    job, dv, teacher, school = create_completed_training_job(db, v_tag)

    model = registered_model_repository.create(
        db=db,
        name=f"model-lineage-{uuid.uuid4().hex[:4]}",
        display_name="Lineage Test Model",
        school_id=school.id,
        created_by_user_id=teacher.id,
    )

    next_ver_num = model_version_repository.get_next_version_number(db, model.id)
    assert next_ver_num == 1

    mv = ModelVersion(
        model_id=model.id,
        version=f"v{next_ver_num}",
        version_number=next_ver_num,
        status=ModelVersionStatus.REGISTERED.value,
        training_job_id=job.id,
        training_run_id=job.current_run_id,
        experiment_id=job.experiment_id,
        dataset_version_tag=job.dataset_version_tag,
        dataset_hash=job.dataset_hash,
        base_model_name=job.base_model_name,
        base_model_revision="main",
        tokenizer_name_or_path=job.base_model_name,
        adapter_type="LORA",
        adapter_config_hash="sha256:adapter1234567890abcdef",
        artifact_uri=job.final_adapter_path or job.artifact_uri,
        artifact_manifest_hash="sha256:merkle1234567890abcdef",
        model_manifest_payload={"model_name": model.name, "version": "v1"},
        school_id=school.id,
        created_by_user_id=teacher.id,
    )
    saved_mv = model_version_repository.create(db, mv)

    assert saved_mv.id is not None
    assert saved_mv.version == "v1"
    assert saved_mv.version_number == 1
    assert saved_mv.status == ModelVersionStatus.REGISTERED.value
    assert saved_mv.training_job_id == job.id
    assert saved_mv.dataset_hash == dv.dataset_hash
    assert len(saved_mv.promotion_history) == 1
    assert saved_mv.promotion_history[0]["to_status"] == ModelVersionStatus.REGISTERED.value


# ==============================================================================
# 3. SEQUENTIAL VERSIONING (v1 -> v2 -> v3) & IMMUTABILITY
# ==============================================================================


def test_sequential_version_number_generation_v1_v2_v3(db: Session):
    v_tag = f"v_mv_seq_{uuid.uuid4().hex[:4]}"
    job, dv, teacher, school = create_completed_training_job(db, v_tag)

    model = registered_model_repository.create(
        db=db,
        name=f"model-seq-{uuid.uuid4().hex[:4]}",
        display_name="Sequential Version Test Model",
        school_id=school.id,
    )

    for expected_num in [1, 2, 3]:
        num = model_version_repository.get_next_version_number(db, model.id)
        assert num == expected_num

        mv = ModelVersion(
            model_id=model.id,
            version=f"v{num}",
            version_number=num,
            status=ModelVersionStatus.REGISTERED.value,
            training_job_id=job.id,
            training_run_id=f"run_{num}",
            experiment_id=job.experiment_id,
            dataset_version_tag=job.dataset_version_tag,
            dataset_hash=job.dataset_hash,
            base_model_name=job.base_model_name,
            tokenizer_name_or_path=job.base_model_name,
            adapter_type="LORA",
            adapter_config_hash=f"hash_{num}",
            artifact_uri=f"s3://bucket/runs/job_1/run_{num}/adapter",
            artifact_manifest_hash=f"merkle_{num}",
            model_manifest_payload={"version": f"v{num}"},
            school_id=school.id,
        )
        model_version_repository.create(db, mv)

    versions = model_version_repository.list_by_model(db, model.id)
    assert len(versions) == 3
    assert [v.version for v in versions] == ["v3", "v2", "v1"]  # ordered desc by version_number


def test_model_version_unique_model_id_and_version_constraint(db: Session):
    v_tag = f"v_mv_dup_{uuid.uuid4().hex[:4]}"
    job, dv, teacher, school = create_completed_training_job(db, v_tag)

    model = registered_model_repository.create(
        db=db,
        name=f"model-dupver-{uuid.uuid4().hex[:4]}",
        display_name="Dup Version Test",
        school_id=school.id,
    )

    mv1 = ModelVersion(
        model_id=model.id,
        version="v1",
        version_number=1,
        training_job_id=job.id,
        training_run_id="run_1",
        experiment_id="E2",
        dataset_version_tag="v1",
        dataset_hash="hash_1",
        base_model_name="model_1",
        tokenizer_name_or_path="tok_1",
        adapter_type="LORA",
        adapter_config_hash="h1",
        artifact_uri="uri_1",
        artifact_manifest_hash="m1",
        model_manifest_payload={},
        school_id=school.id,
    )
    model_version_repository.create(db, mv1)
    db.commit()

    # Duplicate version 'v1' for same model_id must fail at database level
    mv2 = ModelVersion(
        model_id=model.id,
        version="v1",
        version_number=1,
        training_job_id=job.id,
        training_run_id="run_2",
        experiment_id="E2",
        dataset_version_tag="v1",
        dataset_hash="hash_1",
        base_model_name="model_1",
        tokenizer_name_or_path="tok_1",
        adapter_type="LORA",
        adapter_config_hash="h2",
        artifact_uri="uri_2",
        artifact_manifest_hash="m2",
        model_manifest_payload={},
        school_id=school.id,
    )
    with pytest.raises(IntegrityError):
        model_version_repository.create(db, mv2)
    db.rollback()


# ==============================================================================
# 4. TENANT ISOLATION & FK RESTRICT
# ==============================================================================


def test_tenant_isolation_on_registered_model_and_versions(db: Session):
    v_tag1 = f"v_ten1_{uuid.uuid4().hex[:4]}"
    v_tag2 = f"v_ten2_{uuid.uuid4().hex[:4]}"
    job1, dv1, teacher1, school1 = create_completed_training_job(
        db, v_tag1, school_name="School Alpha"
    )
    job2, dv2, teacher2, school2 = create_completed_training_job(
        db, v_tag2, school_name="School Beta"
    )

    model1 = registered_model_repository.create(
        db=db,
        name="model-alpha",
        display_name="School Alpha Model",
        school_id=school1.id,
    )

    # School Beta attempting to query School Alpha's model by ID should return None
    assert registered_model_repository.get_by_id(db, model1.id, school_id=school2.id) is None

    # School Beta listing models should only see its own models
    models_beta = registered_model_repository.list_models(db, school_id=school2.id)
    assert model1.id not in [m.id for m in models_beta]


def test_foreign_key_restrict_prevents_deleting_referenced_job_or_model(db: Session):
    v_tag = f"v_fk_res_{uuid.uuid4().hex[:4]}"
    job, dv, teacher, school = create_completed_training_job(db, v_tag)

    model = registered_model_repository.create(
        db=db,
        name=f"model-fk-{uuid.uuid4().hex[:4]}",
        display_name="FK Restrict Test",
        school_id=school.id,
    )

    mv = ModelVersion(
        model_id=model.id,
        version="v1",
        version_number=1,
        training_job_id=job.id,
        training_run_id=job.current_run_id,
        experiment_id=job.experiment_id,
        dataset_version_tag=job.dataset_version_tag,
        dataset_hash=job.dataset_hash,
        base_model_name=job.base_model_name,
        tokenizer_name_or_path=job.base_model_name,
        adapter_type="LORA",
        adapter_config_hash="cfg_hash",
        artifact_uri="s3://bucket/runs/job/run/adapter",
        artifact_manifest_hash="art_hash",
        model_manifest_payload={},
        school_id=school.id,
    )
    model_version_repository.create(db, mv)

    # Attempting to delete TrainingJob referenced by ModelVersion must be restricted
    # Note: On SQLite with FK enabled or Postgres, deletion raises IntegrityError
    db.delete(job)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


# ==============================================================================
# 5. POINTER UPDATES, ROLLBACK & AUDIT LOGGING
# ==============================================================================


def test_active_production_and_staged_pointer_updates_and_rollback(db: Session):
    v_tag = f"v_pointers_{uuid.uuid4().hex[:4]}"
    job, dv, teacher, school = create_completed_training_job(db, v_tag)

    model = registered_model_repository.create(
        db=db,
        name=f"model-pointers-{uuid.uuid4().hex[:4]}",
        display_name="Pointers & Rollback Test",
        school_id=school.id,
    )

    # Create v1 and v2
    mv1 = model_version_repository.create(
        db,
        ModelVersion(
            model_id=model.id,
            version="v1",
            version_number=1,
            status=ModelVersionStatus.REGISTERED.value,
            training_job_id=job.id,
            training_run_id="run_1",
            experiment_id="E2",
            dataset_version_tag="v1",
            dataset_hash="h1",
            base_model_name="m1",
            tokenizer_name_or_path="t1",
            adapter_type="LORA",
            adapter_config_hash="c1",
            artifact_uri="uri1",
            artifact_manifest_hash="m1",
            model_manifest_payload={},
            school_id=school.id,
        ),
    )

    mv2 = model_version_repository.create(
        db,
        ModelVersion(
            model_id=model.id,
            version="v2",
            version_number=2,
            status=ModelVersionStatus.REGISTERED.value,
            training_job_id=job.id,
            training_run_id="run_2",
            experiment_id="E2",
            dataset_version_tag="v2",
            dataset_hash="h2",
            base_model_name="m2",
            tokenizer_name_or_path="t2",
            adapter_type="LORA",
            adapter_config_hash="c2",
            artifact_uri="uri2",
            artifact_manifest_hash="m2",
            model_manifest_payload={},
            school_id=school.id,
        ),
    )

    # Promote v1 to STAGED
    registered_model_repository.update_pointers(
        db=db,
        model_id=model.id,
        active_staged_version_id=mv1.id,
        update_staged=True,
    )
    model_version_repository.update_status(
        db, mv1.id, ModelVersionStatus.STAGED, reason="Staging evaluation"
    )

    db.refresh(model)
    assert model.active_staged_version_id == mv1.id
    assert model.active_production_version_id is None

    # Promote v1 to PRODUCTION
    registered_model_repository.update_pointers(
        db=db,
        model_id=model.id,
        active_production_version_id=mv1.id,
        update_production=True,
    )
    model_version_repository.update_status(
        db, mv1.id, ModelVersionStatus.PRODUCTION, reason="Promoted to live grading"
    )

    db.refresh(model)
    assert model.active_production_version_id == mv1.id

    # Promote v2 to PRODUCTION (Superseding v1)
    registered_model_repository.update_pointers(
        db=db,
        model_id=model.id,
        active_production_version_id=mv2.id,
        update_production=True,
    )
    model_version_repository.update_status(
        db, mv2.id, ModelVersionStatus.PRODUCTION, reason="New version release"
    )
    model_version_repository.update_status(
        db, mv1.id, ModelVersionStatus.ARCHIVED, reason="Superseded by v2"
    )

    db.refresh(model)
    assert model.active_production_version_id == mv2.id

    # Rollback PRODUCTION: v2 -> v1 without modifying v2 artifact
    registered_model_repository.update_pointers(
        db=db,
        model_id=model.id,
        active_production_version_id=mv1.id,
        update_production=True,
    )
    model_version_repository.update_status(
        db, mv1.id, ModelVersionStatus.PRODUCTION, reason="Rollback due to v2 anomaly"
    )
    model_version_repository.update_status(
        db, mv2.id, ModelVersionStatus.ARCHIVED, reason="Demoted during rollback"
    )

    db.refresh(model)
    assert model.active_production_version_id == mv1.id

    # Verify audit history on mv1
    db.refresh(mv1)
    history = mv1.promotion_history
    assert len(history) >= 4
    assert history[-1]["reason"] == "Rollback due to v2 anomaly"
    assert history[-1]["to_status"] == ModelVersionStatus.PRODUCTION.value


def test_registered_model_delete_does_not_cascade_model_versions(db: Session):
    v_tag = f"v_no_cascade_{uuid.uuid4().hex[:4]}"
    job, dv, teacher, school = create_completed_training_job(db, v_tag)

    model = registered_model_repository.create(
        db=db,
        name=f"model-nocascade-{uuid.uuid4().hex[:4]}",
        display_name="No Cascade Test",
        school_id=school.id,
    )

    mv = model_version_repository.create(
        db,
        ModelVersion(
            model_id=model.id,
            version="v1",
            version_number=1,
            status=ModelVersionStatus.REGISTERED.value,
            training_job_id=job.id,
            training_run_id=job.current_run_id,
            experiment_id=job.experiment_id,
            dataset_version_tag=job.dataset_version_tag,
            dataset_hash=job.dataset_hash,
            base_model_name=job.base_model_name,
            tokenizer_name_or_path=job.base_model_name,
            adapter_type="LORA",
            adapter_config_hash="c1",
            artifact_uri="uri1",
            artifact_manifest_hash="m1",
            model_manifest_payload={},
            school_id=school.id,
        ),
    )
    db.commit()

    # Attempting to delete RegisteredModel must NOT cascade-delete ModelVersion; FK RESTRICT blocks deletion
    db.delete(model)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()

    # After rollback, both model and model version must still exist
    assert registered_model_repository.get_by_id(db, model.id) is not None
    assert model_version_repository.get_by_id(db, mv.id) is not None


def test_model_version_cannot_belong_to_different_school_than_registered_model(db: Session):
    v_tag1 = f"v_cross_s1_{uuid.uuid4().hex[:4]}"
    v_tag2 = f"v_cross_s2_{uuid.uuid4().hex[:4]}"
    job1, dv1, teacher1, school1 = create_completed_training_job(db, v_tag1, school_name="School 1")
    job2, dv2, teacher2, school2 = create_completed_training_job(db, v_tag2, school_name="School 2")

    model1 = registered_model_repository.create(
        db=db,
        name=f"model-s1-{uuid.uuid4().hex[:4]}",
        display_name="School 1 Model",
        school_id=school1.id,
    )

    # Attempting to attach a ModelVersion with School 2's ID to School 1's Model must raise PermissionError
    mv_cross = ModelVersion(
        model_id=model1.id,
        version="v1",
        version_number=1,
        status=ModelVersionStatus.REGISTERED.value,
        training_job_id=job2.id,
        training_run_id="run_cross",
        experiment_id="E2",
        dataset_version_tag="v1",
        dataset_hash="h1",
        base_model_name="m1",
        tokenizer_name_or_path="t1",
        adapter_type="LORA",
        adapter_config_hash="c1",
        artifact_uri="uri1",
        artifact_manifest_hash="m1",
        model_manifest_payload={},
        school_id=school2.id,  # Mismatched school_id
    )

    with pytest.raises(PermissionError, match="Tenant isolation violation"):
        model_version_repository.create(db, mv_cross)
    db.rollback()


def test_model_version_lineage_fields_are_immutable(db: Session):
    v_tag = f"v_immut_{uuid.uuid4().hex[:4]}"
    job, dv, teacher, school = create_completed_training_job(db, v_tag)

    model = registered_model_repository.create(
        db=db,
        name=f"model-immut-{uuid.uuid4().hex[:4]}",
        display_name="Immutability Guard Test",
        school_id=school.id,
    )

    mv = model_version_repository.create(
        db,
        ModelVersion(
            model_id=model.id,
            version="v1",
            version_number=1,
            status=ModelVersionStatus.REGISTERED.value,
            training_job_id=job.id,
            training_run_id=job.current_run_id,
            experiment_id=job.experiment_id,
            dataset_version_tag=job.dataset_version_tag,
            dataset_hash=job.dataset_hash,
            base_model_name=job.base_model_name,
            tokenizer_name_or_path=job.base_model_name,
            adapter_type="LORA",
            adapter_config_hash="c1",
            artifact_uri="uri1",
            artifact_manifest_hash="m1",
            model_manifest_payload={},
            school_id=school.id,
        ),
    )
    db.commit()
    mv_id = mv.id

    # 1. Attempting to mutate dataset_hash must raise ValueError
    mv.dataset_hash = "sha256:tampered_hash_value"
    with pytest.raises(
        ValueError, match="Mutation prohibited: ModelVersion field 'dataset_hash' is immutable"
    ):
        db.flush()
    db.rollback()

    # Re-fetch clean entity
    mv_clean = model_version_repository.get_by_id(db, mv_id)
    assert mv_clean is not None

    # 2. Attempting to mutate artifact_uri must raise ValueError
    mv_clean.artifact_uri = "s3://tampered/bucket/adapter"
    with pytest.raises(
        ValueError, match="Mutation prohibited: ModelVersion field 'artifact_uri' is immutable"
    ):
        db.flush()
    db.rollback()

    # Re-fetch clean entity
    mv_clean2 = model_version_repository.get_by_id(db, mv_id)
    assert mv_clean2 is not None

    # 3. Attempting to mutate base_model_name must raise ValueError
    mv_clean2.base_model_name = "random-unauthorized-base-model"
    with pytest.raises(
        ValueError, match="Mutation prohibited: ModelVersion field 'base_model_name' is immutable"
    ):
        db.flush()
    db.rollback()

    # 4. Updating mutable lifecycle fields (status, validation_report, promotion_history) is allowed
    mv_clean3 = model_version_repository.get_by_id(db, mv_id)
    mv_clean3.status = ModelVersionStatus.VALIDATING.value
    mv_clean3.validation_report_payload = {"checks_passed": True}
    db.flush()
    db.refresh(mv_clean3)
    assert mv_clean3.status == ModelVersionStatus.VALIDATING.value
    assert mv_clean3.validation_report_payload == {"checks_passed": True}
