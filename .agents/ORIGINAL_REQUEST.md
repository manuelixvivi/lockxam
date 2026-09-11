# Original User Request

## 2026-09-11T02:09:42Z

Comprehensive implementation and verification of the Equigrade x Lockxam v10 security and feature audit remediations, hardening student boundaries, fixing exam engine workflows, and extending AI governance.

Working directory: C:\Users\irul2\Downloads\Equigrade_x_Lockxam
Integrity mode: development

## Requirements

### R1. Absolute Elimination of Student Browser Bypass
Completely remove all student dev-bypass headers, flags, query parameters, and fallback conditions (`x-lockxam-dev-bypass`, `lockxam_dev_bypass`, and `COOKIE_SECURE=false` bypass) across backend authentication (`auth_service.py`) and frontend guards (`LockxamAppGuard.tsx`, `LoginView`). Unauthenticated or non-APK student requests must fail closed with HTTP 403 Forbidden.

### R2. Backend Enforcement of Forced Password Change
Enforce `must_change_password` at the server level via a mandatory FastAPI authorization dependency. Users flagged with `must_change_password=True` must be strictly blocked from all application endpoints (returning HTTP 403) with the exception of password modification (`/auth/change-password`), session termination (`/auth/logout`), and profile verification (`/auth/me`).

### R3. CBT Exam State Machine & Android Keyboard Suppression
- Re-architect the check-in and kiosk lifecycle: Successful QR check-in keeps the student in a confirmed dashboard state with a live server-synchronized countdown. Kiosk mode (`enterKioskMode()`) must ONLY activate upon an authorized attempt start (`start_attempt`) when the server exam window is actively open.
- Eliminate native Android soft-keyboard conflicts in CBT essay and short-answer components using `inputMode="none"`, read-only textarea handling, and programmatic Lockxam virtual keypad input.

### R4. SuperAdmin AI Control Center Expansion
Extend the SuperAdmin AI Configuration management interface in `SuperAdminAiSystemView.tsx` to expose all available backend AI parameters, including Evaluation Model (`eval_model_name`), Strict Transformer enforcement, RAG tuning parameters (Embedding model, Top-K, similarity thresholds, context limits), and AI Safety status indicators (HMAC callback health, configured webhook secret verification, replay protection status).

### R5. AI Confidence Level Elevation & Teacher Review Experience
- Elevate AI Confidence to first-class fields (`confidence`, `confidence_level`, `review_required`) in the grading evaluation API responses.
- In the Teacher grading detail interface, present the grading output with a visual confidence gauge, categorical classification (HIGH: 90–100% / Auto Accept, MEDIUM: 75–89% / Requires Review, LOW: 0–74% / Manual Review Required), rubric criteria breakdowns, and generated academic rationales.

### R6. Layer 2 Client Hardening & Regression Testing
Apply client-side defense-in-depth protections (Vite production minification, selective code obfuscation, sourcemap stripping, DevTools detection/deterrence signals, Content Security Policy) as client hardening under backend authority. Ensure all existing and new security unit/integration tests pass with zero regressions.

## Acceptance Criteria

### Security & Bypass Elimination
- [ ] No occurrences of `x-lockxam-dev-bypass` or `lockxam_dev_bypass` remain in backend or frontend codebases.
- [ ] Attempting to login or access student endpoints via browser dev bypass triggers HTTP 403.
- [ ] Any authenticated request to exam, student, teacher, or administrative endpoints with `must_change_password=True` returns HTTP 403, while `/auth/change-password`, `/auth/logout`, and `/auth/me` remain accessible.
- [ ] Regression test suite specifically verifies `must_change_password` endpoint lockdown and bypass rejection.

### Exam Engine & Kiosk Execution
- [ ] Completing QR check-in leaves the student on the schedule screen showing an active countdown without entering kiosk mode.
- [ ] `enterKioskMode()` executes exclusively upon receiving a successful response from `start_attempt`.
- [ ] Focusing essay and short-answer input fields in the CBT interface does not open the Android native soft keyboard.

### AI Governance & Teacher Interface
- [ ] AI grading evaluation API returns root-level `confidence` (float), `confidence_level` (string: HIGH/MEDIUM/LOW), and `review_required` (boolean).
- [ ] Teacher AI grading review UI displays score, confidence gauge, categorical badge, decision recommendation, and rubric criterion breakdown.
- [ ] SuperAdmin AI system settings panel allows configuring `eval_model_name`, strict transformer flag, and displays AI safety webhook verification indicators.

### Quality & Build Verification
- [ ] Pytest execution completes with all tests passing (minimum 331+ tests, 0 failures).
- [ ] Frontend build (`npm run build`) completes with 0 errors and produces minified artifacts with sourcemaps disabled.
