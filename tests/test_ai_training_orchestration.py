import json
import os
import shutil
import tempfile
import unittest.mock
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.models.ai.training_job import TrainingJob, TrainingJobStatus
from app.models.exam.answer_evaluation import ExamAnswerEvaluation
from app.repositories.ai.assessment_history_repository import assessment_history_repository
from app.repositories.ai.training_job_repository import training_job_repository
from app.services.ai.governance.dataset_builder_service import DatasetBuilderService
from app.services.ai.governance.training_candidate_service import TrainingCandidateService
from app.services.ai.training.lora.training_engine import SftTrainingEngine, TrainingCancelledError
from app.services.ai.training.orchestration.artifact_store import (
    ArtifactSyncError,
    LocalArtifactStore,
    S3ArtifactStore,
    get_artifact_store,
)
from app.services.ai.training.orchestration.job_config import JobConfigParser
from app.services.ai.training.orchestration.job_runner import JobRunner
from app.services.ai.training.orchestration.manifest_builder import ManifestBuilder
from app.services.ai.training.orchestration.metrics_logger import MetricsLogger
from app.services.ai.training.schemas import JobConfigModel
from app.services.exam.exam_service import ExamService
from tests.test_assessment_history import setup_exam_environment


def create_orchestration_dataset(
    db: Session, v_tag: str, school_name: str = "SMA Orchestration Lab"
):
    attempt, questions, teacher, student, school, subj = setup_exam_environment(
        db, school_name=school_name
    )
    ExamService.submit_attempt(db, attempt.id)

    evals = (
        db.query(ExamAnswerEvaluation)
        .filter(ExamAnswerEvaluation.exam_attempt_id == attempt.id)
        .all()
    )
    essay_eval = next(ev for ev in evals if ev.question_id == questions[1].id)
    ExamService.finalize_evaluation(
        db=db,
        evaluation_id=essay_eval.id,
        score=9.0,
        feedback="Uraian konsep respirasi aerob dan fermentasi asam laktat sangat lengkap.",
        teacher_account_id=teacher.id,
    )
    h = assessment_history_repository.get_current_by_evaluation(db, essay_eval.id)
    TrainingCandidateService.evaluate_and_ingest_history(db, h.id, created_by_user_id=teacher.id)

    dv = DatasetBuilderService.build_dataset_version(
        db=db,
        version_tag=v_tag,
        school_id=school.id,
        train_ratio=1.0,
        val_ratio=0.0,
        test_ratio=0.0,
    )
    return dv, teacher, school


# ==============================================================================
# 1. CONFIG PARSER & VALIDATION TESTS
# ==============================================================================


def test_job_config_parser_and_validation():
    valid_payload = {
        "experiment_id": "E2_FineTuned_Llama3",
        "dataset_version_tag": "v1.0.0-test",
        "base_model_name": "meta-llama/Llama-3.1-8B-Instruct",
        "execution_mode": "CPU_TEST",
        "training": {
            "learning_rate": 0.0002,
            "num_train_epochs": 3,
            "per_device_train_batch_size": 2,
        },
        "lora": {
            "r": 16,
            "lora_alpha": 32,
            "lora_dropout": 0.05,
        },
    }
    cfg = JobConfigParser.parse_and_validate(valid_payload)
    assert cfg.experiment_id == "E2_FineTuned_Llama3"
    assert cfg.training.learning_rate == 0.0002
    assert cfg.lora.r == 16

    # Test invalid learning rate rejection
    invalid_lr = dict(valid_payload, training={"learning_rate": -0.05})
    with pytest.raises(ValueError, match="learning_rate"):
        JobConfigParser.parse_and_validate(invalid_lr)

    # Test invalid LoRA rank rejection
    invalid_r = dict(valid_payload, lora={"r": 0})
    with pytest.raises(ValueError, match="LoRA rank"):
        JobConfigParser.parse_and_validate(invalid_r)


# ==============================================================================
# 2. JOB LIFECYCLE & STATE MACHINE TESTS
# ==============================================================================


