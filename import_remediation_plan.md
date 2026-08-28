# Import Remediation Plan

**System**: EquiGrade x Lockxam v3.0
**Audit Date**: 2026-08-28
**QA Auditor**: Antigravity QA Auditor
**Document Version**: 1.0 (Proposal)
**Status**: 🔴 PROPOSED — AWAITING REVIEW

---

## 1. Remediation Strategy

To address the `🔴 ATOMICITY VIOLATION` and `🔴 REFERENCE VALIDATION GAP` issues discovered across the codebase, we propose refactoring all bulk data operations to follow a unified pattern:
```text
XLSX file ➔ Parse in Frontend ➔ POST Bulk payload (rows[]) ➔ Validate all (Backend) ➔ Persist Atomically (Rollback on any error)
```
Rather than immediately editing all codebase endpoints, the remediation will be executed in **7 structured batches** to prevent disruption to existing frozen domains.

---

## 2. Implementation Batches

### 📦 BATCH 1: Core Contract & Validation Framework (P0 - Security & Tenant Isolation)
* **Goal**: Establish the base Pydantic models for validation reports and a transaction helper class in the backend core.
* **Dependencies**: None.
* **Backend Modifications**:
  - Create `app/schemas/common/import_validation.py` defining the structured error report schema (row, field, value, error code, explanation).
  - Add tenant validation validators to ensure `school_id` from the JWT token is strictly applied.
* **Risk Addressed**: Tenant bypass and security leaks.

### 📦 BATCH 2: Student Import Refactoring (P0 - Historical Corruption)
* **Goal**: Replace the frontend-driven student import loop with a single atomic transaction.
* **Dependencies**: Batch 1.
* **Backend Modifications**:
  - Create `POST /api/v1/admin/students/import` in `app/api/school_student.py`.
  - Implement `SchoolStudentService.import_students_xlsx()` which verifies class references (`school_id + academic_year_id + name`) and checks duplicate NISN/NIS within the file and database before executing batch insert.
* **Frontend Modifications**:
  - Redirect XLSX uploads to the new batch endpoint.
* **Risk Addressed**: Orphaned student enrollments and partial success database pollution.

### 📦 BATCH 3: Teacher & Subject Importers Refactoring (P1 - Atomicity & Integrity)
* **Goal**: Refactor Teacher and Subject imports to use atomic endpoints.
* **Dependencies**: Batch 1.
* **Backend Modifications**:
  - Create `POST /api/v1/admin/teachers/import` and `POST /api/v1/admin/subjects/import`.
  - Enforce database UNIQUE constraints (`teacher_code`, `subject_code` per school) in single database transactions.
* **Frontend Modifications**:
  - Connect `TeachersView` and `SubjectsView` to new endpoints.
* **Risk Addressed**: Partially imported teachers or subjects with broken reference states.

### 📦 BATCH 4: Class Structure & Academic Relations (P0/P1 - Business Rules)
* **Goal**: Clean up `/classes/import-full` to enforce atomicity and remove silent auto-creations.
* **Dependencies**: Batch 1, 2, 3.
* **Backend Modifications**:
  - Refactor `import_full_classes_xlsx` in `app/api/admin_class.py`.
  - Replace `try...except continue` loops with immediate exceptions.
  - If a Class, Student, or Subject reference does not exist in the DB, reject the row.
  - Remove implicit `TeacherSubject` competency creation.
* **Risk Addressed**: Auto-provisioning of classes or competencies that bypass school admin controls.

### 📦 BATCH 5: Question Bank & Package Importers (P1 - Relational Integrity)
* **Goal**: Migrate teacher question imports to a transaction-bound backend endpoint.
* **Dependencies**: Batch 1.
* **Backend Modifications**:
  - Implement `POST /api/v1/teacher/questions/import` and package question assignments.
* **Risk Addressed**: Broken option arrays or rubrics committed halfway through Excel parse.

### 📦 BATCH 6: Generic Preview & Validation UX (P3 - Usability)
* **Goal**: Refactor `ImportExportBar` to act solely as a file preview, parsing, and progress bar component, without orchestrating API calls directly.
* **Dependencies**: Batch 2, 3, 4, 5.
* **Frontend Modifications**:
  - Modify `ImportExportBar.tsx` to return the parsed array to the parent component, allowing the parent to send the batch payload to the specific atomic endpoint and display the Pydantic-formatted error report.
* **Risk Addressed**: Inconsistent importer user experiences and frontend-driven loops.

### 📦 BATCH 7: Regression Audit & Verification (P4 - Maintainability)
* **Goal**: Write integration tests for all 8 importers verifying rollback behavior on validation failure.
* **Dependencies**: All Batches.
* **Test Additions**:
  - Add pytest cases verifying that if row N fails, rows 1..N-1 are successfully rolled back.

---

## 3. Database Integrity & Race Conditions

* **Select-then-Insert Protection**: To prevent race conditions during bulk uploads, we must not rely solely on `SELECT` pre-checks.
* **Remediation**: Enforce UNIQUE constraints at the database level:
  - `auth_accounts(school_id, username)`
  - `auth_accounts(school_id, nisn)`
  - `schools(npsn)`
  - `schools(code)`
  - `schools(domain)`
  - `classes(school_id, academic_year_id, name)` (ACADEMIC-CLASS-001)

Any SQLAlchemy insertion must catch `IntegrityError`, perform a transaction rollback, and map the database conflict to the correct validation error payload.
