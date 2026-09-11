# Test Infrastructure Specification: Equigrade x Lockxam v10

## 1. Overview
This document specifies the end-to-end (E2E) testing infrastructure for Equigrade x Lockxam v10. The test suite is designed as an independent, opaque-box test harness verifying all 6 security and feature audit remediation areas (R1–R6) and 23 features detailed in `ORIGINAL_REQUEST.md` and `PROJECT.md`.

## 2. 4-Tier Test Architecture
The test suite follows a 4-tier opaque-box validation hierarchy:

### Tier 1: Feature Coverage (>= 5 test cases per feature)
- **R1: Elimination of Student Browser Bypass & Non-APK Fail Closed**
  1. `test_student_login_browser_no_bypass_fails_403`: Standard browser User-Agent rejected with HTTP 403 Forbidden.
  2. `test_student_login_with_x_lockxam_dev_bypass_fails_403`: Header `x-lockxam-dev-bypass: true` rejected with HTTP 403.
  3. `test_student_login_cookie_secure_false_env_fails_403`: `COOKIE_SECURE=false` environment setting does not permit non-APK student login.
  4. `test_student_login_query_param_bypass_fails_403`: URL query parameter bypass attempts rejected with HTTP 403.
  5. `test_student_valid_apk_login_succeeds_200`: Valid APK headers (`x-client-app: lockxam_apk` or `LockxamBrowser/1.0`) succeed with HTTP 200.
  6. `test_non_student_browser_login_allowed_200`: Teachers and SuperAdmins can login via web browser without APK headers.

- **R2: Backend Enforcement of Forced Password Change**
  1. `test_forced_password_blocks_exam_endpoints_403`: Students/teachers with `must_change_password=True` receive HTTP 403 on `/api/v1/exam/*`.
  2. `test_forced_password_blocks_schools_endpoints_403`: Account with `must_change_password=True` blocked on `/api/v1/schools/*`.
  3. `test_forced_password_blocks_teacher_endpoints_403`: Account with `must_change_password=True` blocked on `/api/v1/teacher/*`.
  4. `test_forced_password_exempt_me_endpoint_200`: `/api/v1/auth/me` returns 200 and exposes `must_change_password=True`.
  5. `test_forced_password_exempt_logout_204`: `/api/v1/auth/logout` allows revoking session with HTTP 204.
  6. `test_forced_password_exempt_change_password_and_unblock_200`: Calling `/api/v1/auth/change-password` clears flag and unblocks application access.

- **R3: CBT Exam State Machine & Android Keyboard Suppression**
  1. `test_qr_checkin_success_persists_schedule_state`: QR check-in records attendance and returns HTTP 200 without transitioning attempt to ACTIVE.
  2. `test_start_attempt_before_window_fails_400`: Starting attempt before scheduled start time strictly returns HTTP 400 "Waktu pelaksanaan ujian belum tiba.".
  3. `test_start_attempt_without_checkin_fails_400`: Starting attempt without prior QR check-in returns HTTP 400.
  4. `test_start_attempt_within_window_succeeds_200`: Starting attempt within active window returns HTTP 200 and attempt data.
  5. `test_client_cbt_engine_keyboard_suppression_attributes`: Verifies static component contract for `inputMode="none"` and `readOnly={true}`.
  6. `test_kiosk_mode_restricted_to_start_attempt_success`: Verifies `enterKioskMode()` is not invoked on mount, only post-start.

- **R4: SuperAdmin AI Control Center Expansion**
  1. `test_superadmin_get_ai_overview_includes_safety_status`: Overview endpoint returns `ai_safety_status` dictionary.
  2. `test_superadmin_get_ai_config_includes_eval_model_and_strict`: Active config exposes `eval_model_name` and `strict_transformer`.
  3. `test_superadmin_update_ai_config_eval_model_and_rag_params`: Config update accepts `eval_model_name`, `strict_transformer`, and RAG tuning parameters.
  4. `test_superadmin_ai_safety_status_indicators_reflect_webhook_secret`: Safety status accurately flags HMAC webhook secret configuration.
  5. `test_superadmin_ai_rbac_non_superadmin_forbidden_403`: Non-superadmin access to AI system endpoints is strictly forbidden (HTTP 403).

