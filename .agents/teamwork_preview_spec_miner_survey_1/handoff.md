# Specification Survey & Handoff Report: R1 & R2 Auth & Security

**Author:** `teamwork_preview_spec_miner_survey_1`  
**Working Directory:** `C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_spec_miner_survey_1`  
**Target Specifications:** Requirement 1 (Absolute Elimination of Student Browser Bypass) & Requirement 2 (Backend Enforcement of Forced Password Change) from `ORIGINAL_REQUEST.md`.

---

## Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | R1 - Backend Auth | Student APK Header Detection | `AuthService.login` detects whether request originates from official Lockxam APK client | `User-Agent` (containing "Lockxam", "LockxamBrowser", "EquigradeApp") or `X-Client-App` ("lockxam_apk") | Sets `is_apk` boolean flag and determines session duration (30 days vs 12 hours) | Non-APK student requests trigger `PermissionException` | `app/services/security/auth_service.py:68-75` |
| 2 | R1 - Backend Auth | Dev Bypass Header (Vulnerability) | Header allowing students to bypass APK requirement | `x-lockxam-dev-bypass: true` header on `POST /api/v1/auth/login` | Bypasses student APK requirement, allowing browser login | Bypasses 403 error | `app/services/security/auth_service.py:84` |
| 3 | R1 - Backend Auth | COOKIE_SECURE Dev Bypass (Vulnerability) | Environment variable check allowing APK & single-device bypass | `COOKIE_SECURE=false` in `.env` | Bypasses APK requirement and bypasses QR check-in / exam session device locking | Bypasses 403 error | `app/services/security/auth_service.py:85, 105` |
| 4 | R1 - Frontend Guard | Lockxam App Simulation Bypass (Vulnerability) | SessionStorage flag allowing students to bypass client-side LockxamAppGuard | `sessionStorage.getItem("lockxam_dev_bypass") === "true"` | Sets `devBypass=true`, rendering student workspace on public browsers | Displays amber banner, hides restriction barrier | `frontend/src/components/ui/LockxamAppGuard.tsx:14, 26-42, 124-137, 167-187` |
| 5 | R1 - Student Endpoints | Student Exam Endpoints Authorization | Endpoints serving exam workflows to students | JWT token with `role="STUDENT"` | Student exam schedule, check-in, attempt management, telemetry, answers | Currently returns 401 if unauthenticated, but does not verify APK at endpoint level | `app/api/exam.py:59, 117, 154, 292, 461, 613, 733, 787, 826` |
| 6 | R2 - Data Model | `must_change_password` Storage | Database column tracking whether a user must change default credentials | `AuthAccount.must_change_password` boolean column in PostgreSQL/SQLite | Boolean flag returned in `/auth/me` and `CurrentUserResponse` | Defaults to `True` on account creation | `app/models/security/auth_account.py:34` |
| 7 | R2 - Auth Flow | Password Change Action | Endpoint allowing users to change temporary password | `POST /api/v1/auth/change-password` with `old_password`, `new_password` | Hashes new password, sets `must_change_password=False`, revokes all active sessions | Raises 400 on weak password or invalid old password | `app/services/security/auth_service.py:441-465`, `app/api/auth.py:145-157` |
| 8 | R2 - Frontend Guard | Client-side Forced Password View | Route guard in `App.tsx` intercepting users with `must_change_password=True` | `user?.must_change_password` | Renders `<ForceChangePasswordView />` component | Blocks client navigation, but has zero backend enforcement | `frontend/src/App.tsx:153-159` |
| 9 | R2 - Backend Auth | Centralized Auth Dependency | Mandatory dependency verifying token, session, idle timeout, and school status | `HTTPAuthorizationCredentials` Bearer token via `get_current_user` | Decoded JWT payload dict | Raises 401 on missing/expired token, 403 on suspended school | `app/core/dependencies.py:20-98` |
| 10 | R2 - RBAC | Canonical Role Verification | RBAC dependency wrapping `get_current_user` for route permissions | `require_role(*allowed_roles)` | Decoded JWT payload dict | Raises 403 on role mismatch | `app/core/rbac.py:35-84` |

---

## Edge Cases