def test_training_job_state_machine_happy_path(db: Session):
    v_tag = f"v_orch_happy_{uuid.uuid4().hex[:4]}"
    dv, teacher, school = create_orchestration_dataset(db, v_tag, "SMA Happy Path")

    with tempfile.TemporaryDirectory() as tmpdir:
        job_payload = {
            "dataset_version_tag": v_tag,
            "base_model_name": "meta-llama/Llama-3.1-8B-Instruct",
            "execution_mode": "CPU_TEST",
            "training": {"num_train_epochs": 2, "save_steps": 1, "eval_steps": 1},
        }

        # 1. Create Job (QUEUED)
        job = JobRunner.create_job(
            db=db,
            raw_config=job_payload,
            created_by_user_id=teacher.id,
            school_id=school.id,
            base_artifact_uri=tmpdir,
        )
        assert job.status == TrainingJobStatus.QUEUED
        assert job.job_id.startswith("job_")
        assert job.current_run_id.startswith("run_")

        # 2. Execute Job (QUEUED -> RUNNING -> COMPLETED)
        completed_job = JobRunner.start_job(
            db=db,
            job_id=job.job_id,
            school_id=school.id,
            worker_id="gpu_worker_01",
            base_artifact_uri=tmpdir,
        )

        assert completed_job.status == TrainingJobStatus.COMPLETED
        assert completed_job.train_loss is not None
        assert completed_job.completed_at is not None
        assert os.path.exists(
            os.path.join(tmpdir, "runs", job.job_id, job.current_run_id, "training_manifest.json")
        )
        assert os.path.exists(
            os.path.join(tmpdir, "runs", job.job_id, job.current_run_id, "final_adapter")
        )


def test_training_job_fails_gracefully_on_preflight_error(db: Session):
    v_tag = f"v_orch_fail_{uuid.uuid4().hex[:4]}"
    dv, teacher, school = create_orchestration_dataset(db, v_tag, "SMA Preflight Failure")

    # Corrupt dataset hash
    dv.dataset_hash = "0000000000000000000000000000000000000000000000000000000000000000"
    db.flush()

    with tempfile.TemporaryDirectory() as tmpdir:
        job = JobRunner.create_job(
            db=db,
            raw_config={"dataset_version_tag": v_tag, "execution_mode": "CPU_TEST"},
            school_id=school.id,
            base_artifact_uri=tmpdir,
        )

        failed_job = JobRunner.start_job(
            db=db,
            job_id=job.job_id,
            school_id=school.id,
            base_artifact_uri=tmpdir,
        )

        assert failed_job.status == TrainingJobStatus.FAILED
        assert failed_job.failure_code == "PREFLIGHT_GATE_REJECTED"
        assert "Pre-flight gate failed" in failed_job.error_message


# ==============================================================================
# 3. METRICS STREAMING & ARTIFACT STORE TESTS
# ==============================================================================


def test_metrics_logger_streams_jsonl_records():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalArtifactStore(base_dir=tmpdir, job_id="job_test_01", run_id="run_001")
        logger = MetricsLogger(artifact_store=store)

        logger.log_step(step=10, epoch=0.2, train_loss=1.85, learning_rate=2e-4)
        logger.log_step(
            step=20,
            epoch=0.4,
            train_loss=1.42,
            eval_loss=1.38,
            eval_perplexity=3.97,
            learning_rate=1.8e-4,
        )

        metrics = logger.get_all_metrics()
        assert len(metrics) == 2
        assert metrics[0]["step"] == 10
        assert metrics[0]["train_loss"] == 1.85
        assert metrics[1]["step"] == 20
        assert metrics[1]["eval_loss"] == 1.38


def test_artifact_manager_creates_standard_layout(db: Session):
    v_tag = f"v_layout_{uuid.uuid4().hex[:4]}"
    dv, teacher, school = create_orchestration_dataset(db, v_tag, "SMA Layout Test")

    with tempfile.TemporaryDirectory() as tmpdir:
        job = JobRunner.create_job(
            db=db,
            raw_config={"dataset_version_tag": v_tag, "execution_mode": "CPU_TEST"},
            school_id=school.id,
            base_artifact_uri=tmpdir,
        )
        JobRunner.start_job(db=db, job_id=job.job_id, school_id=school.id, base_artifact_uri=tmpdir)

        run_root = os.path.join(tmpdir, "runs", job.job_id, job.current_run_id)
        assert os.path.exists(os.path.join(run_root, "job_config.json"))
        assert os.path.exists(os.path.join(run_root, "training_manifest.json"))
        assert os.path.exists(os.path.join(run_root, "metrics.jsonl"))
        assert os.path.exists(os.path.join(run_root, "final_adapter"))


def test_training_job_manifest_builder_records_environment():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalArtifactStore(base_dir=tmpdir, job_id="job_env_01", run_id="run_001")
        cfg = JobConfigModel(dataset_version_tag="v_dummy", base_model_name="dummy-model")

        class MockDV:
            version_tag = "v_dummy"
            dataset_hash = "hash_123"
            manifest_hash = "manifest_456"

        manifest = ManifestBuilder.build_and_save_manifest(
            job_id="job_env_01",
            run_id="run_001",
            job_config=cfg,
            dataset_version=MockDV(),
            artifact_store=store,
            worker_id="worker_cuda_0",
        )

        assert manifest["job_id"] == "job_env_01"
        assert manifest["worker_id"] == "worker_cuda_0"
        assert "software_environment" in manifest
        assert "hardware_specification" in manifest
        assert store.exists("training_manifest.json")


