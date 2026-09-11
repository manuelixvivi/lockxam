# Project: Equigrade x Lockxam v10 Security and Feature Audit Remediations

## Architecture
- **Backend**: FastAPI (Python 3.11) with SQLAlchemy async/sync sessions, Pydantic v2 schemas, JWT authentication, and centralized dependency injection (`app/core/dependencies.py`).
- **Frontend**: Vite + React 18 + TypeScript + Tailwind CSS with role-based routing and custom APK client guards (`LockxamAppGuard`).
- **Data Flow**:
  - Student Client (Lockxam APK / Android WebView) -> APK Header Verification (`AuthService.login`) -> Single-Device Token / JWT.
  - Student Exam Lifecycle: QR Check-in (`/api/v1/exam/checkin`) -> Schedule Screen Live Server-Synchronized Countdown -> `start_attempt` Authorization -> Kiosk Mode Activation (`enterKioskMode()`) -> CBT Engine with Virtual Keypad.
  - Teacher Review Lifecycle: Student Answers API -> Visual Confidence Gauge & Categorical Badge -> Rubric Criteria Breakdown -> Academic Rationale.
  - SuperAdmin AI Governance: AI Management Service (`/api/v1/superadmin/ai/*`) -> AI Provider Config (`eval_model_name`, `strict_transformer`, RAG tuning, AI safety webhook verification).
  - Client Hardening: Vite Production Build (`sourcemap: false`, console/debugger stripping, CSP, DevTools deterrence).

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Elimination of Student Dev-Bypass Headers | Remove `x-lockxam-dev-bypass` header and logic from `auth_service.py` | M1 | Survey Miner 1 |
| 2 | Elimination of COOKIE_SECURE Dev Bypass | Remove `COOKIE_SECURE=false` bypass from `auth_service.py` login and device binding | M1 | Survey Miner 1 |
| 3 | Elimination of Frontend Simulation Bypass | Remove `lockxam_dev_bypass` and bypass button/banner from `LockxamAppGuard.tsx` | M1 | Survey Miner 1 |
| 4 | Student Non-APK Fail-Closed Guard | Ensure unauthenticated or non-APK student requests strictly return HTTP 403 Forbidden | M1 | Survey Miner 1 |
| 5 | Forced Password Change Dependency | Enforce `must_change_password` in `get_current_user` blocking all endpoints with HTTP 403 except exempt routes | M1 | Survey Miner 1 |
| 6 | Forced Password Exempt Routes | Allow `/auth/change-password`, `/auth/logout`, and `/auth/me` when `must_change_password=True` | M1 | Survey Miner 1 |
| 7 | Test Fixtures Password Coherence | Update `conftest.py` test fixtures to set `must_change_password=False` and create R1/R2 regression tests | M1 | Survey Miner 1 |
| 8 | QR Check-in Schedule Screen Retention | Remove 800ms auto-start timeout from `performCheckin`; keep student on schedule dashboard with confirmed attendance | M2 | Survey Miner 2 |
| 9 | Live Server-Synchronized Countdown Ticker | Render active countdown on schedule card comparing server-synced time against `scheduled_start_at` | M2 | Survey Miner 2 |
| 10 | Restricted Kiosk Mode Activation | Remove mount-time kiosk call; invoke `enterKioskMode()` exclusively upon successful `start_attempt` | M2 | Survey Miner 2 |
| 11 | Backend Exam Window Start Enforcement | Remove permissive OR clause in `exam_service.py` line 288; strictly return HTTP 400 before `start_at` | M2 | Survey Miner 2 |
| 12 | CBT Essay & Short-Answer Soft-Keyboard Suppression | Add `inputMode="none"` and `readOnly={true}` to `<textarea>` in `StudentCbtEngineView.tsx` | M2 | Survey Miner 2 |
| 13 | Lockxam Virtual Keypad Cursor & Space Fix | Ensure virtual keypad updates cursor position cleanly without summoning IME; fix SPASI cursor placement | M2 | Survey Miner 2 |
| 14 | SuperAdmin AI Config Schema Extension | Add `eval_model_name`, `strict_transformer`, RAG parameters (`embedding_model`, `rag_top_k`, etc.) to backend schemas | M3 | Survey Explorer 3 |
| 15 | SuperAdmin AI Safety Status Indicators | Expose HMAC callback health, webhook secret status, and replay protection in overview API | M3 | Survey Explorer 3 |
| 16 | SuperAdmin AI System Control Center UI | Update `SuperAdminAiSystemView.tsx` with evaluation model input, strict transformer toggle, RAG sliders, and safety badges | M3 | Survey Explorer 3 |
| 17 | AI Grading Schema Root-Level Confidence | Add root-level `confidence` (float), `confidence_level` (string), `review_required` (boolean) to grading responses | M4 | Survey Explorer 3 |
| 18 | Grading Service Confidence Derivation | Compute `confidence = quality_indicator`, categorize (HIGH >= 0.90, MEDIUM 0.75-0.89, LOW < 0.75), set `review_required` | M4 | Survey Explorer 3 |
| 19 | Teacher Student Answers Confidence Propagation | Return confidence fields, rubric breakdown, and academic rationale in teacher student answers API | M4 | Survey Explorer 3 |
| 20 | Teacher Grading Detail UI Elevation | Render visual confidence gauge, categorical badge, rubric criteria breakdown, and academic rationale | M4 | Survey Explorer 3 |
| 21 | Vite Production Minification & Sourcemap Stripping | Configure `sourcemap: false` and `esbuild: { drop: ['console', 'debugger'] }` in `vite.config.ts` | M5 | Survey Explorer 3 |
| 22 | Content Security Policy & DevTools Deterrence | Add CSP meta tag in `index.html`, CSP header in middleware, and client-side DevTools deterrence signal | M5 | Survey Explorer 3 |
| 23 | Baseline Pytest Failures Resolution | Resolve `cryptography` dependency in `.venv` and multi-tenant isolation in `test_school_api_rbac` (331 passing tests) | M5 | Survey Explorer 3 |
| 24 | E2E Test Suite Infrastructure & Test Cases | Design and implement comprehensive opaque-box test suite across Tiers 1-4 | E2E Track | ORIGINAL_REQUEST |
| 25 | Final E2E Test Pass & Adversarial Hardening | Pass 100% of E2E test suite + Tier 5 white-box challenger hardening and forensic audit | M6 | ORIGINAL_REQUEST |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| E2E | E2E Testing Track | Independent opaque-box test suite (Tiers 1-4), harness, and `TEST_READY.md` | None | PLANNED |
| M1 | Auth & Security Bypass Remediation (R1, R2) | Remove bypass headers/flags, enforce `must_change_password` with HTTP 403 on protected routes, update test fixtures & write regression tests | None | PLANNED |
| M2 | CBT Exam State Machine & Keyboard Suppression (R3) | Retain student on schedule after QR check-in, live countdown, restrict `enterKioskMode()`, enforce `start_at` window, suppress Android soft-keyboard | None | PLANNED |
| M3 | SuperAdmin AI Control Center Expansion (R4) | Backend schemas and service for `eval_model_name`, strict transformer, RAG params, AI safety status, and frontend UI controls/badges | None | PLANNED |
| M4 | AI Confidence Elevation & Teacher Review (R5) | Root-level confidence fields in grading schemas, grading service calculation, teacher API propagation, and teacher review UI elevation | M3 (for AI schema alignment) | PLANNED |
| M5 | Layer 2 Client Hardening & Regression Baseline (R6) | Vite config hardening, CSP, DevTools deterrence, `cryptography` fix, `test_school_api_rbac` alignment, 331+ tests passing baseline | None | PLANNED |
| M6 | Final Verification & Adversarial Hardening | Pass 100% of E2E tests (Tiers 1-4), Tier 5 white-box challenger hardening, forensic integrity audit | E2E, M1, M2, M3, M4, M5 | PLANNED |

