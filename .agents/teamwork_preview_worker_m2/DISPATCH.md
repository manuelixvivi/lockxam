# Task Assignment: Milestone 2 - CBT Exam State Machine & Android Keyboard Suppression (R3)

- Working Directory: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_worker_m2
- Workspace Root: C:\Users\irul2\Downloads\Equigrade_x_Lockxam
- Authoritative Request File: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\ORIGINAL_REQUEST.md
- Project Scope: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\PROJECT.md
- Survey Handoff: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_spec_miner_survey_2\handoff.md

## Exclusive Write Ownership
You exclusively own and may edit:
- `frontend/src/views/student/StudentSchedulesView.tsx`
- `frontend/src/views/student/StudentCbtEngineView.tsx`
- `app/services/exam/exam_service.py`
- `tests/test_cbt_kiosk_lifecycle.py` (new test file)

DO NOT edit files owned by other milestones.

## Implementation Scope
1. **QR Check-in Lifecycle & Dashboard Retention**:
   - In `frontend/src/views/student/StudentSchedulesView.tsx`:
     - Remove the 800ms auto-start timeout (`handleStartExam(target)`) in `performCheckin`.
     - Upon successful check-in, keep the student on the schedule screen with confirmed attendance badge (`HADIR ✓`).
     - Render an active live server-synchronized countdown ticker comparing current time to `scheduled_start_at`.
     - While `serverSyncedNow < scheduled_start_at`, keep the exam button disabled with `"Menunggu Jam Ujian"`. Enable `"Mulai Ujian"` strictly when the exam start time arrives.

2. **Restricted Kiosk Mode Activation**:
   - In `frontend/src/views/student/StudentCbtEngineView.tsx`:
     - Remove `LockxamBridge.enterKioskMode()` from the mount `useEffect` (lines 61-66).
     - Move `(window as any).LockxamBridge?.enterKioskMode?.()` into `initAttempt()`, executed strictly and exclusively upon receiving a successful active response from `studentExamApi.startAttempt(schedule.session_id)`.

3. **Backend Exam Window Start Enforcement**:
   - In `app/services/exam/exam_service.py`:
     - In `start_attempt` (lines 280-295), remove the permissive `or str(session.status).upper() in ["PLANNED", "DRAFT", "READY", "SCHEDULED"]` clause.
     - Strictly enforce that if `now_utc < start_at`, raise `BusinessException("Waktu pelaksanaan ujian belum tiba.", status_code=400)`.

4. **Android Native Soft-Keyboard Suppression**:
   - In `frontend/src/views/student/StudentCbtEngineView.tsx`:
     - In essay and short-answer questions ("IS" and "ES"), configure `<textarea>` with `inputMode="none"` and `readOnly={true}`.
     - Handle focus/selection so that tapping the textarea reveals the Lockxam virtual keypad without triggering Android IME soft-keyboard popups.
     - In `LockxamBottomKeyboard`, ensure cursor selection is maintained via `textareaRef.current.setSelectionRange(newPos, newPos)` without summoning native IME.
     - Fix the SPASI (Space) button in `LockxamBottomKeyboard` to call `handleKeyPress(" ")` instead of appending `value + " "` to the end.

5. **Mandatory Integrity Warning**:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Verification
- Run backend tests: `.venv\Scripts\pytest.exe tests/test_exam_security_boundaries.py tests/test_cbt_kiosk_lifecycle.py -v`
- Run frontend build: `npm run build` in `frontend/` (0 errors)
- Document all changes and verification output in `C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_worker_m2\handoff.md`.

## 2026-09-11T02:37:18Z
You are teamwork_preview_worker_m2.
Your working directory is: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_worker_m2
The workspace root is: C:\Users\irul2\Downloads\Equigrade_x_Lockxam
The authoritative request file is: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\ORIGINAL_REQUEST.md

You MUST read C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\ORIGINAL_REQUEST.md before starting work.
Also read C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\PROJECT.md and C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_worker_m2\DISPATCH.md.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your mission:
Implement Milestone 2 (CBT Exam State Machine & Android Keyboard Suppression R3):
- In StudentSchedulesView.tsx: Remove 800ms auto-start timeout from performCheckin; keep student on dashboard with confirmed attendance badge (HADIR ✓) and live server-synchronized countdown ticker; disable start exam button until exam start time arrives.
- In StudentCbtEngineView.tsx: Remove LockxamBridge.enterKioskMode() from mount useEffect; invoke enterKioskMode() exclusively in initAttempt() upon receiving successful active response from studentExamApi.startAttempt(); add inputMode="none" and readOnly={true} to essay/short-answer <textarea>; preserve cursor selection; fix SPASI in LockxamBottomKeyboard to call handleKeyPress(" ").
- In app/services/exam/exam_service.py: Remove permissive OR clause in line 288 (str(session.status).upper() in ["PLANNED", ...]); strictly raise BusinessException("Waktu pelaksanaan ujian belum tiba.", status_code=400) if now_utc < start_at.
- Write tests in tests/test_cbt_kiosk_lifecycle.py and run: .venv\Scripts\pytest.exe tests/test_exam_security_boundaries.py tests/test_cbt_kiosk_lifecycle.py -v.
- Run npm run build in frontend/ to confirm 0 errors.
- Write handoff report to C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_worker_m2\handoff.md and notify orchestrator via send_message.
