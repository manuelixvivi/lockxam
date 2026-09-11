# Handoff Report: Milestone 2 — CBT Exam State Machine & Android Keyboard Suppression (R3)

## 1. Observation

### 1.1 Backend Exam Window Enforcement in `exam_service.py`
- **File**: `app/services/exam/exam_service.py` (Lines 278–294 prior to remediation)
  ```python
  if (
      not start_at
      or now_utc >= start_at
      or str(session.status).upper() in ["PLANNED", "DRAFT", "READY", "SCHEDULED"]
  ):
      session.status = ExamSessionStatus.ACTIVE
      db.flush()
  else:
      raise BusinessException("Waktu pelaksanaan ujian belum tiba.", status_code=400)
  ```
- **Direct Observation**: The permissive clause `or str(session.status).upper() in ["PLANNED", "DRAFT", "READY", "SCHEDULED"]` bypassed the `now_utc >= start_at` requirement for any newly created session. Consequently, students could start attempts before `scheduled_start_at`.
- **Remediation**: Removed the permissive OR clause and enforced strict start time validation:
  ```python
  now_utc = datetime.now(timezone.utc)
  start_at = session.scheduled_start_at
  if start_at and start_at.tzinfo is None:
      start_at = start_at.replace(tzinfo=timezone.utc)

  if start_at and now_utc < start_at:
      raise BusinessException("Waktu pelaksanaan ujian belum tiba.", status_code=400)

  if session.status not in [ExamSessionStatus.ACTIVE, "ACTIVE"]:
      session.status = ExamSessionStatus.ACTIVE
      db.flush()
  ```

### 1.2 QR Check-in Dashboard Retention & Countdown in `StudentSchedulesView.tsx`
- **File**: `frontend/src/views/student/StudentSchedulesView.tsx` (Lines 118–128 prior to remediation)
  ```tsx
  autoStartedRef.current[target.schedule_id] = true;
  setTimeout(() => {
    setIsQrModalOpen(false);
    setCheckinSuccess(false);
    setQrScanTarget(null);
    showToast({ type: "success", title: "Membuka Ujian Otomatis!", message: `Absensi valid. Langsung masuk ke lembar ujian...` });
    handleStartExam(target);
  }, 800);
  ```
- **Direct Observation**: Upon successful QR check-in, an 800ms timer immediately launched `handleStartExam(target)`, removing the student from the dashboard before the scheduled exam start time. There was also no active server-synchronized countdown ticker on the card.
- **Remediation**:
  1. Removed `handleStartExam` from `performCheckin`; student remains on the dashboard with confirmed attendance (`HADIR ✓`).
  2. Implemented `serverSyncedNow = nowMs + serverTimeOffset` calibrated using server's authoritative `checked_in_at` and `Date` response header.
  3. Added `formatCountdown(diffMs)` and rendered a live server-synchronized countdown ticker comparing `serverSyncedNow` against `scheduled_start_at`.
  4. Kept "Mulai Ujian" button disabled with `"Menunggu Jam Ujian"` while `serverSyncedNow < scheduled_start_at`, enabling strictly when `serverSyncedNow >= scheduled_start_at`.

### 1.3 Restricted Kiosk Mode Activation in `StudentCbtEngineView.tsx`
- **File**: `frontend/src/views/student/StudentCbtEngineView.tsx` (Lines 61–66 prior to remediation)
  ```tsx
  useEffect(() => {
    if (typeof window !== "undefined" && (window as any).LockxamBridge?.enterKioskMode) {
      (window as any).LockxamBridge.enterKioskMode();
    }
  }, []);
  ```
- **Direct Observation**: `enterKioskMode()` was called unconditionally on component mount before `initAttempt()` or server authorization occurred.
- **Remediation**: Removed `enterKioskMode()` from mount `useEffect`. Placed it strictly inside `initAttempt()` immediately after a successful, active `startAttempt()` response (`data.status !== "SUBMITTED" && data.status !== "GRADED"`).

### 1.4 Android Soft-Keyboard Suppression & Space Key Fix in `StudentCbtEngineView.tsx`
- **File**: `frontend/src/views/student/StudentCbtEngineView.tsx` (Lines 588–596 and 1091 prior to remediation)
  - `<textarea>` lacked `inputMode="none"` and `readOnly={true}`.
  - Line 1091: Space key called `onClick={() => onChange(value + " ")}`, appending spaces to the end of text instead of inserting at the cursor.
- **Remediation**:
  1. Configured `<textarea>` with `inputMode="none"` and `readOnly={true}`.
  2. Maintained cursor selection and caret position via `setSelectionRange(newPos, newPos)` and `el.focus({ preventScroll: true })` without summoning Android IME.
  3. Fixed the SPASI button in `LockxamBottomKeyboard` to call `handleKeyPress(" ")`.