| # | Feature | Input | Observed Behavior |
|---|---------|-------|-------------------|
| 1 | Student Login | Browser User-Agent + `x-lockxam-dev-bypass: true` | Currently logs in successfully because `dev_bypass` evaluates to True. Must be eliminated to fail closed with HTTP 403. |
| 2 | Student Login | Browser User-Agent + `COOKIE_SECURE=false` | Currently logs in successfully because `os.getenv("COOKIE_SECURE") == "false"`. Must be eliminated to fail closed with HTTP 403. |
| 3 | Single-Device Binding | Concurrent student login when checked-in or active exam + `COOKIE_SECURE=false` | Currently overwrites session instead of rejecting with 403 because of `and os.getenv("COOKIE_SECURE", "true") != "false"`. Must be eliminated so device lock is unconditional. |
| 4 | Student Exam APIs | Unauthenticated or Non-APK request to `/api/v1/exam/schedule` | Unauthenticated currently gives 401; non-APK with student token currently gives 200. Must fail closed with HTTP 403 Forbidden for non-APK student requests. |
| 5 | Forced Password Change | User with `must_change_password=True` calls `/api/v1/auth/me` | Succeeded (200 OK), exposes profile and `must_change_password: true`. Must remain 200 OK (exempt endpoint). |
| 6 | Forced Password Change | User with `must_change_password=True` calls `/api/v1/auth/change-password` | Succeeded (200 OK), changes password and clears flag. Must remain 200 OK (exempt endpoint). |
| 7 | Forced Password Change | User with `must_change_password=True` calls `/api/v1/auth/logout` | Succeeded (204 No Content), logs out user. Must remain 204 No Content (exempt endpoint). |
| 8 | Forced Password Change | User with `must_change_password=True` calls `/api/v1/auth/sessions` | Currently succeeds (200 OK). Must be strictly blocked with HTTP 403 Forbidden. |
| 9 | Forced Password Change | User with `must_change_password=True` calls `/api/v1/schools` or `/api/v1/exam/schedule` | Currently succeeds (200 OK) if token has appropriate role. Must be strictly blocked with HTTP 403 Forbidden. |
| 10 | Pytest Test Fixtures | `test_superadmin` and `test_teacher` in `tests/conftest.py` without `must_change_password=False` | Because `AuthAccount.must_change_password` defaults to `True`, all 329 general tests using these fixtures would fail with 403 if `conftest.py` does not explicitly set `must_change_password=False`. |

---

## 5-Component Handoff Report

### 1. Observation
1. **R1 Backend Code Locations:**
   - In `app/services/security/auth_service.py` (lines 80–92):
     ```python
     role_str = account.role.value if hasattr(account.role, "value") else str(account.role)
     if role_str in ["STUDENT", UserRole.STUDENT] and not is_apk:
         dev_bypass = (
             request.headers.get("x-lockxam-dev-bypass") == "true"
             or os.getenv("COOKIE_SECURE", "true") == "false"
         )
         if not dev_bypass:
             raise PermissionException(
                 "Akun siswa hanya dapat diakses melalui aplikasi resmi Lockxam APK. "
                 "Silakan gunakan aplikasi Android Lockxam."
             )
     ```
   - In `app/services/security/auth_service.py` (lines 104–106):
     ```python
     if (has_checkin or has_active_exam) and os.getenv(
         "COOKIE_SECURE", "true"
     ) != "false":
         raise PermissionException(...)
     ```
2. **R1 Frontend Code Locations:**
   - In `frontend/src/components/ui/LockxamAppGuard.tsx` (lines 14, 26–42, 124–137, 167–187):
     - Line 14: `const [devBypass, setDevBypass] = useState<boolean>(false);`
     - Line 26: `const bypass = sessionStorage.getItem("lockxam_dev_bypass") === "true";`
     - Lines 38–42: `const handleEnableDevBypass = () => { sessionStorage.setItem("lockxam_dev_bypass", "true"); ... };`
     - Lines 124–137: UI card button labeled "Aktifkan Mode Simulasi App".
     - Lines 167–187: Banner showing "Mode Simulasi Lockxam App (Dev Bypass)" with deactivate button.
   - Ripgrep confirmed NO OTHER occurrence of `x-lockxam-dev-bypass` or `lockxam_dev_bypass` exists in the entire workspace.
3. **R2 Backend Code Locations:**
   - Model `app/models/security/auth_account.py` (line 34):
     `must_change_password: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")`
   - Account provisioning sets `must_change_password=True` in `school_service.py:82, 342`, `staff_service.py:170, 299, 508`, and `student_service.py:106, 292, 615`.
   - Dependency funnel `app/core/dependencies.py` (`get_current_user`) at lines 20–98 handles authentication for ALL protected endpoints, but currently does NOT inspect `must_change_password`.
   - Role checkers in `app/core/rbac.py` (`require_role`) wrap `get_current_user` and also do not inspect `must_change_password`.
4. **Current Test Suite Baseline:**
   - Running `$env:PYTHONPATH="."; .venv\Scripts\pytest -q` executed **331 tests**: **329 passed, 2 failed** in 44.05s.
   - The 2 failing tests are:
     1. `tests/test_rc_security_v7.py::test_aes_gcm_crypto_round_trip`: `cryptography` library is missing from `.venv`, triggering fallback PBKDF2 stream cipher in `crypto.py` which emits prefix `enc:` instead of `enc:gcm:`.
     2. `tests/test_school.py::test_school_api_rbac`: `test_teacher` with `school_id=1` is prevented from reading school profile of a newly created school (`school_id=2`) by the multi-tenant isolation check in `app/api/school.py:126-130`.
   - Frontend build (`npm run build` in `frontend/`) passed with **0 errors** in 1.44s.