# ==============================================================================
# 4. CANCELLATION & STALE JOB TESTS
# ==============================================================================


def test_cancel_request_is_graceful(db: Session):
    v_tag = f"v_cancel_{uuid.uuid4().hex[:4]}"
    dv, teacher, school = create_orchestration_dataset(db, v_tag, "SMA Cancel Test")

    with tempfile.TemporaryDirectory() as tmpdir:
        job = JobRunner.create_job(
            db=db,
            raw_config={"dataset_version_tag": v_tag, "execution_mode": "CPU_TEST"},
            school_id=school.id,
            base_artifact_uri=tmpdir,
        )

        # Request cancellation while QUEUED
        cancelled_req = JobRunner.request_cancellation(
            db, job.job_id, school_id=school.id, reason="User cancelled"
        )
        assert cancelled_req.status == TrainingJobStatus.CANCEL_REQUESTED
        assert cancelled_req.cancel_requested_at is not None

        # Start job detects cancel request and transitions cleanly to CANCELLED
        res = JobRunner.start_job(db, job.job_id, school_id=school.id, base_artifact_uri=tmpdir)
        assert res.status == TrainingJobStatus.CANCELLED


def test_stale_running_job_is_detected(db: Session):
    v_tag = f"v_stale_{uuid.uuid4().hex[:4]}"
    dv, teacher, school = create_orchestration_dataset(db, v_tag, "SMA Stale Test")

    job = TrainingJob(
        job_id=f"job_stale_{uuid.uuid4().hex[:6]}",
        current_run_id="run_stale_01",
        dataset_version_id=dv.id,
        dataset_version_tag=dv.version_tag,
        dataset_hash=dv.dataset_hash,
        base_model_name="dummy-model",
        status=TrainingJobStatus.RUNNING,
        execution_mode="CPU_TEST",
        job_config_payload={},
        artifact_uri="./runs/stale",
        worker_id="crashed_gpu_worker",
        last_heartbeat_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        school_id=school.id,
    )
    training_job_repository.create(db, job)

    stale_jobs = training_job_repository.find_and_mark_stale_jobs(db, stale_threshold_seconds=120)
    assert any(j.job_id == job.job_id for j in stale_jobs)

    refreshed = training_job_repository.get_by_job_id(db, job.job_id)
    assert refreshed.status == TrainingJobStatus.STALE
    assert refreshed.failure_code == "WORKER_HEARTBEAT_TIMEOUT"


# ==============================================================================
# 5. RESUME & MULTI-TENANT ISOLATION TESTS
# ==============================================================================


def test_resume_creates_new_run_and_preserves_job_identity(db: Session):
    v_tag = f"v_resume_orch_{uuid.uuid4().hex[:4]}"
    dv, teacher, school = create_orchestration_dataset(db, v_tag, "SMA Resume Orch")

    with tempfile.TemporaryDirectory() as tmpdir:
        job = JobRunner.create_job(
            db=db,
            raw_config={"dataset_version_tag": v_tag, "execution_mode": "CPU_TEST"},
            school_id=school.id,
            base_artifact_uri=tmpdir,
        )
        initial_run_id = job.current_run_id

        # Mark job as FAILED
        training_job_repository.update_status(
            db, job.job_id, TrainingJobStatus.FAILED, error_message="Worker OOM"
        )

        # Resume job
        resumed_job = JobRunner.resume_job(
            db, job.job_id, school_id=school.id, base_artifact_uri=tmpdir
        )

        assert resumed_job.status == TrainingJobStatus.COMPLETED
        assert resumed_job.job_id == job.job_id  # Preserves Job Identity
        assert resumed_job.current_run_id != initial_run_id  # Spawns new Run Identity
        assert resumed_job.parent_run_id == initial_run_id  # Lineage links to parent run
        assert resumed_job.retry_count == 1


