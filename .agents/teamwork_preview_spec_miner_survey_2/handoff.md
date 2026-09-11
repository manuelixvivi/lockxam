# Handoff Report: R3 — CBT Exam State Machine & Android Keyboard Suppression

## 1. Observation

### 1.1 Kiosk Lifecycle & `enterKioskMode()` Invocation
- **File**: `frontend/src/views/student/StudentCbtEngineView.tsx` (Lines 61–66)
  ```tsx
  // 1. Initialize Exam Attempt & Android Native Kiosk Mode
  useEffect(() => {
    if (typeof window !== "undefined" && (window as any).LockxamBridge?.enterKioskMode) {
      (window as any).LockxamBridge.enterKioskMode();
    }
  }, []);
  ```
  **Direct Observation**: `enterKioskMode()` is currently invoked unconditionally inside a mount `useEffect` on line 63 when `StudentCbtEngineView` renders. This occurs *prior* to `initAttempt()` calling `studentExamApi.startAttempt(schedule.session_id)`, and executes even if `start_attempt` fails (e.g., HTTP 400 "Waktu pelaksanaan ujian belum tiba", HTTP 403, or network outage).
- **File**: `frontend/src/views/student/StudentCbtEngineView.tsx` (Lines 68–77)
  ```tsx
  const initAttempt = async () => {
    setIsLoading(true);
    try {
      if (!schedule.session_id) {
        throw new Error("Sesi ujian belum dikonfirmasi oleh pengawas.");
      }
      const data = await studentExamApi.startAttempt(schedule.session_id);
      setAttempt(data);
      if (data.status === "SUBMITTED" || data.status === "GRADED") {
        setIsCompleted(true);
        setIsLoading(false);
        return;
      }
  ```
- **File**: `frontend/src/views/student/StudentSchedulesView.tsx` (Lines 353–356)
  ```tsx
  useEffect(() => {
    (window as any).LockxamBridge?.exitKioskMode?.();
    loadData();
  }, []);
  ```
  On schedule screen mount, `exitKioskMode()` is invoked to release native locks.

### 1.2 QR Check-in Flow & Premature Auto-Start Bug
- **File**: `frontend/src/views/student/StudentSchedulesView.tsx` (Lines 104–135)
  ```tsx
  const performCheckin = useCallback(async (token: string) => {
    const clean = token.trim();
    if (!clean || checkinLoadingRef.current) return;
    checkinLoadingRef.current = true;
    try {
      const result = await studentExamApi.checkin(clean, qrScanTarget?.schedule_id);
      setCheckinSuccess(true);
      showToast({ type: "success", title: "Absensi Berhasil!", message: `Kamu terdaftar untuk "${result.schedule_title}".` });
      const updatedData = await studentExamApi.getMySchedules();
      setSchedules(updatedData);

      const target = updatedData.find((s) => String(s.schedule_id) === String(result.schedule_id)) || qrScanTarget;
      if (
        target &&
        !["SUBMITTED", "GRADED", "GRADING", "CANCELLED"].includes(target.attempt_status)
      ) {
        autoStartedRef.current[target.schedule_id] = true;
        setTimeout(() => {
          setIsQrModalOpen(false);
          setCheckinSuccess(false);
          setQrScanTarget(null);
          showToast({ type: "success", title: "Membuka Ujian Otomatis!", message: `Absensi valid. Langsung masuk ke lembar ujian...` });
          handleStartExam(target);
        }, 800);
      } else {
        setTimeout(() => { setIsQrModalOpen(false); setCheckinSuccess(false); setQrScanTarget(null); }, 2000);
      }
  ```
  **Direct Observation**: As soon as QR check-in succeeds, `performCheckin` registers `autoStartedRef.current[target.schedule_id] = true` and after 800ms directly executes `handleStartExam(target)`. This forces the student *off* the dashboard and into `StudentCbtEngineView`, which subsequently immediately fires `enterKioskMode()`. This violates Requirement R3: *"Completing QR check-in leaves the student on the schedule screen showing an active countdown without entering kiosk mode."*
- **Schedule Card & Countdown State**:
  - In `StudentSchedulesView.tsx` (Lines 681–752), if `sch.has_checked_in` is true and the schedule is `FUTURE`, the card displays a badge `HADIR ✓`, but there is **no active live countdown ticker** rendered on the card.
  - The start button on Line 743 is disabled with `<Clock className="w-3.5 h-3.5" /> Menunggu Jam Ujian`.
  - Time comparison in `getTimeStatus` (Lines 97–102) evaluates `Date.now() < new Date(start).getTime()`, relying on uncorrected client system time rather than server-synchronized time.