## Interface Contracts

### 1. Auth & Forced Password Change (M1)
- `get_current_user` in `app/core/dependencies.py`:
  ```python
  # If account.must_change_password is True:
  # Allowed paths: path.endswith("/auth/change-password"), path.endswith("/auth/logout"), path.endswith("/auth/me")
  # Any other path -> raise PermissionException("Harap ubah kata sandi Anda sebelum melanjutkan.", status_code=403)
  ```
- `AuthService.login` in `app/services/security/auth_service.py`:
  ```python
  # If role_str in ["STUDENT", UserRole.STUDENT] and not is_apk:
  # Strictly raise PermissionException("Akun siswa hanya dapat diakses melalui aplikasi resmi Lockxam APK...", status_code=403)
  ```

### 2. CBT Exam Lifecycle & Window (M2)
- `exam_service.py:start_attempt`:
  ```python
  # if start_at and now_utc < start_at:
  #     raise BusinessException("Waktu pelaksanaan ujian belum tiba.", status_code=400)
  ```
- `StudentSchedulesView.tsx`:
  - `performCheckin`: Sets `checkinSuccess=true`, refreshes schedules, does NOT call `handleStartExam`.
  - Card displays `HADIR ✓` and live countdown timer.
  - "Mulai Ujian" button enabled ONLY when `serverSyncedNow >= scheduled_start_at`.
