# Student Import Architecture Review

**Batch**: Batch 1 — Student Bulk Import Remediation
**Scope**: Surgical Architecture & Security Review
**Status**: 🟢 STUDENT IMPORT FROZEN

---

## 1. Repository Boundary Compliance

We audited `SchoolStudentService.import_students_xlsx()` and removed all direct ORM queries (`db.query(...)` and `select(...)`). All database operations now go strictly through repositories to maintain structural boundary alignment:
* **NISN Uniqueness check**: Refactored to use the existing `auth_repository.get_by_nisn(db, school_id, nisn)`.
* **NIS Uniqueness check**: Added a new compliant method `get_by_nis(db, school_id, nis)` to `AuthRepository` and refactored the service layer to call it.
* **Cross-academic year check**: Added `get_any_by_name_in_school(db, school_id, class_name)` to `ClassRepository` and refactored the service to call it instead of querying `ClassEntity` directly.

**Flow**:
```text
SchoolStudentService
   │
   ├── auth_repository.get_by_nisn(...)          ➔ compliant
   ├── auth_repository.get_by_nis(...)           ➔ compliant
   └── class_repository.get_any_by_name_in_school(...) ➔ compliant
```

---

## 2. Transaction Ownership Trace

The lifecycle of a bulk import transaction is structured as follows:

```text
Router (FastAPI endpoint)
   │
   ├── [1] SchoolStudentService.import_students_xlsx(...)
   │       └── SAVEPOINT (db.begin_nested())
   │           └── db.add() & db.flush() per row
   │           └── SAVEPOINT COMMIT (savepoint.commit())
   │               └── On error: savepoint.rollback() + db.rollback()
   │
   ├── [2] ActivityService.log_activity(...)
   │
   └── [3] Final commit (db.commit())
```

### Analysis of the SAVEPOINT (`db.begin_nested()`)
1. **Necessity**: The local SAVEPOINT inside the service is necessary to guarantee isolated recovery. If one of the row insertions fails at the SQL/DBMS level (e.g. database validation/flush error), the service rolls back to the savepoint cleanly before throwing an exception, keeping the SQLAlchemy Session clean.
2. **Commit Ownership**: The ultimate transaction commit is strictly owned by the **Router** (calling `db.commit()`). The service's `savepoint.commit()` does *not* write to the disk; it only merges the changes into the parent transaction.
3. **Activity Logging Boundary**: Since the activity logging occurs *after* the service returns but *before* the final `db.commit()`, any failure in the activity logger will abort the request. The final commit will never be called, resulting in the entire student import being rolled back. This ensures absolute consistency between the imported entities and the audit trail.

---

## 3. Exception Safety (Leakage Prevention)

We corrected the exception handling block inside the service layer to mask raw database and SQL details:
* **Before**: Raw database/driver exception details (such as unique constraint names, table structures, and internal driver messages) were wrapped directly in `BusinessException` and returned to clients via `str(e)`.
* **After**:
  * Raw exceptions are logged internally via `logger.error` along with the full traceback for diagnostic purposes.
  * The user/client receives a safe, localized generic message: `"Gagal melakukan penyimpanan data ke database. Terjadi kesalahan internal pada server."`
  * This prevents the leak of internal schema signatures, database names, or table configurations.

---

## 4. Summary of Changes Made
* **`app/repositories/security/auth_repository.py`**: Added `get_by_nis()`.
* **`app/repositories/academic/class_repository.py`**: Added `get_any_by_name_in_school()`.
* **`app/services/school/student_service.py`**:
  * Removed direct ORM/`db.query` calls for NISN, NIS, and ClassEntity and replaced them with calls to `auth_repository` and `class_repository` methods.
  * Refactored exception handler to log tracebacks internally and return safe generic error messages.
* **`tests/test_student_import.py`**: Adjusted test assertions to verify that safe generic error messages are returned on DB failure.

---

## 5. Verification & Quality Gate
* **Student Import Integration tests**: `8 passed` (Green).
* **Academic Administration tests**: `Passed` (Green).
* **Full Backend Regression Suite**: `89 passed` (Green).
* **Zero new regressions introduced.**
