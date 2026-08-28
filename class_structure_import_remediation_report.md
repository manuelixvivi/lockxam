# Class Structure Bulk Import Remediation Report

**Batch**: Batch 2 — Class Structure Bulk Import Remediation  
**Status**: 🟢 CONFORMANT  
**Date**: 2026-08-28  

---

## 1. Before Architecture

Previously, the class structure bulk import (`/api/v1/admin/classes/import-full`) possessed several severe design flaws that violated domain constraints:
* **Silent Auto-Creations**: If a class name or a teacher-subject competency relationship did not exist in the database, the import logic would silently auto-create them.
* **Partial Persistence**: The endpoint parsed rows sequentially and persisted elements inside a try-catch block per row, meaning some valid classes/subjects were persisted even if others failed.
* **Loose Reference Checks**: Resolution of Class entities was not bound to the authenticated school and active academic year context.
* **Direct Database Queries**: The service layer bypassed repository patterns and performed direct ORM querying (`db.query`), violating repository boundary rules.

---

## 2. After Architecture

We refactored the bulk import into a fully atomic, non-auto-creating pipeline adhering to **Import Contract v1.0**:

```text
                     XLSX Upload (Client)
                             │
                             ▼
               FastAPI Router (import-full)
                             │
                    [First-Pass Validation]
           Verify Academic Year and Tenant Context
                             │
            Check Existence of all Classes & Subjects
            Check Teacher Competencies (TeacherSubject)
            Check File and DB Duplicate Records
                             │
             ┌───────────────┴───────────────┐
             ▼                               ▼
       Validation Errors?             Validation OK?
             │                               │
       [Rollback & Reject]            [Second-Pass Savepoint]
     Return 422 JSONResponse       Apply Student Enrollments &
                                   Class-Subject Assignments
                                             │
                                             ▼
                                     [Activity Logging]
                                             │
                                             ▼
                                      [Final Commit]
```

---

## 3. Auto-Create Behavior Removed

* **Classes**: Missing classes are no longer provisioned on-the-fly. If a class name is not found within the selected Academic Year, the entire batch is rejected.
* **Subjects**: Missing subjects are no longer created. They must be explicitly created via the `/admin/subjects` master management flow.
* **Teacher Competencies**: Missing `TeacherSubject` entries are no longer auto-generated. If a teacher is assigned to a subject they are not qualified to teach, the import fails with code `TEACHER_NOT_COMPETENT`.

---

## 4. Validation Rules

1. **CLASS_NAME_REQUIRED**: Class name must be populated.
2. **CLASS_NOT_FOUND**: The class must exist for the active school and academic year.
3. **STUDENT_IDENTIFIER_REQUIRED**: Student rows must provide a NISN, NIS, or Username.
4. **STUDENT_NOT_FOUND**: The student must exist in the school.
5. **SUBJECT_CODE_REQUIRED**: Subject code must be specified.
6. **SUBJECT_NOT_FOUND**: The subject must exist in the school.
7. **TEACHER_CODE_REQUIRED**: The teacher identifier (code, NIP, or username) must be specified.
8. **TEACHER_NOT_FOUND**: The teacher must exist in the school.
9. **TEACHER_NOT_COMPETENT**: The teacher must possess active competency for the subject.
10. **DUPLICATE_CLASS_SUBJECT_IN_FILE**: The file must not map the same subject to the same class multiple times.
11. **DUPLICATE_CLASS_SUBJECT_TEACHER_IN_FILE**: The file must not map the same teacher to the same class-subject combination multiple times.

---

## 5. Reference Resolution

* **Class Resolution**: Resolved strictly using the composite key: `school_id + academic_year_id + class_name`. Matching a class name from a different academic year is treated as a validation failure.
* **Teacher Resolution**: Resolved case-insensitively using:
  1. Teacher Code (`get_teacher_by_code`)
  2. NIP (`get_by_nip`)
  3. Username (`get_by_username`)
* **Subject Resolution**: Resolved case-insensitively using `subject_repository.get_by_code_or_name`.

---

## 6. Tenant Rules & Isolation

* **School Authority**: The school context is derived strictly from the authenticated Admin's JWT context (`school_id`).
* **Cross-Tenant Prevention**: Any referenced Class, Student, Subject, or Teacher belonging to another school is rejected immediately during the first-pass validation.

---

## 7. Transaction Behavior

* **Service-Level Savepoint**: The Service starts a SQLAlchemy savepoint (`db.begin_nested()`). If any SQL violation or persistence crash occurs during processing, the service rolls back to the savepoint, rolls back the database session, logs the traceback, and raises a masked generic error.
* **Router Commit**: The Router maintains transaction ownership, executing the final `db.commit()` only after both the service completes and `ActivityService.log_activity` succeeds.

---

## 8. Files Changed

* **Frontend**:
  * [`frontend/src/views/admin/ClassesView.tsx`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/views/admin/ClassesView.tsx): Appended `row_num` to student and subject parsing payloads to provide accurate row-level feedback on validation failures.
* **Backend**:
  * [`app/services/academic/class_structure_service.py`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/app/services/academic/class_structure_service.py): Implemented the non-auto-creating `import_classes_xlsx()` method.
  * [`app/api/admin_class.py`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/app/api/admin_class.py): Refactored `import_full_classes_xlsx()` to call the new service method and return structured `ImportResponse`.

---

## 9. Tests Added

A complete test suite was introduced in:
📄 [`tests/test_class_structure_import.py`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/tests/test_class_structure_import.py)

1. `test_import_class_structure_all_valid`: Verifies all valid rows commit successfully.
2. `test_import_class_structure_missing_class`: Rejects missing classes.
3. `test_import_class_structure_missing_subject`: Rejects missing subjects.
4. `test_import_class_structure_missing_teacher`: Rejects missing teachers.
5. `test_import_class_structure_missing_competency`: Rejects with `TEACHER_NOT_COMPETENT`.
6. `test_import_class_structure_wrong_academic_year`: Rejects incorrect academic year IDs.
7. `test_import_class_structure_cross_tenant_class`: Rejects cross-tenant classes.
8. `test_import_class_structure_cross_tenant_subject`: Rejects cross-tenant subjects.
9. `test_import_class_structure_cross_tenant_teacher`: Rejects cross-tenant teachers.
10. `test_import_class_structure_duplicate_subject_in_file`: Rejects duplicate class-subjects in file.
11. `test_import_class_structure_duplicate_cst_in_file`: Rejects duplicate class-subject-teachers in file.
12. `test_import_class_structure_existing_class_subject`: Safely processes existing class-subject associations without duplicating.
13. `test_import_class_structure_existing_cst`: Safely updates/preserves existing class-subject-teacher associations.
14. `test_import_class_structure_mixed_valid_invalid`: Verifies complete rollback on any invalid rows (0 relations created).
15. `test_import_class_structure_db_failure_rollback`: Verifies database errors are caught, logged, and rolled back safely.

---

## 10. Regression Results

All 32 backend tests passed:
```text
tests\test_student_import.py ........                                    [ 25%]
tests\test_class_structure_import.py ...............                     [ 71%]
tests\test_academic_administration_api.py .........                      [100%]

====================== 32 passed, 65 warnings in 14.20s =======================
```
No regressions were introduced, and the student import domain remained fully intact.
