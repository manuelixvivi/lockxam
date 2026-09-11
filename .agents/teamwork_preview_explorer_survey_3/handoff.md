# Handoff Report: Survey of R4, R5, and R6 (AI Governance, Teacher Experience, Client Hardening & Build/Test Baseline)

- **Date**: 2026-09-11
- **Agent**: teamwork_preview_explorer_survey_3
- **Scope**: Requirements R4, R5, and R6 across backend and frontend codebases
- **Authoritative Request**: `C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\ORIGINAL_REQUEST.md`

---

## 1. Observation

### R4: SuperAdmin AI Control Center Expansion

1. **`SuperAdminAiSystemView.tsx` Form & View Coverage**:
   - File: `frontend/src/views/superadmin/SuperAdminAiSystemView.tsx` (Lines 68–76, 471–680):
     - Form state variables are limited to:
       ```typescript
       const [formProvider, setFormProvider] = useState<string>("Groq");
       const [formModel, setFormModel] = useState<string>("openai/gpt-oss-120b");
       const [formFallbackModel, setFormFallbackModel] = useState<string>("openai/gpt-oss-20b");
       const [formApiKey, setFormApiKey] = useState<string>("");
       const [showApiKey, setShowApiKey] = useState<boolean>(false);
       const [formTemperature, setFormTemperature] = useState<number>(0.2);
       const [formMaxTokens, setFormMaxTokens] = useState<number>(4096);
       const [formRagEnabled, setFormRagEnabled] = useState<boolean>(false);
       ```
     - Missing form controls: There are NO controls, inputs, or selectors for `eval_model_name`, `strict_transformer`, or any RAG hyperparameters (`embedding_model`, `top_k`, `similarity_threshold`, `max_rag_tokens`).
     - Missing safety indicators: The Overview and Health tabs do NOT display HMAC callback health, webhook secret configuration verification status, or replay protection status.

2. **Frontend API Types (`frontend/src/api/superadminAi.ts`)**:
   - `AiProviderConfig` interface (Lines 3–19) has:
     - `eval_model_name: string`
     - `strict_transformer: boolean`
   - `AiProviderConfigUpdatePayload` interface (Lines 21–29) has:
     ```typescript
     export interface AiProviderConfigUpdatePayload {
       provider: string;
       api_key?: string;
       model_name: string;
       fallback_model?: string;
       temperature: number;
       max_output_tokens: number;
       rag_enabled?: boolean;
     }
     ```
     Neither `eval_model_name` nor `strict_transformer` nor RAG tuning parameters are present in `AiProviderConfigUpdatePayload`.

3. **Backend Schemas & API (`app/schemas/ai/ai_management.py` & `app/api/superadmin_ai.py`)**:
   - `AiProviderConfigResponse` (Lines 7–25) defines `eval_model_name: str = "openai/gpt-oss-120b"` and `strict_transformer: bool = False`.
   - `AiProviderConfigUpdateRequest` (Lines 27–35) only defines:
     `provider, api_key, model_name, fallback_model, temperature, max_output_tokens, rag_enabled`.
     It is missing `eval_model_name`, `strict_transformer`, and RAG parameters.
   - `AiManagementService.update_config` (`app/services/ai/ai_management_service.py:209`) forcibly overrides `eval_model_name` with `payload.model_name`:
     ```python
     "model_name": payload.model_name,
     "eval_model_name": payload.model_name,
     ```
   - `AiSystemOverviewResponse` (`app/schemas/ai/ai_management.py:104–114`) omits AI safety status (webhook secret presence, HMAC health, replay protection metrics).

