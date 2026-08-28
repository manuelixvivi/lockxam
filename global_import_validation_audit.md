# Global Import Validation Audit Report

**System**: EquiGrade x Lockxam v3.0  
**Audit Date**: 2026-08-28  
**QA Auditor**: Antigravity QA Auditor  
**Document Version**: 1.0 (Audit Phase)  
**Status**: 🔴 AUDITED — REMEDIATION REQUIRED

---

## 1. Executive Summary

We have performed a system-wide audit of all import and bulk-data mechanisms across SuperAdmin, School Admin, and Teacher portals. 

The audit reveals a fundamental architectural issue: **7 out of 8 import mechanisms violate atomicity (possessing `🔴 ATOMICITY VIOLATION` or `🔴 REFERENCE VALIDATION GAP`)**. Most importers run sequential, individual API requests inside frontend loops, meaning database mutations occur per-row. This leads to **partial persistence** (e.g., 99 rows succeed, 1 fails, leaving 99 rows persisted in a dirty state), lack of proper database transaction boundaries, poor performance, and academic integrity risks.

Only the **Exam Schedule Import** follows the conformant pattern (validate all, commit all, with complete rollback on any error).

---

## 2. Detailed Audit of Importers

### A. Student Import
* **Frontend File**: [`frontend/src/views/admin/StudentsView.tsx`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/views/admin/StudentsView.tsx)
* **Backend Router**: `app/api/school_student.py`
* **Endpoint**: `POST /api/v1/admin/students` (Called in a loop sequentially per row)
* **Schema**: `StudentCreateRequest`
* **Service**: `SchoolStudentService.create_student`
* **Repository**: `auth_repository.create` (inherited from `BaseRepository`)
* **Parser**: Frontend `readXlsxFile` utility
* **Transaction Boundary**: None (Committed per row at database level)
* **Tests**: None covering bulk import

#### Detailed Behavior Verification:
1. **Frontend Parse**: Yes, using `readXlsxFile(file)`.
2. **Frontend Validation**: Yes, validates name, NISN format, and gender format.
3. **Frontend Preview**: No preview stage. It immediately runs the import loop.
4. **Call Behavior**: Calls API sequentially once per row in a loop.
5. **Backend Batch Validation**: No batch validation. Backend only validates a single student per request.
6. **Reference Validation**: `class_name` is passed as a string. However, the system does **not** perform an authoritative check for class existence prior to student creation. (`🔴 REFERENCE VALIDATION GAP`).
7. **Tenant Validation**: Yes, school ID is derived from the current user token.
8. **Authorization**: Yes, gates access via `require_role(UserRole.ADMIN)`.
9. **Duplicate Detection**: Backend detects existing NISN/NIS in DB and throws 409. Lacks checking for duplicates *within* the uploaded Excel file.
10. **Transaction & Commit**: No database transaction or rollback. `🔴 ATOMICITY VIOLATION`. Failed rows are toasted, but previously successful rows remain persisted.
11. **Error Reporting**: Frontend toast displays the row numbers that failed, but the backend lacks a structured validation report.

#### Student Import Target Behavior:
If the user uploads:
* Row 2: Student A ➔ X IPA 1 (exists)
* Row 3: Student B ➔ X IPA 9 (does not exist)

Current Code Behavior:
* Student A is created successfully and committed.
* Student B fails (returns 400/409).
* **Result**: Student A remains persisted while Student B is rejected. This is a direct violation of atomicity.

---

### B. Class Structure Import
* **Frontend File**: [`frontend/src/views/admin/ClassesView.tsx`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/views/admin/ClassesView.tsx)
* **Backend Endpoint**: `POST /api/v1/admin/classes/import-full`
* **Validation Location**: Backend service layer.
* **Reference Validation**: Resolves `class_name`, `nisn`, `subject_code`, `teacher_code`. However, if the referenced class name is missing, it silently creates the class. If a teacher-subject competency is missing, it silently inserts it. (`🔴 REFERENCE VALIDATION GAP`).
* **Tenant Validation**: Checked via `school_id`.
* **Duplicate Validation**: Skips checks for duplicate student enrollments or subject assignments in the file.
* **Atomicity & Transaction**: `🔴 ATOMICITY VIOLATION`. The endpoint catches exceptions in nested loops, performs `db.rollback()` for the single failed row, and calls `continue` to proceed with the next record. It then calls `db.commit()` at the end, committing the mixed success state.
* **Error Reporting**: No specific validation report. Errors are swallowed, and successfully processed records are returned.
* **Tests**: Some tests exist in `test_academic_administration_api.py`.
* **Risk Level**: **P0** (Directly violates core academic boundaries by silently creating master data and teacher competencies).

---

### C. Teacher Import
* **Frontend File**: [`frontend/src/views/admin/TeachersView.tsx`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/views/admin/TeachersView.tsx)
* **Backend Endpoint**: `POST /api/v1/admin/teachers` (Called per row in loop)
* **Validation Location**: Frontend formats + backend single-entity validations.
* **Reference Validation**: None.
* **Tenant Validation**: Yes, isolated by `school_id`.
* **Duplicate Validation**: Checks unique NIP and teacher code in database.
* **Atomicity & Transaction**: `🔴 ATOMICITY VIOLATION`. Run in a sequential loop.
* **Risk Level**: **P1**

---