- `StudentCbtEngineView.tsx`:
  - Mount `useEffect` does NOT call `enterKioskMode()`.
  - Inside `initAttempt()`, after successful `studentExamApi.startAttempt(...)`, invoke `(window as any).LockxamBridge?.enterKioskMode?.()`.
  - Essay `<textarea inputMode="none" readOnly={true} ... />`.

### 3. AI Governance & Schemas (M3, M4)
- `AiProviderConfigUpdateRequest` in `app/schemas/ai/ai_management.py`:
  ```python
  eval_model_name: Optional[str] = None
  strict_transformer: Optional[bool] = None
  embedding_model: Optional[str] = None
  rag_top_k: Optional[int] = None
  rag_similarity_threshold: Optional[float] = None
  max_rag_tokens: Optional[int] = None
  ```
- `AiSystemOverviewResponse` in `app/schemas/ai/ai_management.py`:
  ```python
  ai_safety_status: Dict[str, Any] = Field(default_factory=dict)
  # keys: hmac_callback_configured (bool), webhook_secret_set (bool), replay_protection_active (bool)
  ```
- `GradingEvaluateResponse` in `app/services/ai/grading/grading_schema.py`:
  ```python
  confidence: float = Field(..., ge=0.0, le=1.0)
  confidence_level: str = Field(..., pattern="^(HIGH|MEDIUM|LOW)$")
  review_required: bool = Field(...)
  ```
- Categorical Confidence thresholds:
  - `HIGH`: confidence >= 0.90 -> Auto Accept (`review_required = False`)
  - `MEDIUM`: 0.75 <= confidence < 0.90 -> Requires Review (`review_required = True`)
  - `LOW`: confidence < 0.75 -> Manual Review Required (`review_required = True`)

## Code Layout
- Backend:
  - `app/api/`: FastAPI route handlers (`auth.py`, `exam.py`, `teacher.py`, `superadmin_ai.py`, `school.py`)
  - `app/core/`: Security and dependency injection (`dependencies.py`, `rbac.py`, `security/`)
  - `app/services/`: Business logic services (`security/auth_service.py`, `exam/exam_service.py`, `ai/`)
  - `app/schemas/`: Pydantic schemas (`ai/ai_management.py`, `ai/grading/`)
  - `app/middleware/`: HTTP middlewares (`request_context.py`)
  - `tests/`: Pytest suite (`test_regression_r1.py`, `test_regression_r2.py`, `test_exam_security_boundaries.py`, etc.)
- Frontend:
  - `frontend/src/views/student/`: Student views (`StudentSchedulesView.tsx`, `StudentCbtEngineView.tsx`)
  - `frontend/src/views/teacher/`: Teacher views (`TeacherGradingView.tsx`)
  - `frontend/src/views/superadmin/`: Superadmin views (`SuperAdminAiSystemView.tsx`)
  - `frontend/src/components/ui/`: UI components (`LockxamAppGuard.tsx`)
  - `frontend/src/api/`: API clients (`studentExam.ts`, `teacherDashboard.ts`, `superadminAi.ts`)
  - `frontend/vite.config.ts`, `frontend/index.html`
