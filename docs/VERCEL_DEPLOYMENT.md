# 🌐 EquiGrade x Lockxam: Vercel Deployment & Production Architecture Guide

> **Target Platform:** Vercel (Edge/Serverless Platform)  
> **Deployment Model:** Hybrid Micro-Architecture (Lightweight Frontend + Serverless API on Vercel; Heavy AI Inference/Training & Persistent Jobs on External Workers)  
> **Architecture Status:** 🟢 Verified & Serverless-Safe  
> **Verified Regression Suite:** 406 Passed, 4 Skipped across 41 Test Files (100% Pass Rate)

---

## 1. High-Level Architecture Topology

EquiGrade x Lockxam employs a clean separation of concerns to maximize responsiveness, scalability, and cost efficiency on Vercel:

```text
                               ┌───────────────────────────────────────────────┐
                               │             VERCEL PLATFORM                   │
                               │                                               │
       [ Web Browser / User ] ─┼─► React 19 Frontend SPA (Vite, TailwindCSS)   │
                               │   - Edge CDN Global Distribution              │
                               │   - Optimized Vendor Chunking                 │
                               │                                               │
                               │   FastAPI Serverless API (/api/v1/...)        │
                               │   - Short-lived HTTP Request/Response         │
                               │   - Stateless Auth & RBAC Verification        │
                               │   - Transaction-Scoped DB Queries             │
                               │   - Zero In-Memory Stateful Singletons        │
                               └───────┬──────────────┬──────────────┬─────────┘
                                       │              │              │
                     ┌─────────────────┘              │              └────────────────┐
                     ▼                                ▼                               ▼
       ┌──────────────────────────┐     ┌──────────────────────────┐    ┌──────────────────────────┐
       │   EXTERNAL POSTGRESQL    │     │   EXTERNAL LLM / AI API  │    │  OBJECT STORAGE (S3/R2)  │
       │   (Neon / Supabase / RDS)│     │   (Groq / OpenAI / Micro)│    │  (Persistent Artifacts)  │
       │   - PgBouncer Pooler     │     │   - HTTPS LLM Inference  │    │  - Model Weights & LoRA  │
       │   - NullPool / Lean Conn │     │   - Fast Chat Completion │    │  - Exam Attachments      │
       └─────────────▲────────────┘     └──────────────────────────┘    └─────────────▲────────────┘
                     │                                                                │
                     │                 ┌──────────────────────────┐                   │
                     └─────────────────┤  EXTERNAL WORKER (GPU)   ├───────────────────┘
                                       │  - PyTorch Gradient Loop │
                                       │  - LoRA/QLoRA Training   │
                                       │  - Dense E5-Large Embed  │
                                       │  - Background Batch Job  │
                                       └──────────────────────────┘
```

---

## 2. Component Responsibility Matrix

| Component | Execution Host | Rationale & Constraints |
| :--- | :--- | :--- |
| **React 19 Frontend** | **Vercel Static CDN** | Ultra-fast client-side delivery, code-split vendor chunks (`vendor-react`, `vendor-katex`, `vendor-xlsx`, `vendor-jszip`). |
| **HTTP API Layer** | **Vercel Serverless (Python)** | Handles auth, exam delivery, student proctoring, grading requests, and CRUD via lightweight FastAPI lambda functions. |
| **Database Access** | **External PostgreSQL** | Managed Postgres with connection pooling (e.g. Neon, Supabase, AWS RDS Aurora Serverless). |
| **LLM Inference** | **External HTTPS (Groq/Gemini)** | LLM queries run via stateless HTTPS API calls through `LlmClient` with exponential backoff. |
| **Dense Vector Embeddings** | **External Worker / Microservice** | Generating 1024-D `multilingual-e5-large` embeddings requires neural models that run on dedicated GPU/CPU microservices. |
| **LoRA / QLoRA Training** | **External Training Runner** | PyTorch gradient optimization and checkpoint pruning run strictly on dedicated GPU compute instances. |
| **Persistent File Storage** | **S3-Compatible Object Store** | Model checkpoints, datasets, and question media persist in S3/CloudFlare R2, avoiding ephemeral lambda disk storage. |