4. **Underlying AI & RAG Backend Engine Parameters**:
   - `AiConfig` (`app/services/ai/shared/config.py`):
     - `EVAL_MODEL_NAME`: Line 16 (`os.environ.get("GROQ_MODEL", os.environ.get("EVAL_MODEL_NAME", "openai/gpt-oss-120b"))`)
     - `STRICT_TRANSFORMER`: Lines 28–32 (`os.environ.get("STRICT_TRANSFORMER", "false").lower() in ("true", "1", "yes")`)
     - `MAX_RAG_CONTEXT_TOKENS`: Line 25 (default 1500)
   - `EmbeddingService` (`app/services/ai/embedding_service.py`):
     - Model: `intfloat/multilingual-e5-large` (1024-dim, Line 36)
     - `strict_transformer`: Line 41
     - Batch size: 8 (Line 38), Device: cpu (Line 37)
   - `RagContextService` (`app/services/ai/rag_context_service.py`):
     - `DEFAULT_MAX_RAG_TOKENS = 1500` (Line 61)
     - `DEFAULT_TOP_K = 3` (Line 62)
     - `DEFAULT_SIMILARITY_THRESHOLD = 0.70` (Line 63)
   - AI Webhook & HMAC Callback (`app/api/exam.py:858–883`):
     - Webhook `POST /api/v1/exam/ai/callback` verifies `X-AI-Signature` header via HMAC-SHA256 with `AI_WEBHOOK_SECRET`.
     - Fails closed: 503 if secret is not set, 403 if signature is invalid or missing.
   - Replay Protection (`app/services/exam/exam_service.py:777–786`):
     - `AiGradingEventLog` records `event_id` with atomic idempotency check via `create_if_not_exists` (duplicate events return early with safe HTTP 200).

---

### R5: AI Confidence Level Elevation & Teacher Review Experience

1. **AI Grading Evaluation Response Schemas**:
   - File: `app/services/ai/grading/grading_schema.py` (Lines 64–94):
     ```python
     class GradingEvaluateResponse(BaseModel):
         status: str = Field("success", description="Grading outcome status")
         score: float = Field(..., description="Actual scaled score based on max_score")
         final_score: float = Field(..., description="Percentage score (0-100)")
         max_score: float = Field(10.0, description="Max possible score for question")
         feedback: str = Field(..., description="Constructive pedagogical feedback")
         decision: Dict[str, Any] = Field(default_factory=dict)
         metrics: Dict[str, Any] = Field(default_factory=dict)
         rubric_scores: List[Dict[str, Any]] = Field(default_factory=list)
         ...
     ```
     **Missing Root-Level Fields**:
     - `confidence: float`
     - `confidence_level: str` (HIGH / MEDIUM / LOW)
     - `review_required: bool`
   - File: `app/services/ai/grading/batch_grading_schema.py` (Lines 42–55):
     `BatchStudentGradingResult` contains `quality_indicator: float = Field(1.0)`, but lacks root-level `confidence`, `confidence_level`, and `review_required`.
   - File: `app/services/ai/grading/grading_service.py` (Lines 284–301):
     Calculates `quality_indicator` (0.0 to 1.0) and stores it within `decision["quality_indicator"]`, but does not output root-level confidence attributes or categorical levels.

2. **Teacher Grading Interface (`frontend/src/views/teacher/TeacherGradingView.tsx`)**:
   - Navigation Level 3 (Lines 1296–1425) renders each question for a student attempt:
     - Displays question index, type badge (`PG`, `IS`, `ES`), score badge (`Skor: earned / max`), question content LaTeX, and student answer.
     - Inline score editing input (`full-score-{qId}`) and teacher feedback input (`full-fb-{qId}`).
   - **Completely Missing in UI**:
     - Visual confidence gauge: No visual indicator (gauge, bar, progress circle) for AI confidence percentage.
     - Categorical badges: No categorical classification badge (HIGH: 90–100% / Auto Accept, MEDIUM: 75–89% / Requires Review, LOW: 0–74% / Manual Review Required).
     - Rubric criteria breakdowns: Individual criteria items (`ku_id`, description, weight, achieved points) are NOT rendered in the essay review section.
     - Generated academic rationales: No display of explainability reasoning or step-by-step justification for awarded points.
