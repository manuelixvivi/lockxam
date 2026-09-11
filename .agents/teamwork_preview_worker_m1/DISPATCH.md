# Task Assignment: Milestone 1 - Auth & Security Bypass Remediation (R1, R2)

- Working Directory: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_worker_m1
- Workspace Root: C:\Users\irul2\Downloads\Equigrade_x_Lockxam
- Authoritative Request File: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\ORIGINAL_REQUEST.md
- Project Scope: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\PROJECT.md
- Survey Handoff: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_spec_miner_survey_1\handoff.md

## Exclusive Write Ownership
You exclusively own and may edit:
- `app/services/security/auth_service.py`
- `app/core/dependencies.py`
- `frontend/src/components/ui/LockxamAppGuard.tsx`
- `tests/conftest.py`
- `tests/test_regression_r1.py` (new test file)
- `tests/test_regression_r2.py` (new test file)

DO NOT edit files owned by other milestones.

## Implementation Scope
1. **R1: Absolute Elimination of Student Browser Bypass**:
   - In `app/services/security/auth_service.py`:
     - Completely eliminate `x-lockxam-dev-bypass`, `lockxam_dev_bypass`, and `COOKIE_SECURE=false` student bypass conditions (lines 80-92, 104-106).
     - Ensure any student login request from a non-APK client unconditionally raises `PermissionException("Akun siswa hanya dapat diakses melalui aplikasi resmi Lockxam APK. Silakan gunakan aplikasi Android Lockxam.")` resulting in HTTP 403.
     - Single-device binding check must be unconditional (no `COOKIE_SECURE` bypass).
   - In `frontend/src/components/ui/LockxamAppGuard.tsx`:
     - Completely remove `devBypass` state, `handleEnableDevBypass`, developer bypass button, and simulation banner.
     - Ensure no occurrences of `x-lockxam-dev-bypass` or `lockxam_dev_bypass` remain anywhere in backend or frontend.
   - Trace student endpoints to ensure unauthenticated or non-APK student requests fail closed with HTTP 403 Forbidden.

2. **R2: Backend Enforcement of Forced Password Change**:
   - In `app/core/dependencies.py` (`get_current_user`):
     - Check if `account.must_change_password` is True.
     - Strictly enforce that if `must_change_password=True`, the request path is checked:
       - Allowed paths: `/api/v1/auth/change-password` (or paths ending with `/auth/change-password`), `/auth/logout`, and `/auth/me`.
       - All other paths (exams, students, teachers, schools, sessions, etc.) must raise `PermissionException("Harap ubah kata sandi Anda sebelum melanjutkan.", status_code=403)`.
   - In `tests/conftest.py`:
     - Update fixtures (`test_superadmin`, `test_teacher`) to explicitly set `must_change_password=False` on the created `AuthAccount` records so existing test flows are not broken.
   - Create `tests/test_regression_r1.py` and `tests/test_regression_r2.py`:
     - Verify R1 bypass elimination (header, query, cookie).
     - Verify R2 forced password lockdown (all non-exempt endpoints return 403; change-password, logout, me return 200/204).

3. **Mandatory Integrity Warning**:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Verification
- Run tests: `.venv\Scripts\pytest.exe tests/test_regression_r1.py tests/test_regression_r2.py -v`
- Run full pytest suite: `.venv\Scripts\pytest.exe -q`
- Search for `x-lockxam-dev-bypass` and `lockxam_dev_bypass` across workspace (must be 0 matches).
- Document all changes and test outputs in `C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_worker_m1\handoff.md`.

## 2026-09-11T02:20:44Z
You are teamwork_preview_worker_m1.
Your working directory is: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_worker_m1
The workspace root is: C:\Users\irul2\Downloads\Equigrade_x_Lockxam
The authoritative request file is: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\ORIGINAL_REQUEST.md

You MUST read C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\ORIGINAL_REQUEST.md before starting work.
Also read C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\PROJECT.md and C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_worker_m1\DISPATCH.md.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your mission:
Implement Milestone 1 (Auth & Security Bypass Remediation R1, R2):
- Eliminate x-lockxam-dev-bypass, lockxam_dev_bypass, and COOKIE_SECURE=false student bypasses across backend (auth_service.py) and frontend (LockxamAppGuard.tsx).
- Enforce must_change_password via FastAPI dependency in app/core/dependencies.py, blocking all endpoints (HTTP 403) except /auth/change-password, /auth/logout, and /auth/me.
- Update tests/conftest.py so test accounts set must_change_password=False, and write comprehensive regression tests in tests/test_regression_r1.py and tests/test_regression_r2.py.
- Run tests: .venv\Scripts\pytest.exe tests/test_regression_r1.py tests/test_regression_r2.py -v.
- Write handoff report to C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_worker_m1\handoff.md and report back via send_message.