### 2. Logic Chain
1. **R1 Elimination Mechanism:**
   - In `auth_service.py:83-87`, removing `dev_bypass = (...)` and unconditionally raising `PermissionException(...)` when `role_str in ["STUDENT", UserRole.STUDENT] and not is_apk` guarantees that student login via standard browser, or with `x-lockxam-dev-bypass: true`, or with `COOKIE_SECURE=false` immediately aborts with HTTP 403 Forbidden.
   - In `auth_service.py:104-106`, removing `and os.getenv("COOKIE_SECURE", "true") != "false"` prevents single-device binding bypass in local or dev environments.
   - In `LockxamAppGuard.tsx`, removing `devBypass` state, `handleEnableDevBypass`, developer bypass button, and simulation banner ensures that `isCustomApp` can ONLY be set by authentic client indicators (`LockxamBrowser`, `EquigradeApp`, or `isLockxamApp === true`).
   - In `app/core/rbac.py` (or `app/api/exam.py`), adding an APK validation check for student role requests ensures that non-APK access to student endpoints also fails closed with HTTP 403 Forbidden.
2. **R2 Mandatory Dependency Enforcement Mechanism:**
   - Because `get_current_user` in `app/core/dependencies.py` is the single bottleneck for all authenticated requests across the system, inspecting `must_change_password` there guarantees 100% route coverage without modifying every route handler individually.
   - When `must_change_password` is True on `AuthAccount`, the dependency verifies `request.url.path`.
   - The authorized exempt paths are strictly:
     - Ending with `/auth/change-password`
     - Ending with `/auth/logout`
     - Ending with `/auth/me`
   - All other paths (including `/auth/sessions`, `/auth/logout-all`, and all domain APIs: schools, teachers, students, exams, AI, academic years, classes, licenses) raise `PermissionException(...)`, resulting in HTTP 403 Forbidden.
3. **Fixture Coherence:**
   - Because `AuthAccount.must_change_password` defaults to `True` at the SQLAlchemy column definition level, fixtures in `tests/conftest.py` (`test_superadmin` and `test_teacher`) must explicitly specify `must_change_password=False` so that the 329 existing tests representing regular operational workflows continue to pass without regression.

### 3. Caveats
- No implementation code was altered during this survey turn (read-only per specification miner contract).
- The 2 pre-existing test failures (`test_aes_gcm_crypto_round_trip` and `test_school_api_rbac`) are independent of R1/R2 and stem from environment packaging (`cryptography` package in `.venv`) and tenant isolation assertions in `test_school.py`.
- Endpoints under `/api/v1/exam/commands` use `X-Internal-Token` (service-to-service) and `/api/v1/exam/ai/callback` uses HMAC signatures (`X-AI-Signature`), so they are not user-session endpoints and do not use `get_current_user`.

### 4. Conclusion
- The R1 bypasses (`x-lockxam-dev-bypass`, `lockxam_dev_bypass`, and `COOKIE_SECURE=false`) are fully mapped to exact lines in `app/services/security/auth_service.py` and `frontend/src/components/ui/LockxamAppGuard.tsx`.
- The R2 forced password change enforcement can be cleanly and authoritatively implemented within `app/core/dependencies.py` (`get_current_user`) using path allowlisting (`/auth/change-password`, `/auth/logout`, `/auth/me`), ensuring all other endpoints return HTTP 403 Forbidden.
- Detailed test cases for `tests/test_regression_r1.py` and `tests/test_regression_r2.py` have been designed to lock in regression testing.

### 5. Verification Method
- **Verify R1 in Backend:**
  Run `$env:PYTHONPATH="."; .venv\Scripts\pytest tests/test_regression_r1.py -v`.
  Verify `x-lockxam-dev-bypass` and `COOKIE_SECURE=false` student logins return HTTP 403.
- **Verify R1 in Frontend:**
  Search workspace for occurrences:
  `git grep "x-lockxam-dev-bypass"` and `git grep "lockxam_dev_bypass"`. Both must return 0 results.
  Run `npm run build` in `frontend/` to confirm clean compilation.
- **Verify R2 in Backend:**
  Run `$env:PYTHONPATH="."; .venv\Scripts\pytest tests/test_regression_r2.py -v`.
  Verify users with `must_change_password=True` receive HTTP 403 on application endpoints and HTTP 200/204 on `/auth/change-password`, `/auth/logout`, and `/auth/me`.
- **Verify Full Regression Suite:**
  Run `$env:PYTHONPATH="."; .venv\Scripts\pytest -q` to ensure all 331+ tests run without introducing regressions.
