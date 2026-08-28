# Global Import Validation Matrix

**System**: EquiGrade x Lockxam v3.0  
**Audit Date**: 2026-08-28  
**QA Auditor**: Antigravity QA Auditor  
**Document Version**: 1.0 (Audit Phase)  
**Status**: 🔴 AUDITED — MATRIX COMPLETE

---

| Import | Entity | Frontend | Endpoint | Service | Repository | Structural Validation | Semantic Validation | Reference Validation | Tenant Isolation | Authorization | Duplicate | Transaction | Atomic | Rollback | Row Error | Tests | Risk | Recommendation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Student** | `AuthAccount` (Student) | `StudentsView.tsx` | `/api/v1/admin/students` | `SchoolStudentService` | `auth_repository` | Frontend checks formats | Backend validates unique NISN | 🔴 None (Class name is string) | Yes (Token `school_id`) | Admin role required | Checks DB; no file duplicate check | No transaction | ❌ NO | ❌ NO | Yes (toast logs row number) | No | **P0** | Migrate to batch endpoint |
| **Class Structure** | Classes & relations | `ClassesView.tsx` | `/classes/import-full` | `ClassStructureService` | `class_repository` | Backend parses nested arrays | Backend handles loops | 🔴 Gap (Creates class & competency silently) | Yes | Admin role required | Checks DB | Commit after loops | ❌ NO | ❌ NO | No (swallows exceptions) | Yes | **P0** | Refactor endpoint to rollback on fail |
| **Teacher** | `AuthAccount` (Teacher) | `TeachersView.tsx` | `/api/v1/admin/teachers` | `SchoolTeacherService` | `auth_repository` | Frontend checks formats | Backend validates teacher code | N/A | Yes | Admin role required | Checks DB | No transaction | ❌ NO | ❌ NO | Yes (toast logs row #) | No | **P1** | Migrate to batch endpoint |
| **Subject** | `Subject` | `SubjectsView.tsx` | `/api/v1/admin/subjects` | `SubjectService` | `subject_repository` | Frontend checks formats | Backend validates subject code | N/A | Yes | Admin role required | Checks DB | No transaction | ❌ NO | ❌ NO | Yes (toast logs row #) | No | **P1** | Migrate to batch endpoint |
| **Question Bank** | `TeacherQuestion` | `QuestionBankView.tsx` | `/teacher/questions` | `TeacherContentService` | `teacher_question_repo` | Frontend checks PG/ES formats | Backend validates type & fields | Subject exists check | Yes | Teacher role required | Checked locally in frontend | No transaction | ❌ NO | ❌ NO | Yes (Local report view) | No | **P1** | Migrate to batch endpoint |
| **Question Package** | `QuestionPackageItem` | `QuestionPackageDetailView.tsx` | `/teacher/questions` + `/link` | `TeacherContentService` | `question_package_repo` | Frontend checks options & score | Backend validates fields | Subject exists check | Yes | Teacher role required | Checked locally in frontend | No transaction | ❌ NO | ❌ NO | Yes (Local report view) | No | **P1** | Migrate to batch endpoint |
| **SuperAdmin School** | `School` | `SuperAdminSchoolsView.tsx` | `/api/v1/schools` | `SchoolService` | `school_repository` | Frontend checks format | Backend validates NPSN/domain | Level exists check | N/A | SuperAdmin required | Checks DB | No transaction | ❌ NO | ❌ NO | Yes (Local report banner) | No | **P2** | Migrate to batch endpoint |
| **Exam Schedule** | `ExamSchedule` | `ExamSchedulesView.tsx` | `/exam-schedules/.../import` | `ExamScheduleService` | `exam_schedule_repo` | Backend validates header schema | Backend checks class overlap | 🟢 Yes (resolves Class, Subject, Proctor) | Yes | Admin role required | Check overlap in DB & loop | Yes (commits at end) | 🟢 YES | 🟢 YES | Yes (Precise row # + error code) | Yes | **P4** | Already conformant |
