# Task Assignment: Survey - Auth & Security (R1 & R2)

- Working Directory: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_spec_miner_survey_1
- Workspace Root: C:\Users\irul2\Downloads\Equigrade_x_Lockxam
- Original Request File: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\ORIGINAL_REQUEST.md

## Assignment Details
Read C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\ORIGINAL_REQUEST.md thoroughly.
Conduct a deep, read-only investigation of:
1. R1: Absolute Elimination of Student Browser Bypass:
   - Identify all occurrences of `x-lockxam-dev-bypass`, `lockxam_dev_bypass`, and `COOKIE_SECURE=false` in backend (`auth_service.py`, middleware, dependencies) and frontend (`LockxamAppGuard.tsx`, `LoginView`, etc.).
   - Trace all student authentication and authorization paths to ensure non-APK or unauthenticated student requests fail closed with HTTP 403 Forbidden.
2. R2: Backend Enforcement of Forced Password Change:
   - Identify how `must_change_password` is currently stored, checked, or bypassed.
   - Design/locate the mandatory FastAPI authorization dependency to enforce HTTP 403 on all endpoints EXCEPT `/auth/change-password`, `/auth/logout`, and `/auth/me`.
   - Identify existing backend test coverage and what test cases are needed.

Write your findings to `C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_spec_miner_survey_1\handoff.md` and report back.

## 2026-09-11T02:12:33Z
You are teamwork_preview_spec_miner_survey_1.
Your working directory is: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_spec_miner_survey_1
The workspace root is: C:\Users\irul2\Downloads\Equigrade_x_Lockxam
The authoritative request file is: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\ORIGINAL_REQUEST.md

Your mission:
Survey and investigate R1 and R2 across backend and frontend codebases:
1. R1: Absolute Elimination of Student Browser Bypass
   - Search for every occurrence of `x-lockxam-dev-bypass`, `lockxam_dev_bypass`, and `COOKIE_SECURE=false` bypass across backend authentication (`auth_service.py`, middleware, dependencies) and frontend guards (`LockxamAppGuard.tsx`, `LoginView`, api client, etc.).
   - Trace unauthenticated and non-APK student requests to confirm they fail closed with HTTP 403 Forbidden.
2. R2: Backend Enforcement of Forced Password Change
   - Investigate how `must_change_password` is implemented in user models, auth flows, and FastAPI dependencies.
   - Trace all application endpoints that must be protected, ensuring that users with `must_change_password=True` are blocked (HTTP 403) from all endpoints EXCEPT `/auth/change-password`, `/auth/logout`, and `/auth/me`.
   - Identify existing tests and test files covering auth, permissions, and bypass rejection.

You are a read-only spec miner. Do NOT write or modify implementation code.
Write your detailed report to C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_spec_miner_survey_1\handoff.md.
When complete, notify the orchestrator via send_message with your summary and handoff path.