def test_tenant_isolation_for_training_jobs(db: Session):
    v_tag1 = f"v_tenant_s1_{uuid.uuid4().hex[:4]}"
    v_tag2 = f"v_tenant_s2_{uuid.uuid4().hex[:4]}"
    dv1, teacher1, school1 = create_orchestration_dataset(db, v_tag1, "SMA School 1")
    dv2, teacher2, school2 = create_orchestration_dataset(db, v_tag2, "SMA School 2")

    job1 = JobRunner.create_job(
        db=db,
        raw_config={"dataset_version_tag": v_tag1, "execution_mode": "CPU_TEST"},
        school_id=school1.id,
    )

    # School 2 attempting to view School 1's job must return None
    assert training_job_repository.get_by_job_id(db, job1.job_id, school_id=school2.id) is None

    # School 2 attempting to start School 1's job must raise ValueError
    with pytest.raises(ValueError, match="not found or access denied"):
        JobRunner.start_job(db, job1.job_id, school_id=school2.id)

    # School 2 attempting to create a job targeting School 1's dataset must raise PermissionError
    with pytest.raises(PermissionError, match="Cross-tenant access violation"):
        JobRunner.create_job(
            db=db,
            raw_config={"dataset_version_tag": v_tag1, "execution_mode": "CPU_TEST"},
            school_id=school2.id,
        )


def test_artifact_store_interface_local_and_s3():
    with tempfile.TemporaryDirectory() as tmpdir:
        local_store = get_artifact_store(tmpdir, "job_loc", "run_01")
        assert isinstance(local_store, LocalArtifactStore)
        local_store.save_text("hello.txt", "world")
        assert local_store.exists("hello.txt")

        s3_store = get_artifact_store(
            "s3://equigrade-bucket", "job_s3", "run_01", strict_mode=False
        )
        assert isinstance(s3_store, S3ArtifactStore)
        s3_store.save_json("config.json", {"lr": 0.001})
        assert "s3://equigrade-bucket/runs/job_s3/run_01" in s3_store.get_root_uri()


def test_artifact_isolation_between_jobs():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_a = LocalArtifactStore(tmpdir, "job_AAA", "run_001")
        store_b = LocalArtifactStore(tmpdir, "job_BBB", "run_001")

        store_a.save_text("output.txt", "data_A")
        store_b.save_text("output.txt", "data_B")

        with open(store_a.get_full_path("output.txt")) as f:
            assert f.read() == "data_A"
        with open(store_b.get_full_path("output.txt")) as f:
            assert f.read() == "data_B"


def test_metrics_logger_handles_process_restart():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalArtifactStore(tmpdir, "job_restart", "run_001")
        logger1 = MetricsLogger(artifact_store=store)
        logger1.log_step(step=1, epoch=0.1, train_loss=2.5, learning_rate=1e-4)

        # Simulate process restart by instantiating new logger
        logger2 = MetricsLogger(artifact_store=store)
        logger2.log_step(step=2, epoch=0.2, train_loss=2.1, learning_rate=9e-5)

        all_records = logger2.get_all_metrics()
        assert len(all_records) == 2
        assert all_records[0]["step"] == 1
        assert all_records[1]["step"] == 2


def test_heartbeat_updates_timestamp_and_worker_id(db: Session):
    v_tag = f"v_hb_{uuid.uuid4().hex[:4]}"
    dv, teacher, school = create_orchestration_dataset(db, v_tag, "SMA Heartbeat Test")

    job = JobRunner.create_job(
        db=db,
        raw_config={"dataset_version_tag": v_tag, "execution_mode": "CPU_TEST"},
        school_id=school.id,
    )

    updated = training_job_repository.update_heartbeat(
        db, job.job_id, worker_id="worker_gpu_node_42"
    )
    assert updated.worker_id == "worker_gpu_node_42"
    assert updated.last_heartbeat_at is not None


def test_training_job_repository_list_and_filters(db: Session):
    v_tag = f"v_list_{uuid.uuid4().hex[:4]}"
    dv, teacher, school = create_orchestration_dataset(db, v_tag, "SMA List Test")

    job1 = JobRunner.create_job(
        db=db,
        raw_config={
            "dataset_version_tag": v_tag,
            "experiment_id": "EXP_ALPHA",
            "execution_mode": "CPU_TEST",
        },
        school_id=school.id,
    )

    jobs = training_job_repository.list_jobs(db, school_id=school.id, experiment_id="EXP_ALPHA")
    assert len(jobs) >= 1
    assert any(j.job_id == job1.job_id for j in jobs)


