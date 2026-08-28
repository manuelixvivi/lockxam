# Global Import Inventory

This inventory documents all 8 import and bulk data ingestion mechanisms found in EquiGrade x Lockxam v3.0.

---

## 1. Student Import
* **Domain**: School Admin
* **Entity**: Student (`AuthAccount` with `role == UserRole.STUDENT`)
* **Frontend File**: [`frontend/src/views/admin/StudentsView.tsx`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/views/admin/StudentsView.tsx) (inside `onImportXlsx` callback of `AddDataChoiceModal`)
* **Backend Router**: `app/api/school_student.py`
* **Endpoint**: `POST /api/v1/admin/students` (Called in a loop sequentially per row)
* **Schema**: `StudentCreateRequest`
* **Service**: `SchoolStudentService.create_student`
* **Repository**: `auth_repository.create` (inherited from `BaseRepository`)
* **Parser**: Frontend `readXlsxFile` utility
* **Transaction Boundary**: None (Committed per row at database level)
* **Tests**: None covering bulk import

---

## 2. Teacher Import
* **Domain**: School Admin
* **Entity**: Teacher (`AuthAccount` with `role == UserRole.TEACHER`)
* **Frontend File**: [`frontend/src/views/admin/TeachersView.tsx`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/views/admin/TeachersView.tsx) (inside `onImportXlsx` callback of `AddDataChoiceModal`)
* **Backend Router**: `app/api/teacher.py`
* **Endpoint**: `POST /api/v1/admin/teachers` (Called in a loop sequentially per row)
* **Schema**: `TeacherCreateRequest`
* **Service**: `SchoolTeacherService.create_teacher`
* **Repository**: `auth_repository.create` (inherited from `BaseRepository`)
* **Parser**: Frontend `readXlsxFile` utility
* **Transaction Boundary**: None (Committed per row)
* **Tests**: None covering bulk import

---

## 3. Subject Import
* **Domain**: School Admin
* **Entity**: Subject (`Subject` model)
* **Frontend File**: [`frontend/src/views/admin/SubjectsView.tsx`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/views/admin/SubjectsView.tsx) (inside `onImportXlsx` callback of `AddDataChoiceModal`)
* **Backend Router**: `app/api/subject.py`
* **Endpoint**: `POST /api/v1/admin/subjects` (Called in a loop sequentially per row)
* **Schema**: `SubjectCreateRequest`
* **Service**: `SubjectService.create_subject`
* **Repository**: `subject_repository.create` (inherited from `BaseRepository`)
* **Parser**: Frontend `readXlsxFile` utility
* **Transaction Boundary**: None (Committed per row)
* **Tests**: None covering bulk import

---

## 4. Class Structure Import
* **Domain**: School Admin
* **Entity**: Classes (`Class`), Student Class Enrollments (`StudentClassEnrollment`), Class Subjects (`ClassSubject`), Class Subject Teachers (`ClassSubjectTeacher`)
* **Frontend File**: [`frontend/src/views/admin/ClassesView.tsx`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/views/admin/ClassesView.tsx) (calls API via `handleConfirmFullImport`)
* **Backend Router**: `app/api/admin_class.py`
* **Endpoint**: `POST /api/v1/admin/classes/import-full`
* **Schema**: `ClassFullImportRequest`
* **Service**: `ClassService.create_class`, `ClassStructureService.enroll_student_to_class`, `ClassStructureService.assign_subject_to_class`, `ClassStructureService.assign_teacher_to_class_subject`
* **Repository**: `class_repository`, `subject_repository`, `teacher_subject_repository`
* **Parser**: Frontend custom parse mapping `Object.values(parsedClassesMap)`
* **Transaction Boundary**: Commits at the end of the controller call, but has nested try/except blocks swallowing row exceptions and calling `db.rollback()` for single rows, continuing the loop.
* **Tests**: Integration tests in `test_academic_administration_api.py`

---

## 5. Question Bank Import
* **Domain**: Teacher
* **Entity**: Question (`TeacherQuestion` model)
* **Frontend File**: [`frontend/src/views/teacher/QuestionBankView.tsx`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/views/teacher/QuestionBankView.tsx)
* **Backend Router**: `app/api/teacher.py`
* **Endpoint**: `POST /api/v1/teacher/questions` (Called in a loop sequentially per row)
* **Schema**: `QuestionCreateRequest`
* **Service**: `TeacherContentService.create_question`
* **Repository**: `teacher_question_repository.create`
* **Parser**: Frontend `readMultiSheetXlsxFile` utility
* **Transaction Boundary**: None (Committed per row)
* **Tests**: None covering bulk import

---

## 6. Question Package Import (Manual Composition)
* **Domain**: Teacher
* **Entity**: Question Bank Questions + Question Package Items (`QuestionPackageItem`)
* **Frontend File**: [`frontend/src/views/teacher/QuestionPackageDetailView.tsx`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/views/teacher/QuestionPackageDetailView.tsx)
* **Backend Router**: `app/api/teacher.py`
* **Endpoint**: `POST /api/v1/teacher/questions` (creates question in bank) + `POST /api/v1/teacher/packages/{id}/questions` (links to package) (called sequentially in loop)
* **Schema**: `QuestionCreateRequest` + `AddQuestionToPackageRequest`
* **Service**: `TeacherContentService.create_question`, `TeacherContentService.add_question_to_package`
* **Repository**: `teacher_question_repository`, `question_package_repository`
* **Parser**: Frontend `readMultiSheetXlsxFile`
* **Transaction Boundary**: None (Committed per row/action)
* **Tests**: None covering bulk import

---

## 7. SuperAdmin School Import
* **Domain**: SuperAdmin
* **Entity**: School Profile (`School` model) and Admin Credentials
* **Frontend File**: [`frontend/src/views/superadmin/SuperAdminSchoolsView.tsx`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/views/superadmin/SuperAdminSchoolsView.tsx) (onImportRow of `ImportExportBar`)
* **Backend Router**: `app/api/school.py`
* **Endpoint**: `POST /api/v1/schools` (Called in loop sequentially per row)
* **Schema**: `SchoolCreateRequest`
* **Service**: `SchoolService.create_school`
* **Repository**: `school_repository`
* **Parser**: Frontend `readXlsxFile`
* **Transaction Boundary**: None (Committed per row)
* **Tests**: None covering bulk import

---

## 8. Exam Schedule Import
* **Domain**: School Admin
* **Entity**: Exam Schedule (`ExamSchedule` model)
* **Frontend File**: [`frontend/src/views/admin/ExamSchedulesView.tsx`](file:///C:/Users/irul2/Downloads/Equigrade_x_Lockxam/frontend/src/views/admin/ExamSchedulesView.tsx)
* **Backend Router**: `app/api/admin_exam_schedule.py`
* **Endpoint**: `POST /api/v1/admin/exam-schedules/packages/{public_id}/import` (Receives entire row array)
* **Schema**: List of schedules in request body
* **Service**: `ExamScheduleService.import_schedules_xlsx`
* **Repository**: `exam_schedule_repository`, `class_repository`, `subject_repository`, `class_subject_teacher_repository`, `auth_repository`
* **Parser**: Frontend parses XLSX into JSON rows, sent in single request payload
* **Transaction Boundary**: Backend database transaction (commits only after all items succeed, rolls back on any validation error)
* **Tests**: Integrated tests in `test_academic_administration_api.py`