- **R5: AI Confidence Level Elevation & Teacher Review Experience**
  1. `test_grading_evaluate_response_root_confidence_fields`: Grading response schema includes root-level `confidence`, `confidence_level`, `review_required`.
  2. `test_grading_confidence_threshold_high_auto_accept`: Confidence >= 0.90 classified as HIGH with `review_required=False`.
  3. `test_grading_confidence_threshold_medium_requires_review`: Confidence 0.75–0.89 classified as MEDIUM with `review_required=True`.
  4. `test_grading_confidence_threshold_low_manual_review`: Confidence < 0.75 classified as LOW with `review_required=True`.
  5. `test_teacher_student_answers_propagates_confidence_and_rationale`: Teacher grading review endpoint exposes confidence metrics and rubric breakdown.

- **R6: Layer 2 Client Hardening & Production Baseline**
  1. `test_vite_config_sourcemaps_disabled`: Verifies `sourcemap: false` in production build configuration.
  2. `test_vite_config_console_and_debugger_stripped`: Verifies esbuild drops console and debugger statements.
  3. `test_index_html_csp_meta_tag_present`: Verifies Content Security Policy meta tag exists.
  4. `test_devtools_deterrence_signal_configured`: Verifies client-side DevTools deterrence signal is integrated.
  5. `test_crypto_and_baseline_regression_suite_clean`: Verifies full suite of 331 baseline unit/integration tests passes without failure.

### Tier 2: Boundary & Corner Cases (>= 5 test cases per feature)
- Expired access tokens and session absolute/idle timeout boundaries.
- Negative and zero clock-skew tolerances for countdown synchronization.
- Password change empty/short/invalid boundary validations.
- AI token limit extremes (min 128, max 16384, negative context values).
- Precise floating-point boundaries for confidence tiers (0.749 vs 0.750, 0.899 vs 0.900, 1.000).

### Tier 3: Cross-Feature Combinations
- Combination 1: Check-in before window opens -> attempt start rejected (HTTP 400) -> start attempt after window opens with `must_change_password=True` -> rejected with HTTP 403 -> password changed -> start attempt succeeds (HTTP 200).
- Combination 2: AI grading callback with missing HMAC -> rejected (HTTP 403) -> invalid HMAC -> rejected (HTTP 403) -> valid HMAC -> accepted (HTTP 200) -> replayed identical event -> idempotency handled.
- Combination 3: Non-APK student login attempt with dev-bypass header -> fails (HTTP 403) -> switch to APK header -> succeeds (HTTP 200) -> account flagged `must_change_password=True` -> restricted until password change.

### Tier 4: Real-World Workload Scenarios
- Scenario 1: Multi-role exam lifecycle from school provisioning to student check-in, exam completion, background AI evaluation, and teacher grade review with confidence categorization.

## 3. Test Suite Organization
```
tests/
├── conftest.py                     # Root fixtures and DB session lifecycle
└── e2e/                            # Opaque-box E2E test suite
    ├── __init__.py
    ├── conftest.py                 # E2E fixtures, clients, seed helpers
    ├── test_tier1_r1_auth_bypass.py
    ├── test_tier1_r2_forced_password.py
    ├── test_tier1_r3_exam_lifecycle.py
    ├── test_tier1_r4_superadmin_ai.py
    ├── test_tier1_r5_ai_confidence.py
    ├── test_tier1_r6_client_hardening.py
    ├── test_tier2_boundaries.py
    ├── test_tier3_cross_feature.py
    └── test_tier4_workloads.py
```

## 4. Execution Commands
- Run complete E2E test suite:
  ```powershell
  $env:PYTHONPATH="."
  .venv\Scripts\pytest.exe tests/e2e/ -v
  ```
- Run specific tier:
  ```powershell
  .venv\Scripts\pytest.exe tests/e2e/test_tier1_r1_auth_bypass.py -v
  ```