3. **Teacher Grading API Endpoints**:
   - `GET /api/v1/teacher/exam-history/{schedule_id}/student-answers` (`app/api/teacher.py:1684–1699`):
     Returns `question_id`, `question_type`, `question_content`, `selected_option`, `text_answer`, `score_earned`, `max_score`, `is_correct`, `evaluation_id`, `ai_feedback`.
     Does NOT include `confidence`, `confidence_level`, `review_required`, `rubric_scores`, or `academic_rationale`.
   - `GET /api/v1/teacher/grading/evaluations` (`app/api/teacher.py:1940–1961` & `frontend/src/api/teacherDashboard.ts:57–74`):
     `EssayGradingEvaluation` only carries `ai_score`, `ai_feedback`, `grading_status`, `final_score`.

---

### R6: Layer 2 Client Hardening & Build / Test Suite Baseline

1. **Frontend Build Configuration (`frontend/vite.config.ts`)**:
   - File: `frontend/vite.config.ts` (Lines 50–75):
     ```typescript
     build: {
       chunkSizeWarningLimit: 1000,
       rollupOptions: {
         output: {
           manualChunks(id: string) { ... }
         },
       },
     },
     ```
   - Observations:
     - `sourcemap: false` is not explicitly set in `build`.
     - `esbuild: { drop: ['console', 'debugger'] }` is absent in production configuration.
     - No DevTools detection/deterrence scripts or modules exist.
     - No Content Security Policy (CSP) `<meta>` tag exists in `frontend/index.html`.
     - Backend `RequestContextMiddleware` (`app/middleware/request_context.py:42`) sets `X-Content-Type-Options: nosniff` and `X-Request-ID`, but does not issue a `Content-Security-Policy` header.

2. **Backend Pytest Test Suite Baseline**:
   - Executed Command: `.venv\Scripts\python.exe -m pytest --collect-only -q`
     - **Result**: Exactly **331 tests collected** across 33 test files.
   - Executed Full Run: `.venv\Scripts\python.exe -m pytest -q --tb=short`
     - **Result**: **329 passed**, **2 failed**, 1016 warnings in 40.36s.
   - Failed Test 1: `tests/test_rc_security_v7.py::test_aes_gcm_crypto_round_trip`
     - Verbatim error: `AssertionError: assert False where False = 'enc:Y8hB6RxIl...'.startswith('enc:gcm:')`
     - Cause: `cryptography` library is missing in `.venv` (`ModuleNotFoundError: No module named 'cryptography'`). In `app/core/security/crypto.py:8–13`, `HAS_AESGCM` evaluates to `False`, falling back to the legacy PBKDF2-HMAC stream cipher (`enc:` prefix instead of `enc:gcm:`).
   - Failed Test 2: `tests/test_school.py::test_school_api_rbac`
     - Verbatim error: `assert 403 == 200 where 403 = <Response [403 Forbidden]>.status_code`
     - Log: `AppException handled: Akses ditolak: Anda tidak memiliki akses ke profil sekolah ini. (status_code=403)`
     - Cause: In step 4 of `test_school.py` (Line 154), `test_teacher` attempts to read the single school profile created by superadmin (`API School`). In `app/api/school.py:125–131`, strict multi-tenant boundary checks reject non-superadmin users attempting to read another school's profile (`if not user_school_id or school.id != user_school_id: raise BusinessException(..., 403)`).

3. **Frontend Build Baseline (`npm run build`)**:
   - Executed Command: `npm run build` in `frontend/` (`tsc -b && vite build`)
   - **Result**: Exited with code **0** (built in 1.62s).
   - Output: 39 JS chunks and 2 CSS bundles in `dist/`, 0 errors, no `.map` sourcemap files generated.

---

## 2. Logic Chain

