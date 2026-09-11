# Task Assignment: Milestone 4 - AI Confidence Elevation & Teacher Review Experience (R5)

- Working Directory: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_worker_m4
- Workspace Root: C:\Users\irul2\Downloads\Equigrade_x_Lockxam
- Authoritative Request File: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\ORIGINAL_REQUEST.md
- Project Scope: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\PROJECT.md
- Survey Handoff: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_explorer_survey_3\handoff.md

## Exclusive Write Ownership
You exclusively own and may edit:
- `app/services/ai/grading/grading_schema.py`
- `app/services/ai/grading/batch_grading_schema.py`
- `app/services/ai/grading/grading_service.py`
- `app/api/teacher.py`
- `frontend/src/api/teacherDashboard.ts`
- `frontend/src/views/teacher/TeacherGradingView.tsx`
- `tests/test_ai_confidence_elevation.py` (new test file)

DO NOT edit files owned by other milestones.

## Implementation Scope
1. **Root-Level AI Confidence Schema Elevation**:
   - In `app/services/ai/grading/grading_schema.py`:
     - Add to `GradingEvaluateResponse`:
       - `confidence: float = Field(..., ge=0.0, le=1.0, description="Root-level grading confidence score (0.0 to 1.0)")`
       - `confidence_level: str = Field(..., description="Categorical confidence: HIGH, MEDIUM, or LOW")`
       - `review_required: bool = Field(..., description="Whether teacher review is required")`
   - In `app/services/ai/grading/batch_grading_schema.py`:
     - Add root-level `confidence`, `confidence_level`, and `review_required` to `BatchStudentGradingResult`.
   - In `app/services/ai/grading/grading_service.py`:
     - In `GradingService.evaluate`:
       - Calculate `confidence = quality_indicator` (float between 0.0 and 1.0, defaulting to 0.85 if missing).
       - Classify categorical levels:
         - HIGH: confidence >= 0.90
         - MEDIUM: 0.75 <= confidence < 0.90
         - LOW: confidence < 0.75
       - Set `review_required = (confidence < 0.90)` (HIGH = Auto Accept, MEDIUM = Requires Review, LOW = Manual Review Required).
       - Return these root-level fields in `GradingEvaluateResponse`.

2. **Teacher Grading Endpoints Propagation**:
   - In `app/api/teacher.py`:
     - In `GET /api/v1/teacher/exam-history/{schedule_id}/student-answers`:
       - Return `confidence`, `confidence_level`, `review_required`, `rubric_scores`, and `academic_rationale` for evaluated essay/short-answer answers.
     - In `GET /api/v1/teacher/grading/evaluations`:
       - Include `confidence`, `confidence_level`, and `review_required`.
   - In `frontend/src/api/teacherDashboard.ts`:
     - Update types to include `confidence: number`, `confidence_level: "HIGH" | "MEDIUM" | "LOW"`, `review_required: boolean`, `rubric_scores?: any[]`, `academic_rationale?: string`.

3. **Teacher Grading Detail UI Experience**:
   - In `frontend/src/views/teacher/TeacherGradingView.tsx`:
     - In Level 3 essay review view (where student questions and answers are rendered):
       - Render a visual confidence gauge (e.g. circular or horizontal gauge displaying confidence percentage).
       - Render categorical classification badge:
         - HIGH (90–100%): Emerald badge "HIGH (90–100%) — Auto Accept"
         - MEDIUM (75–89%): Amber badge "MEDIUM (75–89%) — Requires Review"
         - LOW (0–74%): Crimson badge "LOW (0–74%) — Manual Review Required"
       - Render Rubric Criteria Breakdown: render each criterion (`ku_id`, criteria description, weight, earned score / max score).
       - Render Generated Academic Rationale: display pedagogical rationale explaining the awarded points.

4. **Mandatory Integrity Warning**:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Verification
- Run backend tests: `.venv\Scripts\pytest.exe tests/test_ai_confidence_elevation.py tests/test_ai_grading.py -v`
- Run frontend build: `npm run build` in `frontend/` (0 errors)
- Document all changes and verification output in `C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_worker_m4\handoff.md`.
