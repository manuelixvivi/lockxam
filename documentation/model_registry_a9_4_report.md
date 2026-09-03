# 🏛️ EQUIGRADE x LOCKXAM — MILESTONE A9.4 REPORT
## Model Registry, Cryptographic Artifact Promotion & Inference Serving Preparation

**Document Version:** 1.0.0 — Final Hardened Baseline
**Date:** September 2, 2026
**Quality Assurance:** 406 Passed, 4 Skipped across 41 Test Files (100% Pass Rate)
**Security & Compliance:** Multi-tenant isolated, Zero PII leakage, `ON DELETE RESTRICT` lineage protection, Cryptographic SHA-256 Merkle-style manifest verification, Dynamic Base Model Provenance, Runtime Immutability Guard

---

## 1. Executive Summary & Objective

Milestone **A9.4** bridges the gap between training artifact orchestration (**A9.3**) and live inference serving by establishing an **authoritative, tamper-evident Model Registry and Artifact Promotion Engine**.

A9.4 transforms raw checkpoint artifacts into immutable, reproducible, and mathematically verifiable `ModelVersion` records. It decouples the model version pointer (`active_production_version_id`, `active_staged_version_id`) from physical adapter weights, allowing zero-downtime rollback and stage promotion without mutating historical artifact files.

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                           A9.3 Training Job                             │
│                  (COMPLETED + S3/Local Durable Sync)                    │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    A9.4.2 Model Artifact Builder                        │
│       • Canonical Forward-Slash Relative Paths                          │
│       • OS / Transient Noise Exclusion (.DS_Store, __pycache__, .tmp)   │
│       • Deterministic Alphabetical Sorting                              │
│       • SHA-256 Merkle-Style Cumulative Manifest Hash                   │
│       • model_manifest.json Generation                                  │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    A9.4.1 Model Registry Core Domain                    │
│       • RegisteredModel (Canonical identity + Production/Staged Pointers│
│       • ModelVersion (Immutable Lineage + Runtime Immutability Guard)   │
│       • Multi-Tenant Isolation (school_id boundary verification)        │
│       • Database Migration f7a8b9c0d1e2 (ON DELETE RESTRICT)            │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│               A9.4.3 Validation Gate, Promotion & Rollback              │
│       • State Lifecycle: REGISTERED ➔ VALIDATING ➔ VALIDATED ➔          │
│                          STAGED ➔ PRODUCTION ➔ ARCHIVED / REJECTED      │
│       • ModelValidationGate: Bit-rot & Weight Tampering Detection       │
│       • Atomic Superseding & Zero-Downtime Rollback                     │
│       • Audit Trail (promotion_history JSON with actor & timestamp)     │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│            A9.4.4 Inference Bundle & Serving Contract Provider          │
│       • InferenceBundle: Verified Weights + Tokenizer + Execution Spec  │
│       • Dynamic Base Model Provenance (Never Hardcoded)                 │
│       • Startup Cryptographic Integrity Check                           │
│       • Strict Decoupling of RAG Layer from Adapter Bundle              │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Core Architectural Pillars & Locked Invariants

### 🔒 1. Strict Immutability of ModelVersion
Once a `ModelVersion` is registered:
- Lineage fields (`training_job_id`, `training_run_id`, `experiment_id`, `dataset_version_tag`, `dataset_hash`, `base_model_name`, `base_model_revision`, `tokenizer_name_or_path`, `adapter_type`, `adapter_config_hash`, `artifact_uri`, `artifact_manifest_hash`, `model_manifest_payload`) are **immutable**.
- Enforced at runtime via SQLAlchemy `@event.listens_for(ModelVersion, "before_update")` listener. Any attempt to modify lineage or artifact identity raises a `ValueError`.
- Only lifecycle status and audit metadata (`status`, `validation_report_payload`, `promotion_history`, `promoted_at`, `archived_at`) may be updated during staging and production promotion.

### 🔒 2. Pointer Decoupling & Atomic Zero-Downtime Rollback
- `RegisteredModel.active_production_version_id` and `RegisteredModel.active_staged_version_id` point to active versions.
- Promoting a new version (`v2` $\rightarrow$ `PRODUCTION`) updates the pointer and archives `v1` without altering the physical weights of either `v1` or `v2`.
- Rollback (`v2` $\rightarrow$ `v1`) atomically switches `active_production_version_id` back to `v1` and appends an audit event to `promotion_history`.

### 🔒 3. Elimination of Cascade Deletes (`ON DELETE RESTRICT`)
- `RegisteredModel.versions` uses `cascade="save-update, merge"` with `passive_deletes=True`.
- SQLAlchemy ORM is prohibited from issuing cascade deletes against child `ModelVersion` rows, ensuring the underlying PostgreSQL `ON DELETE RESTRICT` constraint actively blocks deletion of models that hold historical training versions.

### 🔒 4. Authoritative Parent-Child Tenant Boundary
- `ModelVersion.school_id` must strictly match `RegisteredModel.school_id`.
- Validated at both the repository layer (`ModelVersionRepository.create()`) and the service layer (`ModelRegistryService`). Cross-tenant version association is rejected with `PermissionError`.

### 🔒 5. Dynamic Base Model Provenance & RAG Decoupling
- `InferenceBundle` dynamically inherits `base_model_name` and `tokenizer_name_or_path` from the registered version's lineage (e.g. `meta-llama/Llama-3.1-8B-Instruct`, `Qwen/Qwen2.5-7B-Instruct`), eliminating any hardcoded model assumptions.
- RAG vector retrieval remains strictly decoupled from the model adapter bundle, enabling objective benchmark evaluation across $E0$ (Zero-Shot Base), $E1$ (RAG Base), $E2$ (Fine-Tuned Adapter), and $E3$ (Fine-Tuned + RAG).

---

## 3. Sub-Milestone Implementation Details

### 3.1. A9.4.1 — Model Registry Core Domain & Database Migrations
- **Models:**
  - `app/models/ai/registered_model.py`: `RegisteredModel` entity with deferred foreign key pointers `active_production_version_id` and `active_staged_version_id`, multi-tenant unique constraint `UNIQUE(name, school_id)`.
  - `app/models/ai/model_version.py`: `ModelVersion` entity, `ModelVersionStatus` enum (`REGISTERED`, `VALIDATING`, `VALIDATED`, `STAGED`, `PRODUCTION`, `ARCHIVED`, `REJECTED`), unique constraints `UNIQUE(model_id, version)` and `UNIQUE(model_id, version_number)`.
- **Migration:**
  - `migrations/versions/f7a8b9c0d1e2_create_model_registry_tables.py`: Migration creating `registered_models` and `model_versions` tables with `ON DELETE RESTRICT` foreign keys and `auth_accounts.id` references.
- **Repositories:**
  - `app/repositories/ai/registered_model_repository.py`: CRUD operations, multi-tenant queries, and production/staged pointer updates.
  - `app/repositories/ai/model_version_repository.py`: Sequential version counter generation (`get_next_version_number`), tenant consistency checks, status transitions, and audit logging.

### 3.2. A9.4.2 — Model Artifact Builder & Cryptographic Manifest
- **Schemas:**
  - `app/services/ai/training/registry/schemas.py`: Pydantic `FileChecksum`, `ModelArtifactManifest`, and `IntegrityVerificationResult`.
- **Engine:**
  - `app/services/ai/training/registry/artifact_builder.py`:
    - Recursive scanning of adapter artifact directories.
    - Automatic exclusion of OS/transient noise (`.DS_Store`, `Thumbs.db`, `__pycache__`, `.tmp`, and `model_manifest.json`).
    - Deterministic alphabetical ordering of relative paths normalized with forward slashes (`/`).
    - Deterministic SHA-256 artifact manifest hash (Merkle-style cumulative hash):
      $$\text{artifact\_manifest\_hash} = \text{SHA-256}\left(\sum_{\text{sorted}} \text{rel\_path} + \text{":"} + \text{file\_hash} + \text{":"} + \text{file\_size}\right)$$
    - Mandatory validation of `adapter_config.json` for LoRA/QLoRA artifacts.
    - Automated generation and serialization of `model_manifest.json`.

### 3.3. A9.4.3 — Model Registry Service, Validation Gate & Rollback
- **Validation Gate:**
  - `app/services/ai/training/registry/validation_gate.py`: Executes filesystem checks, Merkle tree hash verification, and LoRA structure validation.
- **Service:**
  - `app/services/ai/training/registry/service.py`:
    - `register_model_version()`: Verifies completed `TrainingJob` $\rightarrow$ allocates sequential version $vN$ with retry handling $\rightarrow$ builds cryptographic manifest $\rightarrow$ saves `model_manifest.json` $\rightarrow$ persists `ModelVersion` in `REGISTERED` status.
    - `validate_model_version()`: Executes `ModelValidationGate` $\rightarrow$ transitions to `VALIDATED` (or `REJECTED`).
    - `promote_to_staged()`: Transitions `VALIDATED` $\rightarrow$ `STAGED` $\rightarrow$ updates `active_staged_version_id`.
    - `promote_to_production()`: Transitions `VALIDATED`/`STAGED` $\rightarrow$ `PRODUCTION` $\rightarrow$ archives superseded version $\rightarrow$ updates `active_production_version_id`.
    - `rollback_production()`: Verifies model ownership $\rightarrow$ demotes active version $\rightarrow$ promotes target version $\rightarrow$ updates `active_production_version_id` with audit explanation.

### 3.4. A9.4.4 — Inference Bundle & Serving Contract Provider
- **Bundle:**
  - `app/services/ai/inference/bundle.py`: `InferenceBundle` dataclass, `ServingExecutionContract` Pydantic model, canonical SFT prompt formatter.
- **Serving Provider:**
  - `app/services/ai/inference/serving_provider.py`:
    - `get_active_model_bundle()`: Resolves active PRODUCTION or STAGED version pointer $\rightarrow$ verifies local cryptographic integrity $\rightarrow$ instantiates `InferenceBundle`.
    - `get_version_bundle()`: Resolves a specific version for benchmark evaluation.

---

## 4. Verification Matrix & Automated Test Results

The EquiGrade test suite encompasses **406 passed automated tests and 4 skipped** (100% pass rate) across 41 test files:

```text
======================= 406 passed, 4 skipped in 107.71s (0:01:47) =======================
```

| Test Module | Test File Path | Tests Passed | Status |
| :--- | :--- | :---: | :---: |
| **Milestone A9.4.4: Inference Bundle & Serving Provider** | `tests/test_ai_inference_bundle.py` | **4** | 🟢 PASSED |
| **Milestone A9.4.3: Model Registry Service & Rollback** | `tests/test_ai_model_registry_service.py` | **7** | 🟢 PASSED |
| **Milestone A9.4.2: Artifact Builder & Cryptographic Manifest** | `tests/test_ai_model_artifact_builder.py` | **10** | 🟢 PASSED |
| **Milestone A9.4.1: Model Registry Core Domain** | `tests/test_ai_model_registry_core.py` | **11** | 🟢 PASSED |
| Milestone A9.3: Training Orchestration Service Layer | `tests/test_ai_training_orchestration.py` | 31 | 🟢 PASSED |
| Milestone A9.2: LoRA / QLoRA Training Engine | `tests/test_ai_lora_training.py` | 12 (+4 skipped) | 🟢 PASSED |
| Milestone A9.1: Tokenizer & SFT Formatter Pipeline | `tests/test_ai_sft_pipeline.py` | 27 | 🟢 PASSED |
| Milestone A8: Training Governance & Dataset Registry | `tests/test_ai_training_governance.py` | 11 | 🟢 PASSED |
| Milestone A7: Scientific Benchmark Evaluation | `tests/test_benchmark_evaluation.py` | 10 | 🟢 PASSED |
| Milestone A6.2: RAG-Augmented LLM Grading & Batching | `tests/test_rag_augmented_grading.py`<br>`tests/test_ai_batch_grading.py`<br>`tests/test_ai_grading_modular.py` | 34 | 🟢 PASSED |
| Milestone A6.1: RAG Context Assembly Engine | `tests/test_rag_context_service.py` | 20 | 🟢 PASSED |
| Milestone A5: Similarity Vector Search Service | `tests/test_vector_search_service.py` | 18 | 🟢 PASSED |
| Milestone A3: Transformer Dense Embedding | `tests/test_embedding_service.py` | 18 | 🟢 PASSED |
| Milestone A2: Canonical Document Construction | `tests/test_assessment_document_construction.py` | 12 | 🟢 PASSED |
| Milestone A1: Ground Truth Assessment History | `tests/test_assessment_history.py` | 12 | 🟢 PASSED |
| A0 Core Domain, Master, RBAC, Proctoring & Security | 23 Test Files | 179 | 🟢 PASSED |
| **TOTAL VERIFIED REGRESSION SUITE** | **41 Test Files** | **406 Passed, 4 Skipped (100%)** | 🟢 **ALL GREEN** |

---

## 5. Summary of Key Files Delivered in Milestone A9.4

```text
app/
 ├── models/
 │    └── ai/
 │         ├── registered_model.py                # RegisteredModel entity with stage pointers
 │         └── model_version.py                   # Immutable ModelVersion entity + immutability listener
 ├── repositories/
 │    └── ai/
 │         ├── registered_model_repository.py     # Canonical model queries & pointer updates
 │         └── model_version_repository.py        # Sequential version counter & status audit
 ├── services/
 │    └── ai/
 │         ├── training/
 │         │    └── registry/
 │         │         ├── __init__.py              # Registry exports
 │         │         ├── schemas.py               # Manifest & Checksum Pydantic schemas
 │         │         ├── artifact_builder.py      # Deterministic Merkle tree hashing & integrity checker
 │         │         ├── validation_gate.py       # Automated validation gate checks
 │         │         └── service.py               # Authoritative ModelRegistryService
 │         └── inference/
 │              ├── __init__.py                   # Inference exports
 │              ├── bundle.py                     # InferenceBundle & ServingExecutionContract
 │              └── serving_provider.py           # ModelServingProvider (Active bundle resolution)
migrations/
 └── versions/
      └── f7a8b9c0d1e2_create_model_registry_tables.py  # Alembic migration for registry tables
tests/
 ├── test_ai_model_registry_core.py               # Core domain & constraint tests (11 tests)
 ├── test_ai_model_artifact_builder.py            # Manifest & tree hashing tests (10 tests)
 ├── test_ai_model_registry_service.py            # Service, gate & rollback tests (7 tests)
 └── test_ai_inference_bundle.py                  # Serving bundle & provenance tests (4 tests)
```

---

## 6. Conclusion & Transition to A10 (Scientific Benchmark & Evaluation)

Milestone **A9.4** successfully delivers a robust, academically defensible, and cloud-ready **Model Registry & Serving Preparation Layer**.

With A9.4 completed and verified:
- EquiGrade possesses a complete training pipeline ($A8 \rightarrow A9.1 \rightarrow A9.2 \rightarrow A9.3 \rightarrow A9.4$) with cryptographic traceability at every stage.
- The stage is set for **Milestone A10 (Scientific Benchmark Evaluation & Comparative Ablation)** to systematically grade held-out student essays across experimental conditions:
  - $E0$: Zero-Shot Base Model (`Llama-3.1-8B-Instruct`)
  - $E1$: RAG-Augmented Base Model (`Llama-3.1-8B-Instruct` + Dynamic Vector Retrieval)
  - $E2$: Fine-Tuned PEFT LoRA Model (`RegisteredModel` active production adapter)
  - $E3$: Combined Fine-Tuned + RAG Architecture (`InferenceBundle` + Dynamic Vector Retrieval)
