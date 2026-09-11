# Task Assignment: Survey - CBT Exam State Machine & Android Keyboard Suppression (R3)

- Working Directory: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_spec_miner_survey_2
- Workspace Root: C:\Users\irul2\Downloads\Equigrade_x_Lockxam
- Original Request File: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\ORIGINAL_REQUEST.md

## Assignment Details
Read C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\ORIGINAL_REQUEST.md thoroughly.
Conduct a deep, read-only investigation of:
1. QR check-in and kiosk lifecycle:
   - Identify where QR check-in happens, what state transitions occur, and how the student schedule screen and live server countdown are rendered.
   - Trace `enterKioskMode()` calls. Verify where it is currently triggered vs where it MUST be triggered (strictly and exclusively upon an authorized attempt start `start_attempt` when exam window is active).
2. Android soft-keyboard suppression in CBT essay and short-answer components:
   - Inspect existing input components for essay and short-answer questions.
   - Investigate how `inputMode="none"`, read-only textarea handling, and the programmatic Lockxam virtual keypad are implemented and interacted with.
   - Check where native keyboard popups can occur and how to completely suppress them while allowing virtual keypad input.

Write your findings to `C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_spec_miner_survey_2\handoff.md` and report back.
