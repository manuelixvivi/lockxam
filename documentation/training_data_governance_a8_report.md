# 🏛️ EquiGrade Milestone A8: Training Data Governance & Dataset Management Report

> **Milestone:** A8 — EquiGrade Training Data Governance & Cryptographic Dataset Registry
> **Status:** 🟢 IMPLEMENTED & AUDITED (P0 & P1 Complete with Multi-Tenant Security)
> **Tests Passed:** 11 / 11 tests in `tests/test_ai_training_governance.py` (Full Suite: 304 / 304 tests)

---

## 1. Executive Problem & Architectural Resolution

`AssessmentHistory` acts as the authoritative record of teacher-finalized grading ground truth. Milestone A8 ensures that raw records are curated, anonymized, filtered, and versioned into **reproducible, immutable datasets** ready for future Supervised Fine-Tuning (SFT / PEFT / LoRA / QLoRA):

```text
                       EQUIGRADE DATABASE
                              │
                              ▼
                      AssessmentHistory
                 (Authoritative Teacher Ground Truth)
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
       RAG Knowledge Base              Milestone A8 Pipeline
       (Milestones A1–A6)                     │
                                              ▼
                                   PiiSanitizationService
                                 (Non-destructive Masking)
                                 * Zero raw PII in metadata
                                              │
                                              ▼
                                     QualityGateService
                                 (Multi-Criteria Score Filter)
                                 * Heuristic Quality Screening
                                 * Structural Rubric Validator
                                              │
                                              ▼
                                      TrainingCandidate
                                  (Standardized SFT Format)
                                  * Question Lineage Group Key
                                  * Target Scores & Academic Year
                                              │
                                              ▼
                                    DatasetBuilderService
                              (Question-Group Leakage-Free Split)
                              * Strict Supported Strategy Check
                              * Assessment-Time Temporal Ordering
                              * Strict Ratio Sum Validation
                                              │
                                              ▼
                                        DatasetVersion
                                  (v1.0.0 Immutable Release)
                                  * SHA-256 Dataset Identity Hash
                                  * Frozen Snapshot SFT Payloads
                                  * Tenant & Authenticated Lineage
                                              │
                                  ┌───────────┼───────────┐
                                  ▼           ▼           ▼
                                TRAIN        VAL         TEST
```

---

## 2. Key Security & Governance Achievements

### A. RBAC & Multi-Tenant Authorization Boundary (P0)
- Endpoints `POST /candidates/ingest/{history_id}`, `POST /datasets/build`, and `GET /datasets/{version_tag}/export` require authenticated principal (`SUPERADMIN`, `ADMIN`, `SCHOOL_ADMIN`, `TEACHER`).
- Server-side validation strictly enforces tenant boundaries: non-Superadmin users cannot curate, build, or export datasets belonging to another `school_id` (enforced via HTTP 403 Forbidden).

### B. Privacy Protection: Zero Raw PII in Metadata (P0)
- `PiiSanitizationService` identifies sensitive entities (emails, Indonesian phone numbers, 10-digit NISN, 18-digit NIP, student/teacher names).
- In detected entity metadata, **`raw_value` is never stored**. Metadata records only `{ "type": "...", "field": "...", "char_length": len, "detection_method": "..." }`, eliminating any privacy exposure across database records and APIs.

### C. True Immutability & Frozen SFT Snapshot (P0)
- `DatasetVersion` stores `frozen_split_payloads: {"train": [...], "val": [...], "test": [...]}`.
- Exporting a split (`export_dataset_split`) retrieves directly from the immutable frozen snapshot, guaranteeing that subsequent modifications to candidates will **never mutate** an already-released dataset version.

### D. Cryptographic Dataset Identity (P0)
- Each dataset release is indexed with:
  - `dataset_hash`: Deterministic SHA-256 (64-character hex string) computed over the canonical JSON of all frozen split payloads.
  - `manifest_hash`: SHA-256 over the split candidate ID manifest.
- Provides cryptographic reproducibility for academic thesis and empirical research citations.

### E. Assessment-Time Temporal Split & Strict Strategy Invariants (P1)
- `TEMPORAL_SPLIT` sorts candidates according to their source assessment / finalization timestamp (`history.created_at`).
- Permitted split strategies are strictly restricted to `{"QUESTION_GROUP_SPLIT", "TEMPORAL_SPLIT"}`.
- Enforces strict ratio sum invariant: $\text{train\_ratio} + \text{val\_ratio} + \text{test\_ratio} = 1.0$ with $0 < \text{train\_ratio} \le 1.0$.

### F. Structural Rubric Verification in Quality Gate (P1)
- Verifies rubric criterion definitions contain valid descriptive text and positive numerical weights before admitting candidates to the training dataset.

### G. Academic Lineage & Multi-Tenant Scoping (P1)
- `TrainingCandidate` and `DatasetVersion` explicitly store `academic_year_id`, `school_id`, and `created_by_user_id` for complete audit lineage across academic terms.
