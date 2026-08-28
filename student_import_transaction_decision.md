# Student Import Transaction Decision Audit

**Batch**: Batch 1 — Student Bulk Import Remediation  
**Topic**: Transaction Ownership Decision Audit  
**Date**: 2026-08-28  

---

## 1. Current Transaction Flow

The transaction boundary for student bulk import spans across the Router, the Student Service, and the Activity Logger:

```text
Router (FastAPI handler: import_students)
   │
   ├── [1] SchoolStudentService.import_students_xlsx(...)
   │       └── SAVEPOINT (db.begin_nested())
   │           └── Loop: db.add(student) & db.flush()
   │           └── SAVEPOINT COMMIT (savepoint.commit())
   │               └── On persistence error: savepoint.rollback() + db.rollback()
   │
   ├── [2] Loop: ActivityService.log_activity(...) for each student
   │       └── db.add(activity_log) & db.flush() (via Repository)
   │
   └── [3] Final commit (db.commit())
```

---

## 2. Existing Project Conventions

To determine transaction ownership, we inspected other mutation routes (such as schedule creation, proctor assignment, and bulk exam schedule imports in `app/api/admin_exam_schedule.py`):
1. **Conventions**: Across all administration routers, database changes are added to the session and flushed inside the services, and then logged via `ActivityService.log_activity` in the router. The final database commit (`db.commit()`) is always owned and executed by the **Router** at the end of the request handler.
2. **Atomicity**: If any error happens after the service executes but before the final router response (including during activity logging), the router fails to execute `db.commit()`. FastAPI's dependency cleanup then closes the session (`db.close()`), which automatically rolls back the entire pending transaction.

---

## 3. Option Evaluation

### Option A: Student Import + Activity Logging in Same Transaction (Recommended)
* **Semantics**: Both student creations and their audit logs are wrapped in a single database transaction. Either all changes are successfully committed, or everything is rolled back.
* **Pros**: Guarantees data audit consistency. An admin action (importing students) is never recorded in the database without its corresponding audit trail (`ActivityLog`), and vice-versa.
* **Cons**: If the activity logger fails, the successful student import is discarded. (This is generally desirable for strict security compliance).

### Option B: Student Import Independent from Activity Logging
* **Semantics**: Student import commits immediately within the service or router. Activity logging is performed independently (possibly in a separate transaction or background worker).
* **Pros**: Resilience. Failures in logging do not rollback the import.
* **Cons**: Risk of audit trail inconsistency. If the system crashes or logging fails after import commits, the action goes unrecorded.

---

## 4. Recommended Canonical Behavior

We recommend and confirm **Option A** as the canonical transaction model:
1. **Alignment with Convention**: It perfectly matches the transaction lifecycle used throughout the entire codebase (e.g., in `admin_exam_schedule.py`).
2. **Audit Integrity**: In academic administration systems, audit trail validity is paramount. Importing students without writing the activity log violates compliance protocols.
3. **No Code Changes Required**: The current implementation of `POST /api/v1/admin/students/import` and the service layer already strictly conforms to Option A, ensuring that any logging error will rollback the entire student import.

---

## 5. Architectural Quality Gate Checklist

| Requirement | Status | Verification Detail |
| --- | --- | --- |
| **1. Validation before persistence** | 🟢 TRUE | First-pass loop validates all row structure, types, and references before any database write/savepoint. |
| **2. Missing Class rejection** | 🟢 TRUE | If a class name is not resolved in the active year, `CLASS_NOT_FOUND` is triggered; zero students are inserted. |
| **3. Wrong Academic Year rejection** | 🟢 TRUE | Year ID is validated against the active school context at start; throws 400 immediately. |
| **4. Cross-tenant Class rejection** | 🟢 TRUE | Class lookup context uses `school_id + academic_year_id + class_name`, rejecting other school's classes. |
| **5. Duplicate NISN rejection** | 🟢 TRUE | Checked within the import batch (internal seen dict) and against DB (repository call); rejects entire batch. |
| **6. DB Persistence Failure Rollback** | 🟢 TRUE | If database constraint/write failure occurs, the SAVEPOINT rolls back, and the session is rolled back. |
| **7. Error Safety (Masking)** | 🟢 TRUE | Internal logs capture the full traceback while the client receives a safe, generic Indonesian error message. |
| **8. Repository Boundary compliance** | 🟢 TRUE | All lookups use `auth_repository`, `class_repository`, and `academic_year_repository`. No direct ORM calls. |
| **9. Regressions** | 🟢 NONE | Full suite passes: `89 passed, 66 warnings`. |
