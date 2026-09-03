# 🔬 EquiGrade Milestone A9.1: Tokenizer & SFT Formatter Engine Report

> **Milestone:** A9.1 — Dataset Loader, SFT Conversational Formatter, Real Tokenizer Abstraction & Pre-Flight Hard Gate
> **Status:** 🟢 A9.1 FINAL VERIFIED — PRE-TRAINING PIPELINE READY
> **A9.1 Test Suite:** 27 / 27 tests passed (`tests/test_ai_sft_pipeline.py`)
> **Full Regression Suite:** 331 / 331 tests passed in 70.38s (100% Pass Rate)

---

## 1. Executive Summary & Hardened Scientific Pipeline

Milestone A9.1 establishes the data and tokenization contract required for Supervised Fine-Tuning (SFT / LoRA / QLoRA) on top of the frozen A0–A8 baseline.

### 🛡️ P0 & P1 Key Fixes Implemented:
1. **100% A8 $\leftrightarrow$ A9 Hash Byte-for-Byte Canonicalization**:
   - `DatasetLoader` uses identical `json.dumps(payloads, sort_keys=True)` matching A8 `DatasetBuilderService` byte-for-byte across all Unicode/multilingual characters.
2. **Explicit Tokenizer Execution Mode (`CPU_TEST` vs `REAL_TRAINING`)**:
   - In `REAL_TRAINING` mode, `TokenizerService` strictly requires real HuggingFace `AutoTokenizer` and immediately raises `RuntimeError` if unavailable (zero silent fallback).
   - In `CPU_TEST` mode, a deterministic SHA-256 token pseudo-encoder is provided for fast offline CPU unit testing.
3. **Native Model Chat Template Integration**:
   - When real HuggingFace tokenizers are loaded, native Jinja chat templates (`tokenizer.apply_chat_template`) are applied automatically.
4. **Pedagogical Assistant Target Truncation Protection**:
   - With `truncation_strategy="prompt_first"`, prompt tokens are truncated from the left while preserving the full assistant ground-truth target.
   - If sequence length exceeds maximum context window and cuts into the assistant target, `target_is_truncated` is marked `True`, triggering a hard validation failure.
5. **Split Strategy Aware Semantic Leakage Gate**:
   - `QUESTION_GROUP_SPLIT`: Enforces strict zero question group overlap across partitions.
   - `TEMPORAL_SPLIT`: Preserves question overlap across time partitions for temporal generalization benchmarks while strictly enforcing candidate ID disjunction.
6. **Hard Pre-Flight Gate (`TrainingPreflightError`)**:
   - `DatasetValidator.assert_training_ready(db, version_tag)` acts as an uncompromising gate before any downstream training worker executes.

```text
========================================================================================
                          EQUIGRADE MILESTONE A9.1 ARCHITECTURE
========================================================================================

                         DatasetVersion (A8 Frozen Release)
                                         │
                                         ▼
                                   DatasetLoader
                          [SHA-256 Hash Byte-for-Byte Check]
                          [JSONL Export & Stream Ingestion]
                                         │
                                         ▼
                                   SftFormatter
                        [Pure Ground Truth Formatting]
                        [Structured Markdown Prompt Blocks]
                        [Strict JSON Assistant Target]
                        [Zero RAG Context Contamination]
                                         │
                                         ▼
                                  TokenizerService
                        [REAL_TRAINING: Real HF AutoTokenizer]
                        [CPU_TEST: Deterministic SHA-256 Mock]
                        [Prompt Label Masking (-100 Loss)]
                        [Prompt-First Target Loss Protection]
                                         │
                                         ▼
                                  DatasetValidator
                       [Pre-Flight Scientific Quality Gate]
                       [Cryptographic Integrity Assurance]
                       [Question Group Disjoint (Group Split)]
                       [Temporal Generalization (Time Split)]
                       [Truncation Policy Enforcement]
                                         │
                        ┌────────────────┴────────────────┐
                        ▼                                 ▼
                     is_valid                          is_invalid
                        │                                 │
                        ▼                                 ▼
               A9.1 Pipeline Ready              TrainingPreflightError
             (Proceed to A9.2 LoRA)                  (Hard Stop)
========================================================================================
```

---

## 2. Dedicated Test Suite (27 Tests in `tests/test_ai_sft_pipeline.py`)

| Test Function | Verification Scope | Status |
| :--- | :--- | :---: |
| `test_dataset_loader_loads_and_verifies_hash_successfully` | Cryptographic SHA-256 pre-flight verification | ✅ Passed |
| `test_dataset_loader_rejects_corrupted_dataset_hash` | Tamper detection & rejection on corrupted hash | ✅ Passed |
| `test_dataset_loader_export_and_load_jsonl` | File export and stream ingestion via JSONL | ✅ Passed |
| `test_sft_formatter_constructs_structured_messages` | System, user, and assistant JSON message generation | ✅ Passed |
| `test_sft_formatter_zero_rag_leakage` | Verifies zero retrieval XML chunks in SFT data | ✅ Passed |
| `test_sft_formatter_rubric_parsing` | Multi-format rubric criteria parsing and fallback | ✅ Passed |
| `test_sft_formatter_batch_and_dataset` | Batch transformation across dataset splits | ✅ Passed |
| `test_chatml_template_rendering` | ChatML special token rendering | ✅ Passed |
| `test_llama3_template_rendering` | Llama-3 special token rendering | ✅ Passed |
| `test_tokenization_label_masking` | Prompt label masking with `-100` for loss calculation | ✅ Passed |
| `test_tokenization_truncation_right` | Right-side truncation at `max_seq_length` | ✅ Passed |
| `test_tokenization_truncation_left` | Left-side truncation at `max_seq_length` | ✅ Passed |
| `test_tokenization_stats_distribution` | Token length statistical distribution (P95, avg) | ✅ Passed |
| `test_dataset_validator_success` | Full pre-flight scientific validation success | ✅ Passed |
| `test_dataset_validator_detects_data_leakage` | Candidate ID leakage detection across splits | ✅ Passed |
| `test_dataset_validator_detects_out_of_bounds_scores` | Out-of-bounds score detection ($score > max\_score$) | ✅ Passed |
| `test_sft_formatter_score_normalization` | Percentage and normalization precision checks | ✅ Passed |
| `test_tokenization_config_defaults_and_options` | Configuration defaults and custom parameter override | ✅ Passed |
| `test_sha256_mock_tokenizer_deterministic_across_invocations` | Stable, cross-process deterministic SHA-256 token hashing | ✅ Passed |
| `test_dataset_validator_detects_semantic_group_leakage` | Semantic question-group leakage detection for group splits | ✅ Passed |
| `test_dataset_validator_fails_on_target_truncation` | Hard failure when assistant target tokens are truncated | ✅ Passed |
| `test_dataset_validator_fails_on_truncation_rate_exceeded` | Hard failure when truncation rate exceeds policy threshold | ✅ Passed |
| `test_dataset_validator_assert_training_ready_raises_preflight_error` | Hard stop pre-flight exception on invalid datasets | ✅ Passed |
| `test_dataset_loader_exact_unicode_hash_compatibility_with_a8` | Exact Unicode byte-for-byte hash compatibility with A8 | ✅ Passed |
| `test_strict_real_training_mode_raises_when_hf_unavailable` | Strict REAL_TRAINING mode error enforcement | ✅ Passed |
| `test_prompt_first_truncation_preserves_assistant_target` | Prompt-first truncation preserving assistant ground-truth targets | ✅ Passed |
| `test_temporal_split_allows_group_overlap_for_generalization` | Temporal split semantic validation for generalization benchmarks | ✅ Passed |
