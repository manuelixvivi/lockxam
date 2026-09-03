# 🚀 EquiGrade Milestone A9.3: Training Orchestration Service Layer Report

> **Milestone:** A9.3 — Training Job Orchestration Service Layer, Worker-Compatible Execution Contract, Default Fail-Closed S3 Storage Sync & Remote Checkpoint Hydration, Atomic Worker Claim Locking, Checkpoint Namespace Authorization, Canonical Path Traversal Protection, Strict Enum Schema Validation, and Pre-Completion Storage Durability Verification
> **Status:** 🟢 A9.3 FINAL FROZEN — ORCHESTRATION SERVICE CONTRACT HARDENED & VERIFIED
> **A9.3 Test Suite:** 31 tests (`tests/test_ai_training_orchestration.py`)
> **Full Regression Suite:** 374 passed, 4 skipped in 92.25s (100% Pass Rate)

---

## 1. Executive Summary & Architectural Positioning

Milestone A9.3 delivers the **Training Job Orchestration Service Layer**. It establishes an observable, reproducible, resilient, multi-tenant, and worker-compatible service boundary on top of the A9.2 LoRA / QLoRA SFT Training Engine.

### 📐 Architectural Clarification & Scope Boundary

1. **Orchestration Contract vs. Distributed Infrastructure**:
   - A9.3 implements the **Training Orchestration Service Layer & Execution Lifecycle Contract** (`JobConfigParser`, `JobRunner`, `ArtifactStore`, `MetricsLogger`, `ManifestBuilder`, `TrainingJobRepository`).
   - It provides **atomic worker claim locking** (`claim_and_initialize_job`) and cooperative heartbeat/cancellation hooks designed for worker compatibility.
   - Distributed background queue consumers (e.g. AWS SQS, Celery, or dedicated EC2 GPU daemon processes) and HTTP API endpoints belong to dedicated cloud infrastructure and API integration milestones.
2. **Heartbeat & Stale Job Detection**:
   - A9.3 provides repository-level heartbeat updates and stale job detection querying. Periodic background cron/daemon execution of stale sweepers is positioned in the worker daemon layer.

```text
========================================================================================
                          EQUIGRADE MILESTONE A9.3 ARCHITECTURE
========================================================================================

                 ┌──────────────────────────────────────────────────┐
                 │          EquiGrade Application / Service Layer   │
                 │         (Multi-Tenant Governance & DB Session)   │
                 └────────────────────────┬─────────────────────────┘
                                          │ create_job / start_job / resume_job
                                          ▼
┌───────────────────────────────────────────────────────────────────────────────────────┐
│              MILESTONE A9.3: TRAINING JOB ORCHESTRATION SERVICE LAYER                 │
│                                                                                       │
│  ├── JobConfigParser      : Declarative YAML/JSON parsing with strict Literal schemas │
│  ├── JobRunner            : State Machine (QUEUED -> RUNNING -> EVALUATING -> DONE)   │
│  ├── Atomic Claim Lock    : claim_and_initialize_job (prevents duplicate runs)        │
│  ├── Fail-Closed Cloud S3 : strict_mode=True by default for S3 storage operations     │
│  ├── Storage Durability   : S3 sync verified BEFORE state transition to COMPLETED     │
│  ├── Security Authorization: Checkpoint URI restricted to caller job namespace        │
│  ├── Local Artifact Store : Canonical commonpath containment validation               │
│  ├── MetricsLogger        : Step-level loss, PPL, LR, grad_norm, tokens, elapsed_sec  │
│  ├── StepCalculator       : Shared deterministic step & epoch math across engine/run  │
│  └── ManifestBuilder      : Full reproducibility manifest with honest git metadata    │
└─────────────────────────────────────────┬─────────────────────────────────────────────┘
                                          │ Cooperative Callbacks (Cancel, Step, Eval)
                                          ▼
┌───────────────────────────────────────────────────────────────────────────────────────┐
│                        MILESTONE A9.2: SFT TRAINING ENGINE                            │
│                        (Pure PyTorch / LoRA / QLoRA Compute)                          │
│                                                                                       │
│  ├── Model & PEFT Loader      ├── PyTorch Gradient Loop (AdamW + Cosine/Linear)       │
│  ├── Token Collator & Masking └── Validation Loss & Perplexity (no_grad)              │
└─────────────────────────────────────────┬─────────────────────────────────────────────┘
                                          │ Executes on
                                          ▼
                      ┌─────────────────────────────────────────┐
                      │             COMPUTE RUNTIME             │
                      │  • Local CPU / Mock (Test Harness)      │
                      │  • Local NVIDIA GPU (CUDA)              │
                      │  • Apple Silicon (MPS)                  │
                      │  • AWS EC2 GPU (G4dn / G5 instances)    │
                      └─────────────────────────────────────────┘
========================================================================================
```

---

## 2. Hardening & Security Implementation Details

### 🛡️ 1. Fail-Closed Cloud Durability by Default
- `S3ArtifactStore` defaults to `strict_mode=True` (without requiring explicit environment flags).
- If any S3 operation fails during training or artifact synchronization, `ArtifactSyncError` is raised and the job transitions immediately to `FAILED` with `failure_code="ARTIFACT_SYNC_FAILED"`.
- `artifact_store.sync_to_remote()` is verified **before** transitioning database job status to `COMPLETED`.

### 🛡️ 2. Checkpoint URI Namespace Authorization
- `JobRunner.resume_job()` strictly validates that `checkpoint_path` belongs to the requesting job's artifact namespace (`job_id in checkpoint_path`).
- Foreign checkpoint URI injection across distinct jobs or tenants is rejected with `PermissionError`.

