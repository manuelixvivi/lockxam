# 🎓 EquiGrade x Lockxam — AI-Powered Computer-Based Assessment Platform

EquiGrade is a modern, enterprise-grade Computer-Based Testing (CBT) and Automated Essay Evaluation platform. It features **Teacher-in-the-Loop Retrieval-Augmented Generation (RAG)**, dense multilingual Transformer embeddings, and exact relational vector similarity search.

---

## 🏛️ System Architecture

```text
                                NEW STUDENT ESSAY
                                       │
                                       ▼
                       ┌───────────────────────────────┐
                       │  Authoritative Official Data  │
                       │  • Question Content           │
                       │  • Official Answer Key        │
                       │  • Official Grading Rubrics   │
                       └───────────────┬───────────────┘
                                       │
                                       ▼
                        Transformer Dense Embedding
                     (intfloat/multilingual-e5-large)
                                       │
                                       ▼
                             1024-Dimensional Vector
                                       │
                                       ▼
                         Exact Relational Vector Search
                     (PostgreSQL Pre-filtered Cosine Sim)
                                       │
                                       ▼
                           Top-K Historical Cases
                          (Teacher Finalized Only)
                                       │
                                       ▼
                          RAG Context Assembly Layer
                     • Atomic Token Budget (≤1500 tokens)
                     • Prompt Injection Boundary Isolator
                                       │
                                       ▼
                         Augmented LLM Grading Pipeline
                     • RAG_ENABLED Feature Flag (default: false)
                     • Fail-Safe Fallback to Baseline LLM
                                       │
                                       ▼
                            AI Evaluation Output
                           (Status: AI_DRAFT only)
                                       │
                                       ▼
                         Teacher Verification & Review
                                       │
                                       ▼
                                FINALIZED Status
                                       │
                                       ▼
                              Assessment History
                                (Append-Only v1)
                                       │
                                       ▼
                           Continuous Knowledge Base
```

---

## 🔬 AI & Transformer Specifications (Milestones A0–A7)

| Component | Technical Specification |
| :--- | :--- |
| **Embedding Transformer** | `intfloat/multilingual-e5-large` |
| **Vector Dimension** | $1024\text{ dimensions}$ (L2-normalized) |
| **Prefix Protocol** | `passage:` for knowledge documents, `query:` for search queries |
| **Vector Architecture** | Hybrid Relational Pre-Filtered Exact Vector Search in PostgreSQL |
| **Similarity Metric** | Exact Dot-Product Cosine Similarity ($1024\text{D}$) |
| **Multi-Tenant Isolation** | Strict SQL Pre-filtering by `school_id`, `subject_id`, `academic_year_id`, `class_level` |
| **Prompt Injection Defense** | Encapsulated inside `<REFERENCE_CASES><CASE>...</CASE></REFERENCE_CASES>` as passive data |
| **Token Budget Policy** | `MAX_RAG_CONTEXT_TOKENS = 1500` with Atomic Case Preservation |
| **RAG Feature Flag** | `RAG_ENABLED=false` (default) with fail-safe fallback |
| **Empirical Results (A7)**| $\text{MAE: } 8.45 \to 4.15$ ($\downarrow 50.9\%$), $\text{RMSE: } 10.82 \to 5.63$ ($\downarrow 48.0\%$), $r = 0.948$ |

---

## 🚀 Quick Start Guide

### 1. Backend Setup

```bash
# 1. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Setup environment configuration
cp .env.example .env

# 4. Run database migrations
alembic upgrade head

# 5. Start Backend Server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. AI Microservice Setup (`backend_ai`)

```bash
cd backend_ai
cp .env.example .env
pip install -r requirements.txt
python sandbox_app.py
```

### 3. Frontend Setup (`frontend`)

```bash
cd frontend
npm install
npm run dev
```

---

## 🧪 Running Automated Test Suite

EquiGrade maintains an automated test suite with 100% pass rate (343 passed, 2 skipped / 345 total):

```bash
# Run complete test suite (345 tests)
pytest -v

# Run specific AI milestones & modular services
pytest tests/test_assessment_history.py -v               # Milestone A1 (12 tests)
pytest tests/test_assessment_document_construction.py -v # Milestone A2 (12 tests)
pytest tests/test_embedding_service.py -v                # Milestone A3 (18 tests)
pytest tests/test_vector_search_service.py -v            # Milestone A5 (18 tests)
pytest tests/test_rag_context_service.py -v              # Milestone A6.1 (20 tests)
pytest tests/test_rag_augmented_grading.py -v            # Milestone A6.2 (20 tests)
pytest tests/test_ai_batch_grading.py -v                 # Batch Grading & State Machine (7 tests)
pytest tests/test_ai_rubric_service.py -v                # Rubric Generation (4 tests)
pytest tests/test_ai_validation_service.py -v            # Rubric & Key Validation (5 tests)
pytest tests/test_ai_grading_modular.py -v               # Modular Single Grading (7 tests)
pytest tests/test_benchmark_evaluation.py -v             # Milestone A7 (10 tests)
pytest tests/test_ai_training_governance.py -v           # Milestone A8: Training Governance (11 tests)
pytest tests/test_ai_sft_pipeline.py -v                  # Milestone A9.1: Tokenizer & SFT Pipeline (27 tests)
pytest tests/test_ai_lora_training.py -v                # Milestone A9.2: LoRA / QLoRA Training Engine (14 tests)
```

---

## 📚 Milestone Documentation Index

Detailed architectural and empirical reports are located in the `documentation/` folder:
- `documentation/assessment_history_schema_audit.md` (Milestone A0)
- `documentation/assessment_history_schema_amendment.md` (Milestone A0.1)
- `documentation/assessment_history_implementation_report.md` (Milestone A1)
- `documentation/assessment_text_construction_report.md` (Milestone A2)
- `documentation/transformer_embedding_implementation_report.md` (Milestone A3)
- `documentation/vector_store_architecture_audit.md` (Milestone A4)
- `documentation/vector_search_implementation_report.md` (Milestone A5)
- `documentation/rag_context_assembly_report.md` (Milestone A6.1)
- `documentation/rag_augmented_grading_implementation_report.md` (Milestone A6.2)
- `documentation/scientific_evaluation_a7_report.md` (Milestone A7)
- `documentation/training_data_governance_a8_report.md` (Milestone A8)

---

## 📄 License

Academic / Educational Evaluation License — EquiGrade Core Team.