### D. Subject Import
* **Frontend File**: [`frontend/src/views/admin/SubjectsView.tsx`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/views/admin/SubjectsView.tsx)
* **Backend Endpoint**: `POST /api/v1/admin/subjects` (Called per row in loop)
* **Validation Location**: Frontend formats + backend single-subject validation.
* **Duplicate Validation**: Checks unique subject code.
* **Atomicity & Transaction**: `🔴 ATOMICITY VIOLATION`. Run in a sequential loop.
* **Risk Level**: **P1**

---

### E. Question Bank Import
* **Frontend File**: [`frontend/src/views/teacher/QuestionBankView.tsx`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/views/teacher/QuestionBankView.tsx)
* **Backend Endpoint**: `POST /api/v1/teacher/questions` (Called per row in loop)
* **Validation Location**: Frontend (PG options, rubrics) + backend.
* **Reference Validation**: Subject validated.
* **Atomicity & Transaction**: `🔴 ATOMICITY VIOLATION`. Loops sequential requests.
* **Error Reporting**: Displays a custom local report in the UI for success, skipped, and failed rows.
* **Risk Level**: **P1**

---

### F. Question Package Import
* **Frontend File**: [`frontend/src/views/teacher/QuestionPackageDetailView.tsx`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/views/teacher/QuestionPackageDetailView.tsx)
* **Backend Endpoint**: `POST /api/v1/teacher/questions` (to create in bank if missing) + `POST /api/v1/teacher/packages/{id}/questions` (to link to package)
* **Validation Location**: Frontend + Backend.
* **Atomicity & Transaction**: `🔴 ATOMICITY VIOLATION`. Multiple HTTP requests per row are executed sequentially.
* **Risk Level**: **P1**

---

### G. SuperAdmin School Import
* **Frontend File**: [`frontend/src/views/superadmin/SuperAdminSchoolsView.tsx`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/views/superadmin/SuperAdminSchoolsView.tsx)
* **Backend Endpoint**: `POST /api/v1/schools` (Called per row in loop inside `ImportExportBar`)
* **Validation Location**: Frontend (required fields) + Backend.
* **Reference Validation**: School level mapped.
* **Atomicity & Transaction**: `🔴 ATOMICITY VIOLATION`. If any row fails, previous schools remain persisted.
* **Risk Level**: **P2**

---

### H. Exam Schedule Import
* **Frontend File**: [`frontend/src/views/admin/ExamSchedulesView.tsx`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/views/admin/ExamSchedulesView.tsx)
* **Backend Endpoint**: `POST /api/v1/admin/exam-schedules/packages/{id}/import` (Receives entire row array)
* **Validation Location**: Backend service layer.
* **Reference Validation**: Strictly resolves Class, Subject, ClassSubjectTeacher, and Proctor. If any are missing, the import fails.
* **Duplicate Validation**: Verifies overlapping schedules.
* **Atomicity & Transaction**: **🟢 ATOMIC & CONFORMANT**. If any row is invalid, it throws `BusinessException` and aborts the entire transaction.
* **Error Reporting**: Returns row-specific details (e.g., `Baris #12: Rombel Kelas '...' tidak ditemukan`).
* **Tests**: Integrated tests in `test_academic_administration_api.py`.
* **Risk Level**: **P4** (Safe/Protected).

---

## 3. Analysis of the Generic `ImportExportBar.tsx`

The `ImportExportBar` component acts as a generic UI component that manages the file input and shows progress. However, it currently forces a sequential mutation model:
```typescript
      for (let i = 0; i < rows.length; i++) {
        const row = rows[i];
        const identifier = Object.values(row)[0] as string || `Baris ${i + 2}`;
        const errorMsg = await onImportRow(row, i);
        if (errorMsg) {
          failed.push({ row: i + 2, identifier, reason: errorMsg });
        } else {
          successCount++;
        }
      }
```
* **Direct Database Mutation**: Yes, it triggers mutations directly per-row via `onImportRow`.
* **Validation order**: Validation is done per-row at the backend API gateway during mutation.
* **Atomicity Violation**: Yes. If a row fails, previously mutated rows are already committed.
* **Redundancy**: In `StudentsView`, `TeachersView`, and `ClassesView`, `ImportExportBar` actually has a dummy `onImportRow={async () => null}` callback. The actual imports are wired in `AddDataChoiceModal` but still use the same sequential frontend loop pattern.

---

## 4. Academic & Relational Integrity Impact

* **No Implicit Master Creation**: Under the current baseline, imports (like Class Structure) create Class entities on the fly. This violates class uniqueness rules where a class must map strictly to a specific school and academic year.
* **Orphaned Enrollments**: A student can be imported with a legacy `class_name` that does not exist as an actual Class entity in the database, resulting in a disconnected profile.
* **Unvalidated Competency**: Automatic assignment of subject competencies to teachers during class structure import bypasses administrative RBAC gates.

---

## 5. Security & Isolation Check
* **Tenant Security Check**: Yes, `school_id` is resolved strictly from the JWT token in all school admin routes. Even if an Excel row contains a custom `school_id` column, the backend routes completely ignore it, resolving everything via `current_user.get("school_id")`.
* **Academic Year Check**: In class resolution, `class_repository.get_by_name` uses both `school_id` and `academic_year_id` along with the class name. Class names are unique per school and academic year.