### 🛡️ 3. Cancellation Artifact Failure Semantics
- In `JobRunner.start_job()`, if durable sync fails during cooperative cancellation flush, the job transitions to `FAILED` (`failure_code="ARTIFACT_SYNC_FAILED"`), preserving strict cloud observability.

### 🛡️ 4. Canonical Path Traversal Defense (`os.path.commonpath`)
- In `LocalArtifactStore`, canonical containment verification using `os.path.commonpath([normcase(root), normcase(full_path)])` prevents sibling directory path traversal.

### 🛡️ 5. Atomic Concurrency Claim Lock (`claim_and_initialize_job`)
- `TrainingJobRepository.claim_and_initialize_job` uses database row locks (`with_for_update()`), preventing duplicate execution race conditions across concurrent workers.

### 🛡️ 6. Unified `TrainingStepCalculator`
- Both `JobRunner` and `SftTrainingEngine` use the shared static helper `TrainingStepCalculator.calculate_steps(...)`.

---

## 3. Dedicated Automated Test Matrix (31 Tests in `tests/test_ai_training_orchestration.py`)

| Test Function | Verification Scope | Status |
| :--- | :--- | :---: |
| `test_job_config_parser_and_validation` | Declarative config parsing and parameter sanity rejection | ✅ Passed |
| `test_training_job_state_machine_happy_path` | Complete lifecycle transition: QUEUED $\rightarrow$ INITIALIZING $\rightarrow$ RUNNING $\rightarrow$ COMPLETED | ✅ Passed |
| `test_training_job_fails_gracefully_on_preflight_error` | Pre-flight rejection on corrupted dataset hash and FAILED state transition | ✅ Passed |
| `test_metrics_logger_streams_jsonl_records` | Real-time JSONL step metric appending and stream reading | ✅ Passed |
| `test_artifact_manager_creates_standard_layout` | Verifikasi hierarki folder terpadu `runs/<job_id>/<run_id>/` | ✅ Passed |
| `test_training_job_manifest_builder_records_environment` | Snapshot dependency, status Git, CUDA, & hardware di `training_manifest.json` | ✅ Passed |
| `test_cancel_request_is_graceful` | Transisi pembatalan bertahap dari CANCEL_REQUESTED ke graceful CANCELLED | ✅ Passed |
| `test_stale_running_job_is_detected` | Automatic timeout detection of crashed worker jobs to STALE | ✅ Passed |
| `test_resume_creates_new_run_and_preserves_job_identity` | Resuming failed jobs with new `run_id` linked to `parent_run_id` | ✅ Passed |
| `test_tenant_isolation_for_training_jobs` | Cross-school isolation forbidding unauthorized job query and execution | ✅ Passed |
| `test_artifact_store_interface_local_and_s3` | Storage interface verification across Local and S3 schemes | ✅ Passed |
| `test_artifact_isolation_between_jobs` | Complete directory isolation between distinct training jobs | ✅ Passed |
| `test_metrics_logger_handles_process_restart` | Seamless metric stream appending across process restarts | ✅ Passed |
| `test_heartbeat_updates_timestamp_and_worker_id` | Heartbeat timestamp updating and worker registration | ✅ Passed |
| `test_training_job_repository_list_and_filters` | Multi-criteria filtering by status, school, and experiment | ✅ Passed |
| `test_best_adapter_survives_checkpoint_pruning` | Best validation checkpoint protection and final adapter promotion | ✅ Passed |
| `test_path_traversal_protection_raises_security_violation` | Security assertion against path traversal (`../../`) attacks | ✅ Passed |
| `test_cooperative_cancellation_during_active_training` | Emergency checkpoint flush & pembatalan kooperatif saat loop berjalan | ✅ Passed |
| `test_realtime_metrics_streaming_logs_every_step` | Verification of true per-step logging in `metrics.jsonl` | ✅ Passed |
| `test_strict_s3_upload_failure_fails_job_with_artifact_sync_error` | Strict S3 error (fail-closed default) raising ArtifactSyncError & transition to FAILED | ✅ Passed |
| `test_total_steps_accurately_reflects_epoch_and_sample_count` | Exact pre-computed total_steps calculation in database | ✅ Passed |
| `test_evaluating_state_transitions_back_to_running_before_completion` | State transition verification: RUNNING $\rightarrow$ EVALUATING $\rightarrow$ RUNNING | ✅ Passed |
| `test_s3_checkpoint_hydration_downloads_checkpoint_locally_on_resume` | Checkpoint hydration downloading S3 objects down to local staging on resume | ✅ Passed |
| `test_resume_job_with_explicit_checkpoint_and_additional_epochs` | Explicit checkpoint wiring & epoch expansion on resumed jobs | ✅ Passed |
| `test_concurrent_worker_claim_conflict_raises_error` | Atomic claim lock rejecting concurrent worker attempts on the same job | ✅ Passed |
| `test_local_artifact_store_commonpath_containment_rejection` | Canonical commonpath boundary containment rejection | ✅ Passed |
| `test_metrics_logger_records_full_telemetry_fields` | Verification of grad_norm, tokens_processed, and elapsed_seconds in metrics.jsonl | ✅ Passed |
| `test_job_config_schema_rejects_invalid_enum_values` | Strict Literal validation rejecting invalid execution modes and scheduler types | ✅ Passed |
| `test_durable_sync_happens_strictly_before_status_completed` | Execution sequence assertion: durable sync occurs strictly before COMPLETED | ✅ Passed |
| `test_resume_job_rejects_unauthorized_foreign_checkpoint_path` | Security assertion rejecting unauthorized foreign checkpoint paths on resume | ✅ Passed |
| `test_cancellation_with_failing_s3_sync_marks_job_failed` | Strict failure semantics when durable sync fails during cancellation | ✅ Passed |