def test_best_adapter_survives_checkpoint_pruning(db: Session):
    v_tag = f"v_prune_best_{uuid.uuid4().hex[:4]}"
    dv, teacher, school = create_orchestration_dataset(db, v_tag, "SMA Pruning Best")

    with tempfile.TemporaryDirectory() as tmpdir:
        job = JobRunner.create_job(
            db=db,
            raw_config={
                "dataset_version_tag": v_tag,
                "execution_mode": "CPU_TEST",
                "training": {
                    "num_train_epochs": 3,
                    "save_steps": 1,
                    "eval_steps": 1,
                    "save_total_limit": 2,
                },
            },
            school_id=school.id,
            base_artifact_uri=tmpdir,
        )

        completed_job = JobRunner.start_job(
            db, job.job_id, school_id=school.id, base_artifact_uri=tmpdir
        )
        run_root = os.path.join(tmpdir, "runs", job.job_id, job.current_run_id)

        assert os.path.exists(os.path.join(run_root, "best_adapter"))
        assert os.path.exists(os.path.join(run_root, "final_adapter"))
        assert completed_job.status == TrainingJobStatus.COMPLETED


def test_path_traversal_protection_raises_security_violation():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalArtifactStore(base_dir=tmpdir, job_id="job_sec", run_id="run_sec")
        with pytest.raises(ValueError, match="path traversal detected"):
            store.get_full_path("../../outside_secret.txt")


def test_cooperative_cancellation_during_active_training(db: Session):
    v_tag = f"v_coop_cancel_{uuid.uuid4().hex[:4]}"
    dv, teacher, school = create_orchestration_dataset(db, v_tag, "SMA Coop Cancel")

    with tempfile.TemporaryDirectory() as tmpdir:
        job = JobRunner.create_job(
            db=db,
            raw_config={
                "dataset_version_tag": v_tag,
                "execution_mode": "CPU_TEST",
                "training": {"num_train_epochs": 10},
            },
            school_id=school.id,
            base_artifact_uri=tmpdir,
        )

        # Set status to CANCEL_REQUESTED before start_job executes loop
        training_job_repository.request_cancellation(db, job.job_id, school_id=school.id)

        res = JobRunner.start_job(db, job.job_id, school_id=school.id, base_artifact_uri=tmpdir)
        assert res.status == TrainingJobStatus.CANCELLED


def test_realtime_metrics_streaming_logs_every_step(db: Session):
    v_tag = f"v_steps_stream_{uuid.uuid4().hex[:4]}"
    dv, teacher, school = create_orchestration_dataset(db, v_tag, "SMA Stream Steps")

    with tempfile.TemporaryDirectory() as tmpdir:
        job = JobRunner.create_job(
            db=db,
            raw_config={
                "dataset_version_tag": v_tag,
                "execution_mode": "CPU_TEST",
                "training": {"num_train_epochs": 2, "save_steps": 1, "eval_steps": 1},
            },
            school_id=school.id,
            base_artifact_uri=tmpdir,
        )

        completed_job = JobRunner.start_job(
            db, job.job_id, school_id=school.id, base_artifact_uri=tmpdir
        )
        metrics_file = os.path.join(tmpdir, "runs", job.job_id, job.current_run_id, "metrics.jsonl")
        assert os.path.exists(metrics_file)

        with open(metrics_file) as f:
            lines = [json.loads(line) for line in f if line.strip()]
        assert len(lines) >= 2
        assert lines[0]["step"] == 1
        assert lines[1]["step"] == 2


def test_strict_s3_upload_failure_fails_job_with_artifact_sync_error(db: Session, monkeypatch):
    v_tag = f"v_s3_fail_{uuid.uuid4().hex[:4]}"
    dv, teacher, school = create_orchestration_dataset(db, v_tag, "SMA S3 Strict Test")

    # Explicitly ensure EQUIGRADE_STRICT_CLOUD_SYNC is not set, proving S3 is fail-closed by default
    monkeypatch.delenv("EQUIGRADE_STRICT_CLOUD_SYNC", raising=False)

    # 1. Create job using dummy S3 store without network failure yet
    job = JobRunner.create_job(
        db=db,
        raw_config={"dataset_version_tag": v_tag, "execution_mode": "CPU_TEST"},
        school_id=school.id,
        base_artifact_uri="s3://equigrade-mock-bucket",
    )

    # 2. Mock boto3 client to raise an exception on upload during execution
    class MockFailingS3Client:
        def upload_file(self, *args, **kwargs):
            raise ConnectionError("AWS S3 Connection Refused")

    import sys

    class MockBoto3Module:
        def client(self, name):
            return MockFailingS3Client()

    monkeypatch.setitem(sys.modules, "boto3", MockBoto3Module())

    # 3. Start job -> must catch S3 failure and mark job FAILED with ARTIFACT_SYNC_FAILED
    failed_job = JobRunner.start_job(
        db=db,
        job_id=job.job_id,
        school_id=school.id,
        base_artifact_uri="s3://equigrade-mock-bucket",
    )

    assert failed_job.status == TrainingJobStatus.FAILED
    assert failed_job.failure_code == "ARTIFACT_SYNC_FAILED"
    assert "Durable cloud artifact synchronization failure" in failed_job.error_message