### 1.3 Server-Side Exam Window Enforcement in `start_attempt`
- **File**: `app/services/exam/exam_service.py` (Lines 278–294)
  ```python
  # Auto-activate session if start time has arrived or session was PLANNED / DRAFT
  if session.status not in [ExamSessionStatus.ACTIVE, "ACTIVE"]:
      now_utc = datetime.now(timezone.utc)
      start_at = session.scheduled_start_at
      if start_at and start_at.tzinfo is None:
          start_at = start_at.replace(tzinfo=timezone.utc)

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
  **Direct Observation**: Line 288 includes `or str(session.status).upper() in ["PLANNED", "DRAFT", "READY", "SCHEDULED"]`. Because initial sessions are created in `PLANNED` status, this `or` clause causes the condition to evaluate to `True` even when `now_utc < start_at`. This prevents the `else` clause from raising HTTP 400 `"Waktu pelaksanaan ujian belum tiba."`, allowing premature attempt creation before the exam window opens.

### 1.4 Android Soft-Keyboard In CBT Essay and Short-Answer Questions
- **File**: `frontend/src/views/student/StudentCbtEngineView.tsx` (Lines 421, 570–609, 669–688)
  - Text question identification:
    `const isTextQuestion = currentQuestion.question_type === "IS" || currentQuestion.question_type === "ES";`
  - Input component:
    ```tsx
    <textarea
      ref={textareaRef}
      value={currentAnswer.text_answer || ""}
      onChange={(e) => saveAnswer(currentQuestion.question_id, undefined, e.target.value)}
      onFocus={() => setIsKeyboardVisible(true)}
      onClick={() => setIsKeyboardVisible(true)}
      placeholder="Ketik jawaban Anda di sini, atau sisipkan foto lembar jawaban kertas Anda..."
      className="w-full min-h-[100px] bg-slate-950 border border-slate-800 rounded-xl p-3.5 text-xs sm:text-sm text-slate-100 focus:border-indigo-500 focus:outline-none transition-colors font-mono resize-y"
      rows={4}
    />
    ```
  - Virtual Keyboard integration:
    ```tsx
    <LockxamBottomKeyboard
      value={currentAnswer.text_answer || ""}
      textareaRef={textareaRef}
      onChange={(newVal, newPos) => {
        saveAnswer(currentQuestion.question_id, undefined, newVal);
        if (newPos !== undefined && textareaRef.current) {
          const el = textareaRef.current;
          setTimeout(() => {
            el.setSelectionRange(newPos, newPos);
            el.focus();
          }, 0);
        }
      }}
      onClose={() => setIsKeyboardVisible(false)}
    />
    ```
- **Mechanisms Causing Native Keyboard Popups**:
  1. `<textarea>` lacks `inputMode="none"`. On mobile Chrome / Android WebView, tapping or focusing the textarea prompts the Android Input Method Editor (IME) soft-keyboard to emerge.
  2. `<textarea>` is not `readOnly`.
  3. Every key press on `LockxamBottomKeyboard` fires `onChange` which triggers `el.focus()` (Line 680). In the absence of `inputMode="none"` and `readOnly` handling, calling `el.focus()` explicitly commands Android to summon the native keyboard on every single virtual keystroke.
  4. In `LockxamBottomKeyboard` (Line 1091), the SPASI (Space) button calls `onClick={() => onChange(value + " ")}`. Unlike character keys, backspace, and enter, Space ignores cursor position (`textarea.selectionStart`) and appends to the end of the text.

### 1.5 Attempt State Models & Endpoints
- **Models**:
  - `ExamAttempt` (`app/models/exam/exam_attempt.py`): Primary attempt model with statuses `NOT_STARTED`, `IN_PROGRESS`, `PAUSED`, `SUBMITTED`, `GRADING`, `GRADED`.
  - `StudentAnswer` (`app/models/exam/student_answer.py`): Stores `selected_option` (for "PG") and `text_answer` (for "IS" and "ES").
  - `DeviceSession` (`app/models/exam/device_session.py`): Stores active device session token with unique partial index `uq_active_device_per_attempt`.
  - `ExamCheckin` (`app/models/exam/exam_checkin.py`): Records check-in per schedule and student with `checked_in_at`.
- **Endpoints**:
  - `GET /api/v1/exam/my-schedules` (`app/api/exam.py:165`): Fetches student schedule list.
  - `POST /api/v1/exam/checkin` (`app/api/exam.py:458`): Validates QR token / PIN and upserts `ExamCheckin`.
  - `POST /api/v1/exam/sessions/{session_id}/start-attempt` (`app/api/exam.py:605`): Validates check-in, activates session, creates/resumes `ExamAttempt`.
  - `POST /api/v1/exam/attempts/{attempt_id}/autosave` (`app/api/exam.py:685`): Saves answer changes.
  - `POST /api/v1/exam/attempts/{attempt_id}/submit` (`app/api/exam.py:760`): Final attempt submission.

---

## 2. Logic Chain

1. **Premature Auto-Start & Kiosk Activation**:
   - In `performCheckin` (`StudentSchedulesView.tsx`), the callback unconditionally triggers `handleStartExam(target)` after 800ms.
   - When `handleStartExam` is called, `StudentCbtEngineView` is mounted.
   - In `StudentCbtEngineView`, line 63 executes `LockxamBridge.enterKioskMode()` inside `useEffect([], ...)`.
   - Consequently, the student enters kiosk mode immediately after check-in, bypassing the schedule dashboard and ignoring whether the exam start time has arrived.
   - If `startAttempt` subsequently fails (because the exam start time is in the future), the student is stuck in a locked kiosk screen with an error.

2. **Server Window Bypass in `start_attempt`**:
   - In `exam_service.py` line 288, checking `or str(session.status).upper() in ["PLANNED", "DRAFT", "READY", "SCHEDULED"]` short-circuits the start time check.
   - As a result, calling `start_attempt` before `session.scheduled_start_at` erroneously succeeds and promotes the session to `ACTIVE`.
   - Removing this permissive clause ensures that `now_utc < start_at` strictly raises `BusinessException("Waktu pelaksanaan ujian belum tiba.", status_code=400)`.

3. **Restricting `enterKioskMode()` Exclusively to Authorized Attempt Start**:
   - Eliminating the mount-time `useEffect` in `StudentCbtEngineView.tsx` stops premature locking.
   - Moving `LockxamBridge.enterKioskMode()` into `initAttempt()`, guarded by a successful response from `studentExamApi.startAttempt(schedule.session_id)` and status checking (`data.status !== "SUBMITTED" && data.status !== "GRADED"`), ensures that kiosk mode only activates after the server authorizes the attempt start.

4. **Preserving Dashboard State with Live Server-Synchronized Countdown**:
   - Removing the automatic `handleStartExam(target)` from `performCheckin` ensures the student stays on `StudentSchedulesView` after QR check-in.
   - The schedule card for the checked-in exam updates `has_checked_in = true` and `checked_in_at`.
   - A live countdown ticker can be rendered on the schedule card using a calculated offset between the server timestamp (from `/checkin` or HTTP `Date` header) and client `Date.now()`.
   - While `syncedNow < startTime`, the start button remains disabled with `"Menunggu Jam Ujian"`.
   - When `syncedNow >= startTime`, the button activates to `"Mulai Ujian"`, allowing authorized entry.

5. **Eliminating Native Soft-Keyboard Conflicts**:
   - Adding `inputMode="none"` to `<textarea>` signals the Android browser/WebView not to display the soft-keyboard when the element is focused.
   - Adding `readOnly={true}` prevents the OS from accepting native keyboard input or opening IME popups across all Android versions, while still allowing DOM selection and programmatic updates from `LockxamBottomKeyboard`.
   - When keys on `LockxamBottomKeyboard` are tapped, React state (`currentAnswer.text_answer`) updates programmatically, and `textareaRef.current.setSelectionRange(newPos, newPos)` maintains cursor position without triggering native IME.
   - Fixing `SPASI` in `LockxamBottomKeyboard` to use `handleKeyPress(" ")` ensures cursor-aware space insertion.

---

## 3. Features Discovered

## Features Discovered
| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | Kiosk Lifecycle | Schedule Screen Kiosk Release | Automatically exits Android Kiosk Mode when navigating to or viewing the student schedule list | Component mount | `LockxamBridge.exitKioskMode()` invoked | Silent no-op if bridge unavailable | `StudentSchedulesView.tsx:354` |
| 2 | Kiosk Lifecycle | Unconditional Engine Kiosk Lock | Enters Kiosk Mode immediately upon `StudentCbtEngineView` component mount before attempt creation | Component mount | `LockxamBridge.enterKioskMode()` invoked | Locks device even on start-attempt failure | `StudentCbtEngineView.tsx:63` |
| 3 | Attendance / QR | QR Check-in Submission | Student scans proctor QR code or submits 6-digit PIN to record attendance | `token`, `expected_schedule_id`, `X-Device-Id` header | `{ success, schedule_title, checked_in_at, start_time, end_time }` | 400 if invalid/expired token, 403 if ineligible | `StudentSchedulesView.tsx:109`, `app/api/exam.py:458` |
| 4 | Attendance / QR | Post-Check-in Auto-Start | Automatically triggers exam navigation 800ms after successful check-in | Successful check-in result | Navigation to `StudentCbtEngineView` | Bypasses dashboard countdown | `StudentSchedulesView.tsx:121` |
| 5 | Exam Engine | Start Attempt Authorization | Student initiates or resumes an exam attempt; binds single active device session | `session_id`, `X-Device-Id` header | `ExamAttemptResponse` with `questions`, `answers`, `device_session_token` | 400 if not checked in, 403 if ineligible, 404 if session missing | `app/api/exam.py:605`, `exam_service.py:263` |
| 6 | Exam Engine | Session Auto-Activation Permissiveness | Backend auto-activates planned/draft sessions on attempt start regardless of start time | `now_utc`, `scheduled_start_at`, `session.status` | `session.status = ACTIVE` | Permissive OR condition bypasses window check | `exam_service.py:288` |
| 7 | CBT Interface | Textarea Essay/Short-Answer Input | Interactive textarea for answering "IS" and "ES" question types | User touch/click, typing | Answer text update in React state | Missing `inputMode="none"` triggers native keyboard | `StudentCbtEngineView.tsx:588` |
| 8 | CBT Interface | Lockxam Programmatic Keypad | Fixed bottom virtual keyboard supporting ABC, 123, and SYM modes with cursor tracking | Virtual key taps, selection range | New string value and cursor position | Keystroke focus commands trigger native Android IME | `StudentCbtEngineView.tsx:805` |
| 9 | CBT Interface | Space Key Appending Bug | Space button in virtual keypad appends to end of string instead of inserting at cursor | Space button click | `onChange(value + " ")` | Misplaces space when editing in middle of text | `StudentCbtEngineView.tsx:1091` |
| 10 | Security / Proctor | Native Android Auto-Lock Callback | Native bridge callback to lock device and launch exam when scheduled time arrives | `onNativeExamAutoLockTriggered` event | Triggers `handleStartExam(target)` | Triggers auto-start if matching schedule exists | `StudentSchedulesView.tsx:373` |
| 11 | Autosave | Resilient Answer Autosaving | Autosaves question answers with device session token and IndexedDB fallback | `question_id`, `text_answer` / `selected_option`, `X-Device-Token` | Updated answer record | 400/403 on token mismatch or deadline expiry | `studentExamApi.ts:112`, `exam_service.py:420` |

---

## 4. Edge Cases

## Edge Cases
| # | Feature | Input | Observed Behavior |
|---|---------|-------|-------------------|
| 1 | QR Check-in Auto-Start | Student scans QR 30 minutes before exam start | Currently auto-navigates to exam and triggers `enterKioskMode()` immediately; student trapped in kiosk before start time |
| 2 | Start Attempt Window Enforcement | `start_attempt` called when `now_utc < scheduled_start_at` | Currently succeeds because `session.status in ["PLANNED", ...]` overrides start time check; should return 400 `"Waktu pelaksanaan ujian belum tiba."` |
| 3 | Start Attempt Without Check-in | Student calls `start_attempt` without scanning QR | Backend returns 400 `"Anda belum melakukan absensi..."`; if called from frontend, kiosk mode is currently already active |
| 4 | Soft-Keyboard Suppression | User taps textarea in Android WebView | Android native soft-keyboard pops up over CBT view because `inputMode="none"` and `readOnly` are missing |
| 5 | Virtual Keypad Keystroke Focus | User taps any letter on Lockxam virtual keypad | `onChange` executes `el.focus()`, causing Android to summon native keyboard on every keystroke |
| 6 | Virtual Keypad Space Placement | User places cursor in middle of word and taps SPASI | Space is appended to the very end of `value` rather than inserted at cursor position |
| 7 | Completed Exam Opening | Student clicks on an already submitted/graded exam card | If engine opens, `enterKioskMode()` is invoked before `data.status === "SUBMITTED"` check exits; should never enter kiosk mode |
| 8 | Client-Server Clock Skew | Student device clock is set 1 hour fast | Client local `Date.now()` marks exam as OPEN, but server returns 400 on `start_attempt`; live countdown must use server-synchronized offset |
| 9 | Attempt Resume After App Crash | Student re-opens app after restart during active exam | `start_attempt` resumes existing attempt (`IN_PROGRESS`); `enterKioskMode()` activates exclusively after successful resume response |
| 10 | Exam Window Expiration During Attempt | Student working on exam when `deadline_at` or `scheduled_end_at` passes | Autosave rejects further answers, auto-submit marks attempt submitted, student exits to schedule view with kiosk released |

---

## 5. Caveats
1. The virtual keypad currently provides basic ABC (QWERTY), 123, and SYM rows. Extended international characters, accented letters, or LaTeX math equations are inserted as ASCII symbols; advanced math editing uses the preview container (`LaTeXText`).
2. Hardware USB/Bluetooth keyboards attached to Android devices: if `<textarea>` is made `readOnly={true}`, hardware typing directly into the DOM textarea will be suppressed unless explicitly forwarded via `onKeyDown`. In high-security kiosk testing, suppressing external hardware input is standard to prevent unauthorized shortcuts and clipboard exploits.
3. Native bridge integration: `window.LockxamBridge` is an Android JavascriptInterface injected by the Lockxam APK container. When running in a standard web browser during development, bridge calls are safely optional-chained (`(window as any).LockxamBridge?.enterKioskMode?.()`), ensuring zero browser console crashes.

---

## 6. Conclusion
The investigation revealed two critical bugs and their direct remedies:
1. **Kiosk Lifecycle**: Currently, `performCheckin` in `StudentSchedulesView.tsx` automatically initiates the exam after 800ms, and `StudentCbtEngineView.tsx` executes `enterKioskMode()` on mount before `startAttempt` is evaluated. To remediate:
   - Remove the auto-start timeout in `performCheckin`; leave the student on the schedule screen with confirmed attendance badge (`HADIR ✓`) and a live server-synchronized countdown ticker.
   - Remove `enterKioskMode()` from `useEffect([], ...)` in `StudentCbtEngineView.tsx`.
   - Call `LockxamBridge.enterKioskMode()` exclusively inside `initAttempt()` upon receiving a valid active attempt response from `studentExamApi.startAttempt()`.
   - Remove the permissive `or str(session.status).upper() in ["PLANNED", ...]` condition in `exam_service.py` so that premature attempt starts strictly return HTTP 400.
2. **Android Soft-Keyboard Suppression**:
   - In `StudentCbtEngineView.tsx`, configure `<textarea>` with `inputMode="none"` and `readOnly={true}`.
   - Ensure `el.focus()` in `LockxamBottomKeyboard.onChange` does not trigger IME popup by virtue of `inputMode="none"` and `readOnly`.
   - Fix the SPASI button in `LockxamBottomKeyboard` to call `handleKeyPress(" ")` so spaces respect the cursor position.

---

## 7. Verification Method
1. **Backend Window Validation Test**:
   - Run: `$env:PYTHONPATH="."; .venv\Scripts\pytest.exe tests\test_exam_security_boundaries.py -q`
   - Test premature start-attempt: Create schedule with `scheduled_start_at = now + 10m`. Attempting `POST /api/v1/exam/sessions/{id}/start-attempt` must return HTTP 400 with detail `"Waktu pelaksanaan ujian belum tiba."`.
2. **Kiosk Invocation Unit Inspection**:
   - Verify that `enterKioskMode` is absent from mount effects in `StudentCbtEngineView.tsx` and present solely after `await studentExamApi.startAttempt(...)`.
3. **Frontend Build & Lint**:
   - Run: `npm run build` in `frontend/` (must pass with 0 errors, producing minified assets).
   - Run: `npm run lint` in `frontend/` (oxlint completes cleanly).
4. **Pytest Regression Suite**:
   - Run: `$env:PYTHONPATH="."; .venv\Scripts\pytest.exe -q` (all 331 tests passing, 0 failures).
