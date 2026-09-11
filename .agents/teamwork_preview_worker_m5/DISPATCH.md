# Task Assignment: Milestone 5 - Layer 2 Client Hardening & Regression Baseline (R6)

- Working Directory: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_worker_m5
- Workspace Root: C:\Users\irul2\Downloads\Equigrade_x_Lockxam
- Authoritative Request File: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\ORIGINAL_REQUEST.md
- Project Scope: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\PROJECT.md
- Survey Handoff: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_explorer_survey_3\handoff.md

## Exclusive Write Ownership
You exclusively own and may edit:
- `frontend/vite.config.ts`
- `frontend/index.html`
- `frontend/src/utils/securityDeterrence.ts` (or devtools deterrence helper)
- `app/middleware/request_context.py`
- `tests/test_school.py`
- `requirements.txt` (and installing packages into `.venv`)

DO NOT edit files owned by other milestones.

## Implementation Scope
1. **Pytest Regression Baseline Resolution (331 Passing Tests, 0 Failures)**:
   - Install `cryptography` in `.venv`:
     Execute `.venv\Scripts\pip.exe install cryptography` and add `cryptography>=41.0.0` to `requirements.txt`.
     Verify that `test_aes_gcm_crypto_round_trip` in `tests/test_rc_security_v7.py` passes.
   - Fix `tests/test_school.py::test_school_api_rbac`:
     In step 4, the test teacher attempts to read another school's profile which is blocked (403) by strict multi-tenant isolation. Update the test to verify that cross-tenant read correctly returns HTTP 403, and test reading the teacher's own school profile returns HTTP 200.
   - Verify that ALL 331 tests in the baseline test suite pass with 0 failures!

2. **Frontend Layer 2 Client Hardening**:
   - In `frontend/vite.config.ts`:
     - Configure `build: { sourcemap: false, minify: "esbuild", ... }` explicitly.
     - Configure `esbuild: { drop: mode === "production" ? ["console", "debugger"] : [] }`.
   - In `frontend/index.html`:
     - Add strict Content-Security-Policy (CSP) meta tag restricting scripts, styles, and iframe framing.
   - In `app/middleware/request_context.py`:
     - Add `Content-Security-Policy` and defense-in-depth response headers.
   - Add a lightweight DevTools detection/deterrence module in `frontend/src/` that logs deterrence signals if inspection is attempted in student views.

3. **Mandatory Integrity Warning**:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Verification
- Run full pytest suite: `.venv\Scripts\pytest.exe -q` (all 331+ tests MUST pass, 0 failures).
- Run frontend build: `npm run build` in `frontend/` (0 errors, minified artifacts, sourcemaps disabled, no `.map` files in `dist/`).
- Document all changes and verification outputs in `C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_worker_m5\handoff.md`.

## 2026-09-11T02:20:45Z
You are teamwork_preview_worker_m5.
Your working directory is: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_worker_m5
The workspace root is: C:\Users\irul2\Downloads\Equigrade_x_Lockxam
The authoritative request file is: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\ORIGINAL_REQUEST.md

You MUST read C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\ORIGINAL_REQUEST.md before starting work.
Also read C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\PROJECT.md and C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_worker_m5\DISPATCH.md.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your mission:
Implement Milestone 5 (Layer 2 Client Hardening & Regression Baseline R6):
- Install cryptography in .venv (.venv\Scripts\pip.exe install cryptography) and update requirements.txt so test_aes_gcm_crypto_round_trip passes.
- Fix tests/test_school.py::test_school_api_rbac step 4 to align with multi-tenant isolation rules.
- Verify full test suite: .venv\Scripts\pytest.exe -q (all 331 tests must pass with 0 failures).
- Harden frontend in frontend/vite.config.ts (sourcemap: false, esbuild drop console/debugger in production).
- Add CSP meta tag in frontend/index.html, CSP header in app/middleware/request_context.py, and DevTools deterrence signal.
- Run frontend build (npm run build in frontend/) and verify 0 errors and minified assets without sourcemaps.
- Write handoff report to C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_worker_m5\handoff.md and report back via send_message.