1. **R4 Logic**:
   - *Premise 1*: Backend configuration modules (`AiConfig`, `RagContextService`, `EmbeddingService`) support and consume `eval_model_name`, `strict_transformer`, `max_rag_context_tokens`, `rag_top_k`, `rag_similarity_threshold`, and `embedding_model`.
   - *Premise 2*: Webhook HMAC verification and replay event logging exist in `app/api/exam.py` and `app/services/exam/exam_service.py`.
   - *Observation*: `AiProviderConfigUpdateRequest` and `SuperAdminAiSystemView.tsx` only allow modifying `provider, api_key, model_name, fallback_model, temperature, max_output_tokens, rag_enabled`.
   - *Deduction*: There is an architectural disconnect where advanced AI governance and safety parameters exist in the backend engine but cannot be configured, persisted, or observed through the SuperAdmin interface. Exposing these requires extending `AiProviderConfigUpdateRequest`, `AiProviderConfigResponse`, `AiSystemOverviewResponse`, `superadminAiApi`, and `SuperAdminAiSystemView.tsx`.

2. **R5 Logic**:
   - *Premise 1*: The authoritative acceptance criteria require root-level `confidence` (float), `confidence_level` (string: HIGH/MEDIUM/LOW), and `review_required` (boolean) in grading evaluation responses.
   - *Observation*: `GradingEvaluateResponse` only carries `decision["quality_indicator"]` inside an unstructured dictionary and has no root-level confidence fields.
   - *Observation*: `TeacherGradingView.tsx` currently only renders raw score and feedback input without any confidence gauge, categorical badge (Auto Accept / Requires Review / Manual Review Required), rubric criteria weights, or academic rationales.
   - *Deduction*: Both backend schema elevation and frontend presentation expansion are necessary to satisfy R5:
     1. Add root-level fields to `GradingEvaluateResponse` (and propagate them into teacher student answers response).
     2. Calculate `confidence` (0.0–1.0), derive `confidence_level` (HIGH >= 0.90, MEDIUM 0.75–0.89, LOW < 0.75), and set `review_required = (confidence < 0.90)`.
     3. Update `TeacherGradingView.tsx` Level 3 view to render the visual confidence gauge, categorical badge, rubric breakdown table, and academic rationale accordion.

3. **R6 Logic**:
   - *Observation 1*: Pytest discovers 331 tests, with 329 passing and 2 failing.
   - *Observation 2*: `test_aes_gcm_crypto_round_trip` fails because `cryptography` is not in `.venv`.
   - *Observation 3*: `test_school_api_rbac` fails because step 4 tests cross-tenant read by a teacher, which was intentionally hardened to 403 by multi-tenant security in RC-V7.
   - *Observation 4*: Frontend build succeeds with 0 errors, but lacks explicit `sourcemap: false`, console stripping, DevTools detection, and CSP headers/meta tags.
   - *Deduction*: To achieve the baseline criterion of 331+ tests passing (0 failures) and hardened client:
     1. Install `cryptography` in `.venv` (and add to requirements).
     2. Align `test_school_api_rbac` step 4 with multi-tenant rules (e.g. read own school or verify 403 on cross-tenant read).
     3. Lock `sourcemap: false` and configure `esbuild.drop: ['console', 'debugger']` in `vite.config.ts`.
     4. Add DevTools deterrence signal and configure CSP meta tag in `index.html` and CSP headers in `RequestContextMiddleware`.

---

## 3. Caveats

1. **Read-Only Scope**: In compliance with the investigator role, no source code files were altered during this survey.
2. **Pytest Count Baseline**: The current codebase contains exactly 331 tests. Writing new security tests for R1, R2, R4, R5, and R6 will increase the total test count beyond 331+ (as required by Acceptance Criteria).
3. **Teacher Student Answers Endpoint**: In `app/api/teacher.py:1541`, student answers are read from `ExamAttempt` and `ExamAnswerEvaluation`. If evaluations were created without rubric breakdowns or confidence stored in DB, fallback mock/calculated values from the question's rubric JSON must be synthesized for display.

---

## 4. Conclusion