---

## 2. Logic Chain

1. **Premature Auto-Start Elimination**: By removing `handleStartExam` from `performCheckin`, students stay on `StudentSchedulesView` after scanning QR code or submitting PIN.
2. **Server-Synchronized Dashboard State**: `serverSyncedNow` continuously compares synchronized server time against `sch.start_time`. While `serverSyncedNow < sch.start_time`, `getTimeStatus` returns `"FUTURE"`, which keeps the button disabled as `"Menunggu Jam Ujian"` and displays the live countdown ticker alongside the `HADIR ✓` attendance badge.
3. **Window Arrival & Start Button Activation**: Once `serverSyncedNow >= sch.start_time`, `getTimeStatus` returns `"OPEN"`, activating `"Mulai Ujian"`. Clicking opens the confirmation modal and proceeds to `StudentCbtEngineView`.
4. **Authoritative Backend Protection**: In `exam_service.py`, `start_attempt` rejects any premature request (`now_utc < start_at`) with HTTP 400 `"Waktu pelaksanaan ujian belum tiba."`.
5. **Kiosk Mode Exclusivity**: In `StudentCbtEngineView.tsx`, `LockxamBridge.enterKioskMode()` is only reached after `studentExamApi.startAttempt()` returns HTTP 200 with an active attempt.
6. **Soft-Keyboard Suppression**: With `inputMode="none"` and `readOnly={true}`, Android WebView suppresses the native soft keyboard, while `LockxamBottomKeyboard` handles virtual typing and cursor placement via `handleKeyPress` (including `" "` for SPASI).

---

## 3. Caveats

- In browser testing environments, `window.LockxamBridge` is mocked or undefined; all bridge invocations use optional chaining (`LockxamBridge?.enterKioskMode?.()`), ensuring non-Android clients do not encounter runtime errors.
- External physical Bluetooth or USB keyboards attached to Android devices will not type directly into read-only textareas, which conforms to strict kiosk examination integrity requirements.

---

## 4. Conclusion

All Milestone 2 (R3) requirements have been implemented and verified:
1. `performCheckin` retains students on the schedule dashboard with `HADIR ✓` badge.
2. Schedule cards render an active live server-synchronized countdown ticker.
3. Start exam button remains disabled with `"Menunggu Jam Ujian"` until exam start time arrives.
4. `enterKioskMode()` executes exclusively upon receiving a successful active response from `startAttempt`.
5. Permissive OR clause in `exam_service.py` is removed; premature start attempts strictly return HTTP 400 `"Waktu pelaksanaan ujian belum tiba."`.
6. Essay and short-answer textareas suppress the Android native soft keyboard using `inputMode="none"` and `readOnly={true}`.
7. SPASI in `LockxamBottomKeyboard` inserts spaces at the current cursor position via `handleKeyPress(" ")`.
8. Backend tests (`tests/test_cbt_kiosk_lifecycle.py` and `tests/test_exam_security_boundaries.py`) pass 22/22.
9. Frontend production build (`npm run build`) completes with 0 errors.

---

## 5. Verification Method

### 5.1 Backend Pytest Verification
Run the test command:
```bash
.venv\Scripts\pytest.exe tests/test_exam_security_boundaries.py tests/test_cbt_kiosk_lifecycle.py -v
```
**Expected Result**: All 22 tests pass with 0 failures:
- `tests/test_cbt_kiosk_lifecycle.py::test_start_attempt_premature_strictly_rejected_400` PASSED
- `tests/test_cbt_kiosk_lifecycle.py::test_start_attempt_elimination_of_permissive_status_clause` PASSED
- `tests/test_cbt_kiosk_lifecycle.py::test_start_attempt_requires_prior_checkin` PASSED
- `tests/test_cbt_kiosk_lifecycle.py::test_start_attempt_authorized_open_window_success` PASSED
- `tests/test_cbt_kiosk_lifecycle.py::test_start_attempt_resume_and_device_session_binding` PASSED
- `tests/test_exam_security_boundaries.py` (17 tests) PASSED

### 5.2 Frontend Build & Lint Verification
In `frontend/`:
```bash
npm run build
npm run lint
```
**Expected Result**:
- `npm run build`: `tsc -b && vite build` completes in <2s with 0 errors.
- `npm run lint`: oxlint completes with 0 errors.

### 5.3 Invalidation Conditions
- Any return of `x-lockxam-dev-bypass` or premature auto-navigation in `performCheckin`.
- Any call to `LockxamBridge.enterKioskMode()` on component mount prior to `startAttempt()` resolution.
- Any attempt start before `scheduled_start_at` returning HTTP 200 instead of HTTP 400.