def test_total_steps_accurately_reflects_epoch_and_sample_count(db: Session):
    v_tag = f"v_total_steps_{uuid.uuid4().hex[:4]}"
    dv, teacher, school = create_orchestration_dataset(db, v_tag, "SMA Steps Math")

    with tempfile.TemporaryDirectory() as tmpdir:
        job = JobRunner.create_job(
            db=db,
            raw_config={
                "dataset_version_tag": v_tag,
                "execution_mode": "CPU_TEST",
                "training": {
                    "num_train_epochs": 5,
                    "per_device_train_batch_size": 2,
                    "gradient_accumulation_steps": 1,
                    "save_steps": 1,
                    "eval_steps": 1,
                },
            },
            school_id=school.id,
            base_artifact_uri=tmpdir,
        )

        completed_job = JobRunner.start_job(
            db, job.job_id, school_id=school.id, base_artifact_uri=tmpdir
        )
        assert completed_job.status == TrainingJobStatus.COMPLETED
        # Dataset has 2 train examples, batch size 2 -> 1 step/epoch * 5 epochs = 5 total steps
        assert completed_job.total_steps == 5
        assert completed_job.current_step == 5


def test_evaluating_state_transitions_back_to_running_before_completion(db: Session):
    v_tag = f"v_eval_lifecycle_{uuid.uuid4().hex[:4]}"
    dv, teacher, school = create_orchestration_dataset(db, v_tag, "SMA Eval Lifecycle")

    with tempfile.TemporaryDirectory() as tmpdir:
        job = JobRunner.create_job(
            db=db,
            raw_config={
                "dataset_version_tag": v_tag,
                "execution_mode": "CPU_TEST",
                "training": {
                    "num_train_epochs": 3,
                    "save_steps": 1,
                    "eval_steps": 1,
                },
            },
            school_id=school.id,
            base_artifact_uri=tmpdir,
        )

        observed_states = []
        orig_update_status = training_job_repository.update_status

        def tracking_update_status(db_session, job_id, status, *args, **kwargs):
            observed_states.append(status)
            return orig_update_status(db_session, job_id, status, *args, **kwargs)

        with unittest.mock.patch.object(
            training_job_repository, "update_status", side_effect=tracking_update_status
        ):
            JobRunner.start_job(db, job.job_id, school_id=school.id, base_artifact_uri=tmpdir)

        # Verify state machine visited EVALUATING and transitioned back to RUNNING
        assert TrainingJobStatus.EVALUATING in observed_states
        eval_idx = observed_states.index(TrainingJobStatus.EVALUATING)
        # Next state after first eval should be RUNNING
        assert observed_states[eval_idx + 1] == TrainingJobStatus.RUNNING


def test_s3_checkpoint_hydration_downloads_checkpoint_locally_on_resume(db: Session, monkeypatch):
    v_tag = f"v_s3_hydrate_{uuid.uuid4().hex[:4]}"
    dv, teacher, school = create_orchestration_dataset(db, v_tag, "SMA S3 Hydrate")

    with tempfile.TemporaryDirectory() as tmpdir:
        job = JobRunner.create_job(
            db=db,
            raw_config={"dataset_version_tag": v_tag, "execution_mode": "CPU_TEST"},
            school_id=school.id,
            base_artifact_uri=tmpdir,
        )

        training_job_repository.update_status(
            db, job.job_id, TrainingJobStatus.FAILED, school_id=school.id
        )

        # Mock download_checkpoint on store
        mock_hydrated_dir = os.path.join(tmpdir, "hydrated_local_ckpt")
        os.makedirs(mock_hydrated_dir, exist_ok=True)
        with open(os.path.join(mock_hydrated_dir, "trainer_state.json"), "w") as f:
            json.dump({"global_step": 1}, f)

        def mock_download_ckpt(self, remote_uri, target_dir):
            shutil.copytree(mock_hydrated_dir, target_dir, dirs_exist_ok=True)
            return target_dir

        with unittest.mock.patch.object(S3ArtifactStore, "download_checkpoint", mock_download_ckpt):
            with unittest.mock.patch.object(
                S3ArtifactStore, "_upload_file_to_s3", lambda *args, **kwargs: None
            ):
                resumed = JobRunner.resume_job(
                    db=db,
                    job_id=job.job_id,
                    checkpoint_path=f"s3://my-bucket/runs/{job.job_id}/run_1/checkpoint-1",
                    school_id=school.id,
                    base_artifact_uri="s3://my-bucket",
                )

            assert resumed.status == TrainingJobStatus.COMPLETED
            assert resumed.parent_run_id is not None


