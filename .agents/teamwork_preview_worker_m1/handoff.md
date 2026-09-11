# Milestone 1: Auth & Security Bypass Remediation (R1, R2) - Handoff Report

## 1. Observation

### 1.1 Scope & Modified Files
Exclusive write ownership was respected. Only the assigned files and test files were modified:
- `app/services/security/auth_service.py`: Completely stripped developer bypasses and `COOKIE_SECURE=false` bypasses. Enforced fail-closed HTTP 403 on non-APK student requests. Enforced unconditional single-device lock for students. Corrected session revocation reason enum to `SessionRevokedReason.USER_FORCE_LOGOUT`.
- `app/core/dependencies.py`: In `get_current_user`, added database account lookup, fail-closed non-APK student role check, and strict `must_change_password` check returning HTTP 403 Forbidden for all non-exempt endpoints.
- `frontend/src/components/ui/LockxamAppGuard.tsx`: Removed developer bypass state (`devBypass`), sessionStorage reads/writes (`lockxam_dev_bypass`), bypass button, and simulation banner. Only legitimate APK signatures permit student access.
- `tests/conftest.py`: Explicitly set `must_change_password=False` on shared test fixtures (`test_superadmin`, `test_teacher`) and added a SQLAlchemy `before_flush` hook defaulting `must_change_password=False` on newly created test accounts unless explicitly tagged with `_keep_must_change_password=True`.
- `tests/test_regression_r1.py`: Added 7 comprehensive regression tests covering student browser rejection, `x-lockxam-dev-bypass` header rejection, `COOKIE_SECURE=false` bypass rejection, APK header acceptance, non-APK student endpoint access rejection, APK student endpoint access acceptance, and unconditional single-device lock.
- `tests/test_regression_r2.py`: Added 4 comprehensive regression tests covering complete lockdown of non-exempt endpoints when `must_change_password=True`, access to strictly exempt endpoints (`/auth/me`, `/auth/logout`, `/auth/change-password`), full password recovery workflow, and student exam endpoint blockage.

### 1.2 Git Diff Summary
```text
 app/core/dependencies.py                       |  34 +++++
 app/services/security/auth_service.py          |  18 +--
 frontend/src/components/ui/LockxamAppGuard.tsx |  61 +-------
 tests/conftest.py                              |   9 ++
 tests/test_regression_r1.py                    | 186 +++++++++++++++++++++++++
 tests/test_regression_r2.py                    | 179 ++++++++++++++++++++++++
 6 files changed, 416 insertions(+), 71 deletions(-)
```

### 1.3 Verbatim Test Results
#### Specific M1 Regression Test Suite:
Command: `.venv\Scripts\python -m pytest tests/test_regression_r1.py tests/test_regression_r2.py -v`
Output:
```text
tests/test_regression_r1.py::test_web_login_session_duration PASSED      [  4%]
tests/test_regression_r1.py::test_apk_login_session_duration PASSED      [  9%]
tests/test_regression_r1.py::test_web_refresh_rotation_preserves_expiry PASSED [ 14%]
tests/test_regression_r1.py::test_apk_refresh_rotation_preserves_expiry PASSED [ 19%]
tests/test_regression_r1.py::test_refresh_only_reads_httponly_cookie PASSED [ 23%]
tests/test_regression_r1.py::test_logout_deletes_cookie_and_revokes_db_session PASSED [ 28%]
tests/test_regression_r1.py::test_student_login_rejected_from_web_browser PASSED [ 33%]
tests/test_regression_r1.py::test_student_login_with_x_lockxam_dev_bypass_fails_403 PASSED [ 38%]
tests/test_regression_r1.py::test_student_login_with_cookie_secure_false_bypass_fails_403 PASSED [ 42%]
tests/test_regression_r1.py::test_student_login_success_with_apk_headers PASSED [ 47%]
tests/test_regression_r1.py::test_student_endpoint_access_rejected_without_apk PASSED [ 52%]
tests/test_regression_r1.py::test_student_endpoint_access_allowed_with_apk PASSED [ 57%]
tests/test_regression_r1.py::test_student_single_device_binding_unconditional PASSED [ 61%]
tests/test_regression_r2.py::test_toggle_school_subscription_syncs_status PASSED [ 66%]
tests/test_regression_r2.py::test_create_school_returns_credentials PASSED [ 71%]
tests/test_regression_r2.py::test_list_activation_keys_rbac_and_ordering PASSED [ 76%]
tests/test_regression_r2.py::test_must_change_password_exposed_via_me PASSED [ 80%]
tests/test_regression_r2.py::test_forced_password_change_blocks_all_non_exempt_endpoints PASSED [ 85%]
tests/test_regression_r2.py::test_forced_password_change_allows_strictly_exempt_endpoints PASSED [ 90%]
tests/test_regression_r2.py::test_forced_password_change_workflow_and_recovery PASSED [ 95%]
tests/test_regression_r2.py::test_forced_password_change_blocks_student_exam_endpoints PASSED [100%]
======================= 21 passed, 15 warnings in 6.84s =======================
```

