# Task Assignment: E2E Test Suite Creation (Tiers 1-4)

- Working Directory: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_test_writer_e2e
- Workspace Root: C:\Users\irul2\Downloads\Equigrade_x_Lockxam
- Authoritative Request File: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\ORIGINAL_REQUEST.md
- Project Scope: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\PROJECT.md

## Scope & File Ownership
You exclusively own:
- `tests/e2e/` (create this directory and write test files here)
- `TEST_INFRA.md` (at project root `C:\Users\irul2\Downloads\Equigrade_x_Lockxam\TEST_INFRA.md`)
- `TEST_READY.md` (at project root `C:\Users\irul2\Downloads\Equigrade_x_Lockxam\TEST_READY.md`)

DO NOT edit any production code (`app/` or `frontend/`).

## Methodology: 4-Tier Opaque-Box Test Suite
Design and implement an opaque-box test suite based strictly on user requirements from `ORIGINAL_REQUEST.md` and `PROJECT.md § Feature Inventory` (Features 1–23):
1. **Tier 1 - Feature Coverage (>=5 per feature)**:
   - R1: Elimination of `x-lockxam-dev-bypass`, `lockxam_dev_bypass`, and `COOKIE_SECURE=false` student bypass; non-APK student requests fail closed with HTTP 403.
   - R2: Forced password change enforcement via FastAPI dependency; blocked from all endpoints (HTTP 403) except `/auth/change-password`, `/auth/logout`, and `/auth/me`.
   - R3: QR check-in leaves student on schedule screen with live countdown; `enterKioskMode()` only on authorized `start_attempt`; backend window enforcement (`now_utc < start_at` returns 400); Android soft-keyboard suppression in essay/short-answer.
   - R4: SuperAdmin AI control center configuration (`eval_model_name`, strict transformer, RAG params, AI safety status indicators).
   - R5: AI confidence elevation (`confidence`, `confidence_level`, `review_required`) and teacher review experience.
   - R6: Client hardening (Vite minification, sourcemaps disabled, CSP, DevTools deterrence).
2. **Tier 2 - Boundary & Corner Cases (>=5 per feature)**:
   - Expired tokens, clock-skew offsets, empty passwords, maximum token context limits, edge boundary scores (89.9% vs 90.0% confidence tier thresholds).
3. **Tier 3 - Cross-Feature Combinations**:
   - Check-in before window opens -> start_attempt before window -> start_attempt after window with must_change_password=True.
   - AI grading callback with invalid HMAC signature vs valid HMAC signature + replay duplicate event.
4. **Tier 4 - Real-World Workload Scenarios**:
   - Full student exam lifecycle from check-in to submission to teacher grading review.

Write the tests in `tests/e2e/`, ensure they run via pytest (`.venv\Scripts\pytest.exe tests/e2e/`), create `TEST_INFRA.md` and `TEST_READY.md`, and report back with your handoff.

## 2026-09-11T02:20:44Z
You are teamwork_preview_test_writer_e2e.
Your working directory is: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_test_writer_e2e
The workspace root is: C:\Users\irul2\Downloads\Equigrade_x_Lockxam
The authoritative request file is: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\ORIGINAL_REQUEST.md

You MUST read C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\ORIGINAL_REQUEST.md before starting work.
Also read C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\PROJECT.md and C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_test_writer_e2e\DISPATCH.md.

Your mission:
Design and build an opaque-box E2E test suite (Tiers 1-4) covering all features from ORIGINAL_REQUEST.md and PROJECT.md § Feature Inventory.
You exclusively own:
- tests/e2e/ (create directory and write tests here)
- TEST_INFRA.md at project root
- TEST_READY.md at project root

Do NOT edit any production application code.
Run the test suite using pytest (.venv\Scripts\pytest.exe tests/e2e/), ensure it runs cleanly, create TEST_INFRA.md and TEST_READY.md, write your handoff report to C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_test_writer_e2e\handoff.md, and notify the orchestrator via send_message.