def test_resume_job_with_explicit_checkpoint_and_additional_epochs(db: Session):
    v_tag = f"v_resume_explicit_{uuid.uuid4().hex[:4]}"
    dv, teacher, school = create_orchestration_dataset(db, v_tag, "SMA Resume Explicit")

    with tempfile.TemporaryDirectory() as tmpdir:
        job = JobRunner.create_job(
            db=db,
            raw_config={
                "dataset_version_tag": v_tag,
                "execution_mode": "CPU_TEST",
                "training": {"num_train_epochs": 2, "save_steps": 1, "eval_steps": 1},
            },
            school_id=school.id,
            base_artifact_uri=tmpdir,
        )

        # Mark as FAILED
        training_job_repository.update_status(
            db, job.job_id, TrainingJobStatus.FAILED, school_id=school.id
        )

        # Resume with explicit additional epochs
        resumed = JobRunner.resume_job(
            db=db,
            job_id=job.job_id,
            school_id=school.id,
            additional_epochs=2,
            base_artifact_uri=tmpdir,
        )

        assert resumed.status == TrainingJobStatus.COMPLETED
        assert resumed.total_epochs == 4  # 2 + 2 additional epochs
        assert resumed.retry_count == 1


def test_concurrent_worker_claim_conflict_raises_error(db: Session):
    v_tag = f"v_concurrent_{uuid.uuid4().hex[:4]}"
    dv, teacher, school = create_orchestration_dataset(db, v_tag, "SMA Concurrent Lock")

    with tempfile.TemporaryDirectory() as tmpdir:
        job = JobRunner.create_job(
            db=db,
            raw_config={"dataset_version_tag": v_tag, "execution_mode": "CPU_TEST"},
            school_id=school.id,
            base_artifact_uri=tmpdir,
        )

        # Worker 1 successfully claims and starts the job
        training_job_repository.claim_and_initialize_job(
            db, job.job_id, worker_id="worker_alpha", school_id=school.id
        )

        # Worker 2 attempts to start the same job -> must raise RuntimeError concurrency conflict
        with pytest.raises(RuntimeError, match="Concurrency conflict"):
            JobRunner.start_job(
                db,
                job.job_id,
                worker_id="worker_beta",
                school_id=school.id,
                base_artifact_uri=tmpdir,
            )


def test_local_artifact_store_commonpath_containment_rejection():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalArtifactStore(base_dir=tmpdir, job_id="job_x", run_id="run_1")
        # Attacker tries subtle non-prefix traversal e.g. "run_10/file.txt"
        with pytest.raises(ValueError, match="path traversal detected"):
            store.get_full_path("../run_10/file.txt")


def test_metrics_logger_records_full_telemetry_fields(db: Session):
    v_tag = f"v_telemetry_{uuid.uuid4().hex[:4]}"
    dv, teacher, school = create_orchestration_dataset(db, v_tag, "SMA Telemetry Test")

    with tempfile.TemporaryDirectory() as tmpdir:
        job = JobRunner.create_job(
            db=db,
            raw_config={
                "dataset_version_tag": v_tag,
                "execution_mode": "CPU_TEST",
                "training": {"num_train_epochs": 1, "save_steps": 1, "eval_steps": 1},
            },
            school_id=school.id,
            base_artifact_uri=tmpdir,
        )

        JobRunner.start_job(db, job.job_id, school_id=school.id, base_artifact_uri=tmpdir)
        metrics_file = os.path.join(tmpdir, "runs", job.job_id, job.current_run_id, "metrics.jsonl")
        assert os.path.exists(metrics_file)

        with open(metrics_file) as f:
            lines = [json.loads(line) for line in f if line.strip()]

        assert len(lines) > 0
        first = lines[0]
        assert "grad_norm" in first
        assert "tokens_processed" in first
        assert "elapsed_seconds" in first
        assert first["tokens_processed"] > 0
        assert first["elapsed_seconds"] >= 0.0


def test_job_config_schema_rejects_invalid_enum_values():
    from pydantic import ValidationError

    # Invalid execution_mode
    with pytest.raises(ValidationError):
        JobConfigParser.parse_and_validate(
            {
                "dataset_version_tag": "v_test",
                "execution_mode": "INVALID_MODE",
            }
        )

    # Invalid lr_scheduler_type
    with pytest.raises(ValidationError):
        JobConfigParser.parse_and_validate(
            {
                "dataset_version_tag": "v_test",
                "training": {"lr_scheduler_type": "super_decay"},
            }
        )