#### Full Test Suite:
Command: `.venv\Scripts\python -m pytest -q`
Output:
```text
348 passed, 303 warnings in 47.93s
```

#### Frontend Build:
Command: `npm run build` (in `frontend/`)
Output:
```text
> frontend@0.0.0 build
> tsc -b && vite build

vite v8.2.1 building client environment for production...
transforming...✓ 1872 modules transformed.
rendering chunks...
computing gzip size...
✓ built in 1.77s
```

#### Linting:
Command: `ruff check app/core/dependencies.py app/services/security/auth_service.py tests/conftest.py tests/test_regression_r1.py tests/test_regression_r2.py`
Output:
```text
All checks passed!
```

#### Workspace Bypass Term Scan:
Searched for `x-lockxam-dev-bypass` and `lockxam_dev_bypass` across the workspace:
- Total in application source code (`app/`, `frontend/src/`): **0 occurrences**
- Present only in regression test assertions (`tests/test_regression_r1.py`, `tests/e2e/test_tier1_r1_auth_bypass.py`) verifying that supplying such headers/parameters strictly triggers HTTP 403 Forbidden.

---

## 2. Logic Chain

1. **R1 Elimination of Dev-Bypasses**:
   - In `app/services/security/auth_service.py`, previously:
     ```python
     dev_bypass = request.headers.get("x-lockxam-dev-bypass") == "true" or os.getenv("COOKIE_SECURE", "true") == "false"
     if account.role == UserRole.STUDENT and not is_apk and not dev_bypass:
         raise PermissionException(...)
     ```
   - Any client sending `x-lockxam-dev-bypass: true` or running in an environment with `COOKIE_SECURE=false` could log in as a student from an arbitrary desktop web browser, completely bypassing the Lockxam APK sandbox.
   - Furthermore, the single-device binding check in `auth_service.py` was skipped if `dev_bypass` was truthy.
   - **Remediation**: The `dev_bypass` variable, `x-lockxam-dev-bypass` header inspection, and `COOKIE_SECURE=false` check were removed entirely. Any student login request where `not is_apk` immediately raises `PermissionException("Akses ujian hanya diperbolehkan melalui aplikasi resmi Lockxam.")` resulting in HTTP 403. The single-device binding check was made unconditional for student accounts.
   - In `frontend/src/components/ui/LockxamAppGuard.tsx`, the `devBypass` state, `sessionStorage.getItem("lockxam_dev_bypass")`, the "Bypass untuk Developer (Simulasi APK)" button, and banner were removed. The guard now checks solely whether the application is running inside an authentic Lockxam APK environment (`window.__LOCKXAM_DEVICE__`, `window.LockxamAndroid`, or Android user agent).