1. **R4 Delta**:
   - Backend `AiProviderConfigUpdateRequest` must be extended with: `eval_model_name: Optional[str]`, `strict_transformer: Optional[bool]`, `embedding_model: Optional[str]`, `rag_top_k: Optional[int]`, `rag_similarity_threshold: Optional[float]`, `max_rag_tokens: Optional[int]`.
   - Backend `AiSystemOverviewResponse` must be extended with `ai_safety_status: { hmac_callback_configured: bool, webhook_secret_set: bool, replay_protection_active: bool }`.
   - `SuperAdminAiSystemView.tsx` requires:
     - Input for `eval_model_name` (Evaluation Model).
     - Toggle switch for `strict_transformer`.
     - Tuning sliders/inputs for RAG (Embedding Model, Top-K, Similarity Threshold, Context Token Limit).
     - Safety status badges in the Overview and Config tabs (HMAC Callback Health, Webhook Secret Verification, Replay Protection Status).

2. **R5 Delta**:
   - `GradingEvaluateResponse` (`app/services/ai/grading/grading_schema.py`) must include:
     ```python
     confidence: float = Field(..., description="Root-level grading confidence (0.0 - 1.0)")
     confidence_level: str = Field(..., description="Categorical confidence: HIGH, MEDIUM, or LOW")
     review_required: bool = Field(..., description="Whether manual teacher review is required")
     ```
   - In `GradingService.evaluate`:
     - Calculate `confidence = quality_indicator`.
     - Assign `confidence_level = "HIGH" if confidence >= 0.90 else "MEDIUM" if confidence >= 0.75 else "LOW"`.
     - Assign `review_required = confidence < 0.90`.
   - In `app/api/teacher.py` (`student-answers` endpoint): Return `confidence`, `confidence_level`, `review_required`, `rubric_scores`, and `academic_rationale` in each answer object.
   - In `TeacherGradingView.tsx`: Render a visual confidence gauge component, categorical badge (HIGH: 90–100% Auto Accept, MEDIUM: 75–89% Requires Review, LOW: 0–74% Manual Review Required), detailed rubric criteria breakdown with points achieved per criterion, and generated academic rationales.

3. **R6 Delta**:
   - **Pytest Baseline**: Current test count is 331 (329 pass, 2 fail). Resolving the missing `cryptography` dependency fixes `test_aes_gcm_crypto_round_trip`. Aligning `test_school_api_rbac` with the multi-tenant isolation rule brings the baseline to 331 passing tests (0 failures).
   - **Client Hardening**:
     - Explicitly declare `sourcemap: false` and `esbuild: { drop: ['console', 'debugger'] }` in `frontend/vite.config.ts`.
     - Add CSP `<meta http-equiv="Content-Security-Policy" ...>` in `frontend/index.html`.
     - Add CSP header in `app/middleware/request_context.py`.
     - Add lightweight DevTools detection/deterrence in frontend initialization.
     - `npm run build` currently succeeds (1.62s) and maintains clean build hygiene.

---

## 5. Verification Method

1. **Verify Test Collection Count**:
   ```powershell
   .venv\Scripts\python.exe -m pytest --collect-only -q
   # Expected output: 331 tests collected (or 331+ after new tests added)
   ```

2. **Verify Failing Test Diagnoses**:
   ```powershell
   .venv\Scripts\python.exe -m pytest tests/test_rc_security_v7.py::test_aes_gcm_crypto_round_trip tests/test_school.py::test_school_api_rbac -vv
   ```

3. **Verify Frontend Build**:
   ```powershell
   cd frontend
   npm run build
   # Verify dist/ contains no .map files and exits with code 0
   ```

4. **Verify File Locations**:
   - `frontend/src/views/superadmin/SuperAdminAiSystemView.tsx`
   - `frontend/src/views/teacher/TeacherGradingView.tsx`
   - `app/schemas/ai/ai_management.py`
   - `app/services/ai/grading/grading_schema.py`
   - `app/services/ai/grading/grading_service.py`
   - `frontend/vite.config.ts`
   - `frontend/index.html`