def test_durable_sync_happens_strictly_before_status_completed(db: Session):
    v_tag = f"v_sync_order_{uuid.uuid4().hex[:4]}"
    dv, teacher, school = create_orchestration_dataset(db, v_tag, "SMA Sync Order")

    with tempfile.TemporaryDirectory() as tmpdir:
        job = JobRunner.create_job(
            db=db,
            raw_config={"dataset_version_tag": v_tag, "execution_mode": "CPU_TEST"},
            school_id=school.id,
            base_artifact_uri=tmpdir,
        )

        event_order = []

        store = get_artifact_store(tmpdir, job.job_id, job.current_run_id)
        orig_sync = store.sync_to_remote
        orig_update_status = training_job_repository.update_status

        def tracking_sync(*args, **kwargs):
            event_order.append("sync_to_remote")
            return orig_sync(*args, **kwargs)

        def tracking_update_status(db_session, job_id, status, *args, **kwargs):
            if status == TrainingJobStatus.COMPLETED:
                event_order.append("status_COMPLETED")
            return orig_update_status(db_session, job_id, status, *args, **kwargs)

        with unittest.mock.patch.object(LocalArtifactStore, "sync_to_remote", tracking_sync):
            with unittest.mock.patch.object(
                training_job_repository, "update_status", tracking_update_status
            ):
                JobRunner.start_job(db, job.job_id, school_id=school.id, base_artifact_uri=tmpdir)

        # Confirm sync_to_remote occurred BEFORE status_COMPLETED
        assert "sync_to_remote" in event_order
        assert "status_COMPLETED" in event_order
        sync_idx = event_order.index("sync_to_remote")
        completed_idx = event_order.index("status_COMPLETED")
        assert sync_idx < completed_idx


def test_resume_job_rejects_unauthorized_foreign_checkpoint_path(db: Session):
    v_tag = f"v_sec_resume_{uuid.uuid4().hex[:4]}"
    dv, teacher, school = create_orchestration_dataset(db, v_tag, "SMA Resume Auth")

    with tempfile.TemporaryDirectory() as tmpdir:
        job = JobRunner.create_job(
            db=db,
            raw_config={"dataset_version_tag": v_tag, "execution_mode": "CPU_TEST"},
            school_id=school.id,
            base_artifact_uri=tmpdir,
        )

        training_job_repository.update_status(
            db, job.job_id, TrainingJobStatus.FAILED, school_id=school.id
        )

        # Attempt to resume with foreign checkpoint from another job
        foreign_ckpt = "s3://my-bucket/runs/job_attacker_foreign/run_1/checkpoint-100"
        with pytest.raises(PermissionError, match="Security violation: Checkpoint URI"):
            JobRunner.resume_job(
                db=db,
                job_id=job.job_id,
                checkpoint_path=foreign_ckpt,
                school_id=school.id,
                base_artifact_uri=tmpdir,
            )


def test_cancellation_with_failing_s3_sync_marks_job_failed(db: Session, monkeypatch):
    v_tag = f"v_cancel_sync_fail_{uuid.uuid4().hex[:4]}"
    dv, teacher, school = create_orchestration_dataset(db, v_tag, "SMA Cancel Fail")

    with tempfile.TemporaryDirectory() as tmpdir:
        job = JobRunner.create_job(
            db=db,
            raw_config={
                "dataset_version_tag": v_tag,
                "execution_mode": "CPU_TEST",
                "training": {"num_train_epochs": 10},
            },
            school_id=school.id,
            base_artifact_uri=tmpdir,
        )

        # Mock sync_to_remote raising ArtifactSyncError during cancellation flush
        def failing_sync(*args, **kwargs):
            raise ArtifactSyncError("AWS S3 Connection dropped during cancellation flush")

        with unittest.mock.patch.object(LocalArtifactStore, "sync_to_remote", failing_sync):
            # Request cancellation before start_job begins loop
            # Note: in cooperative cancellation loop, SftTrainingEngine raises TrainingCancelledError
            def mock_run_training(*args, **kwargs):
                raise TrainingCancelledError("Cancelled midway")

            with unittest.mock.patch.object(SftTrainingEngine, "run_training", mock_run_training):
                res = JobRunner.start_job(
                    db, job.job_id, school_id=school.id, base_artifact_uri=tmpdir
                )

        assert res.status == TrainingJobStatus.FAILED
        assert res.failure_code == "ARTIFACT_SYNC_FAILED"
        assert "durable artifact sync failed" in res.error_message