---

## 3. Serverless Optimization & Safety Invariants

1. **Cold-Start Optimization**:
   - Heavy machine learning libraries (`torch`, `transformers`, `peft`, `sentence-transformers`) are **not** loaded at API module startup. They are isolated behind lazy imports within dedicated training paths.
   - Database table schema creation (`Base.metadata.create_all`) and master seeding are bypassed during serverless cold starts (`AUTO_CREATE_TABLES=false` when `VERCEL=1`).
2. **Database Connection Safety**:
   - `app/core/database.py` dynamically adjusts connection pooling for serverless execution:
     - Automatically enables `NullPool` when `DB_USE_NULLPOOL=true` (recommended for PgBouncer / Neon connection pooling).
     - Restricts connection pool size (`pool_size=5`, `max_overflow=5`, `pool_recycle=300`) to prevent connection exhaustion.
3. **Stateless Authentication**:
   - Access tokens are stored strictly in client memory. Refresh tokens and CSRF protections use HttpOnly Secure cookies.
4. **CORS & Domain Routing**:
   - `main.py` dynamically allows configured production domains via `ALLOWED_ORIGINS` and regex-matches Vercel preview environments (`https://.*\.vercel\.app`).

---

## 4. Environment Variables Configuration

Set the following environment variables in your **Vercel Project Settings $\rightarrow$ Environment Variables**:

### Required Backend Environment Variables
```ini
# Database (Managed PostgreSQL / Neon / Supabase)
DATABASE_URL=postgresql://user:password@ep-sample-pooler.us-east-2.aws.neon.tech/equigrade?sslmode=require
DB_USE_NULLPOOL=true

# Security & Authentication
SECRET_KEY=your_super_secret_jwt_encryption_key_min_32_chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# LLM & AI Engine (External Groq / AI Service)
GROQ_API_KEY=gsk_your_groq_production_api_key
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_FALLBACK_MODEL=llama-3.1-8b-instant

# AI Governance & RAG Flags
RAG_ENABLED=true
STRICT_TRANSFORMER=false
AUTO_CREATE_TABLES=false

# CORS & Domain Configuration
ALLOWED_ORIGINS=https://equigrade.yourdomain.com,https://equigrade.vercel.app
CORS_ORIGIN_REGEX=^https:\/\/.*\.vercel\.app$
```

### Required Frontend Environment Variables (Build Time)
```ini
# API Base URL (Leave empty if deploying Frontend + Backend under same Vercel project)
VITE_API_BASE_URL=
```

---

## 5. Deployment Step-by-Step

### Option A: Monorepo Single-Project Deployment (Recommended)
The repository contains a unified [`vercel.json`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/vercel.json) that automatically builds the React frontend with `@vercel/static-build` and mounts the FastAPI backend with `@vercel/python` on `/api/(.*)`:

1. Push your repository to GitHub:
   ```bash
   git push origin master
   ```
2. Import the repository in [Vercel Dashboard](https://vercel.com/new).
3. Select **Other** as the Framework Preset.
4. Add all environment variables listed in Section 4.
5. Click **Deploy**.

### Option B: Vercel CLI Deployment
```bash
# 1. Install Vercel CLI
npm install -g vercel

# 2. Link & Deploy to Production
vercel --prod
```

---

## 6. Running Database Migrations

Because serverless lambdas should not execute DDL migrations on cold starts, run Alembic migrations once from your local environment or CI/CD pipeline before deploying:

```bash
# Point to your production database
export DATABASE_URL="postgresql://user:pass@host/db?sslmode=require"

# Upgrade to the latest schema migration (Head: f7a8b9c0d1e2)
alembic upgrade head
```

---

## 7. Local Development Workflow

Run frontend and backend simultaneously for local development:

```bash
# Terminal 1: Backend API (Port 1409)
uvicorn main:app --host 0.0.0.0 --port 1409 --reload

# Terminal 2: Frontend Vite Dev Server (Port 5173)
cd frontend
npm run dev
```