2. **R2 Server-Enforced `must_change_password` Lockdown**:
   - The frontend previously had a route-level redirect (`ForceChangePasswordView`), but an attacker or student could call API endpoints directly without changing their password.
   - **Remediation**: Centralized enforcement was placed inside `app/core/dependencies.py` in the `get_current_user` dependency:
     - Retrieves the database `AuthAccount` record using `auth_repository.get_by_id(db, token_payload.account_id)`.
     - Validates that non-APK student requests are blocked with HTTP 403.
     - Checks `account.must_change_password`. If `True`, compares the request path against the strict whitelist of exempt paths:
       - `/api/v1/auth/change-password`
       - `/api/v1/auth/logout`
       - `/api/v1/auth/me`
     - If the path is not exempt, raises `PermissionException("Anda harus mengubah password terlebih dahulu sebelum melanjutkan.")` with HTTP 403 Forbidden.
   - In `app/services/security/auth_service.py`, when `change_password` is called, `account.must_change_password` is set to `False`, the active session is maintained, and all other concurrent sessions are revoked using `SessionRevokedReason.USER_FORCE_LOGOUT` (fixing a bug where non-existent enum `PASSWORD_CHANGED` threw an AttributeError).

3. **Test Infrastructure Realism & Compatibility**:
   - In `app/models/account.py`, `AuthAccount.must_change_password` defaults to `True`. Existing fixture instances created in other test suites (`test_proctor.py`, `test_academic.py`, `test_license.py`) omit `must_change_password` and thus would be blocked on subsequent API calls.
   - To resolve this cleanly without modifying files outside our milestone, a SQLAlchemy `before_flush` event listener was registered in `tests/conftest.py`. Any new `AuthAccount` created during test execution is assigned `must_change_password = False` by default, unless explicitly annotated with `_keep_must_change_password = True`.
   - Dedicated regression tests in `tests/test_regression_r2.py` use `_keep_must_change_password = True` to verify the lockdown and recovery flows under genuine database conditions.

---

## 3. Caveats

- **Out-of-Scope Files**: Pre-existing modifications in `app/services/exam/exam_service.py`, `frontend/src/views/student/StudentCbtEngineView.tsx`, and `frontend/src/views/superadmin/SuperAdminAiSystemView.tsx` were already present in the workspace and pertain to other milestones. They were left completely intact and untouched.
- **Exempt Path Whitelist**: The exemption in `app/core/dependencies.py` is intentionally minimal (`/auth/change-password`, `/auth/logout`, `/auth/me`). Any future endpoints needed during the mandatory password reset phase must be deliberately added to this whitelist.

---

## 4. Conclusion

Milestone 1 objectives R1 and R2 are fully implemented, verified, and hardened:
- Student browser access bypasses (`x-lockxam-dev-bypass`, `lockxam_dev_bypass`, `COOKIE_SECURE=false`) have been 100% eliminated from both backend and frontend.
- Non-APK student requests fail closed with HTTP 403 Forbidden.
- Student single-device binding check is unconditional.
- Server-side forced password change (`must_change_password`) is enforced at the dependency level, blocking all non-exempt endpoints with HTTP 403 Forbidden.
- Full password change workflow revokes other sessions and restores access to the application.
- All 21 regression tests in `test_regression_r1.py` and `test_regression_r2.py` pass.
- All 348 tests across the entire backend suite pass with 0 failures.
- Frontend builds cleanly with 0 TypeScript/Vite errors.

---

## 5. Verification Method

To independently verify all findings and implementations:

1. **Run R1 & R2 Regression Tests**:
   ```bash
   .venv\Scripts\python -m pytest tests/test_regression_r1.py tests/test_regression_r2.py -v
   ```
   *Expected result*: 21 passed in ~7s.

2. **Run Full Test Suite**:
   ```bash
   .venv\Scripts\python -m pytest -q
   ```
   *Expected result*: 348 passed in ~48s.

3. **Verify Zero Bypass Occurrences in Source Code**:
   ```bash
   git grep -i "x-lockxam-dev-bypass" app/ frontend/src/
   git grep -i "lockxam_dev_bypass" app/ frontend/src/
   ```
   *Expected result*: 0 matches.

4. **Verify Frontend Build**:
   ```bash
   cd frontend && npm run build
   ```
   *Expected result*: `✓ built in ~1.8s` with 0 errors.

5. **Verify Linter Cleanliness**:
   ```bash
   ruff check app/core/dependencies.py app/services/security/auth_service.py tests/conftest.py tests/test_regression_r1.py tests/test_regression_r2.py
   ```
   *Expected result*: `All checks passed!`.
