from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.exceptions.base import BusinessException
from app.models.academic.class_subject import ClassSubject
from app.models.academic.class_subject_teacher import ClassSubjectTeacher
from app.models.academic.enums import EnrollmentStatus
from app.models.academic.student_class_enrollment import StudentClassEnrollment
from app.models.security.auth_account import AuthAccount
from app.repositories.academic.class_repository import class_repository
from app.repositories.academic.class_subject_repository import (
    class_subject_repository,
)
from app.repositories.academic.class_subject_teacher_repository import (
    class_subject_teacher_repository,
)
from app.repositories.academic.student_enrollment_repository import (
    student_enrollment_repository,
)
from app.repositories.academic.subject_repository import subject_repository
from app.repositories.academic.teacher_subject_repository import (
    teacher_subject_repository,
)
from app.repositories.security.auth_repository import (
    auth_repository,
)


class ClassStructureService:
    # ── 1. Student Enrollment & Mutation ──

    @staticmethod
    def enroll_student_to_class(
        db: Session, school_id: int, student_id: int, class_id: int
    ) -> StudentClassEnrollment:
        cls = class_repository.get_by_id(db, class_id)
        if not cls or cls.school_id != school_id:
            raise BusinessException("Kelas tidak ditemukan.", status_code=404)

        student = auth_repository.get_by_id(db, student_id)
        if not student or student.school_id != school_id:
            raise BusinessException("Siswa tidak ditemukan.", status_code=404)

        # Invariant STUDENT-ACADEMIC-001: Year-scoped class membership with history preservation
        active_enrollment = student_enrollment_repository.get_active_enrollment(
            db, student_id, cls.academic_year_id
        )

        if active_enrollment:
            if active_enrollment.class_id == class_id:
                return active_enrollment  # Already active in this class

            # Mutasi Siswa: End previous active enrollment historically
            active_enrollment.status = EnrollmentStatus.TRANSFERRED.value
            active_enrollment.end_date = datetime.utcnow()
            db.flush()

        # Create new active enrollment
        new_enrollment = StudentClassEnrollment(
            school_id=school_id,
            student_id=student_id,
            class_id=class_id,
            academic_year_id=cls.academic_year_id,
            status=EnrollmentStatus.ACTIVE.value,
            start_date=datetime.utcnow(),
        )
        created = student_enrollment_repository.create(db, new_enrollment)

        # Update fast denormalized class_name on student profile
        student.class_name = cls.name
        db.flush()

        return created

    @staticmethod
    def remove_student_from_class(
        db: Session, school_id: int, student_id: int, class_id: int
    ) -> None:
        cls = class_repository.get_by_id(db, class_id)
        if not cls or cls.school_id != school_id:
            raise BusinessException("Kelas tidak ditemukan.", status_code=404)

        active_enrollment = student_enrollment_repository.get_active_enrollment(
            db, student_id, cls.academic_year_id
        )
        if active_enrollment and active_enrollment.class_id == class_id:
            active_enrollment.status = EnrollmentStatus.DROPPED.value
            active_enrollment.end_date = datetime.utcnow()
            db.flush()

            student = auth_repository.get_by_id(db, student_id)
            if student:
                student.class_name = None
                db.flush()

    @staticmethod
    def list_students_in_class(
        db: Session, class_id: int
    ) -> list[StudentClassEnrollment]:
        return student_enrollment_repository.list_by_class(
            db, class_id, status=[
                EnrollmentStatus.ACTIVE.value,
                EnrollmentStatus.COMPLETED.value,
                EnrollmentStatus.TRANSFERRED.value,
            ]
        )

    @staticmethod
    def get_student_history(
        db: Session, student_id: int
    ) -> list[StudentClassEnrollment]:
        return student_enrollment_repository.list_history_by_student(db, student_id)

    # ── 2. Class Subject & Teacher Assignment ──

    @staticmethod
    def assign_subject_to_class(
        db: Session, school_id: int, class_id: int, subject_id: int
    ) -> ClassSubject:
        cls = class_repository.get_by_id(db, class_id)
        if not cls or cls.school_id != school_id:
            raise BusinessException("Kelas tidak ditemukan.", status_code=404)

        subj = subject_repository.get_by_id(db, subject_id)
        if not subj or subj.school_id != school_id:
            raise BusinessException("Mata pelajaran tidak ditemukan.", status_code=404)

        return class_subject_repository.assign(db, school_id, class_id, subject_id)

    @staticmethod
    def remove_subject_from_class(
        db: Session, school_id: int, class_id: int, subject_id: int
    ) -> None:
        cls = class_repository.get_by_id(db, class_id)
        if not cls or cls.school_id != school_id:
            raise BusinessException("Kelas tidak ditemukan.", status_code=404)

        subj = subject_repository.get_by_id(db, subject_id)
        if not subj or subj.school_id != school_id:
            raise BusinessException("Mata pelajaran tidak ditemukan.", status_code=404)

        # Unassign teacher from class subject if any
        class_subject_teacher_repository.unassign(db, class_id, subject_id)

        # Unassign subject from class
        class_subject_repository.unassign(db, class_id, subject_id)

    @staticmethod
    def assign_teacher_to_class_subject(
        db: Session, school_id: int, class_id: int, subject_id: int, teacher_id: int
    ) -> ClassSubjectTeacher:
        cls = class_repository.get_by_id(db, class_id)
        if not cls or cls.school_id != school_id:
            raise BusinessException("Kelas tidak ditemukan.", status_code=404)

        subj = subject_repository.get_by_id(db, subject_id)
        if not subj or subj.school_id != school_id:
            raise BusinessException("Mata pelajaran tidak ditemukan.", status_code=404)

        teacher = auth_repository.get_by_id(db, teacher_id)
        if not teacher or teacher.school_id != school_id:
            raise BusinessException("Guru tidak ditemukan.", status_code=404)

        # Ensure TeacherSubject competency exists — NO AUTO-REGISTRATION
        competency = teacher_subject_repository.get_by_teacher_and_subject(
            db, teacher_id, subject_id
        )
        if not competency:
            raise BusinessException(
                "Guru bersangkutan belum memiliki kompetensi untuk mata pelajaran ini (TeacherSubject missing). "
                "Tetapkan kompetensi mata pelajaran pada profil guru terlebih dahulu.",
                status_code=400,
            )

        # Ensure ClassSubject entry exists
        class_subject_repository.assign(db, school_id, class_id, subject_id)

        # Create or update ClassSubjectTeacher
        result = class_subject_teacher_repository.assign_or_update(
            db, school_id, class_id, subject_id, teacher_id
        )

        # subjects_taught sync intentionally removed.
        # TeacherSubject is the ONLY authority for competency.
        # The derived projection is computed at read-time in SchoolStaffService.list_teachers().

        return result

    @staticmethod
    def list_class_subject_teachers(
        db: Session, class_id: int
    ) -> list[ClassSubjectTeacher]:
        return class_subject_teacher_repository.list_by_class(db, class_id)

    @staticmethod
    def import_classes_xlsx(
        db: Session,
        school_id: int,
        academic_year_id: int,
        classes_data: list[dict],
    ) -> tuple[bool, list[ClassSubjectTeacher], list[dict]]:
        from app.repositories.academic.academic_year_repository import academic_year_repository
        from app.models.security.enums import UserRole

        # 1. Verify academic_year_id exists and belongs to school
        academic_year = academic_year_repository.get_by_id(db, academic_year_id)
        if not academic_year or academic_year.school_id != school_id:
            raise BusinessException(
                "Tahun ajaran tidak ditemukan atau bukan milik sekolah Anda.",
                status_code=400
            )

        errors = []
        validated_batch_data = []

        # Duplicate checking maps within the XLSX file
        seen_class_subjects = set()
        seen_class_subject_teachers = set()

        # First Pass: Validate ALL rows/entities before persistence
        for class_idx, cls_item in enumerate(classes_data):
            class_row_fallback = class_idx + 2
            class_name = str(cls_item.get("name") or "").strip()
            grade_level = cls_item.get("grade_level")

            if not class_name:
                errors.append({
                    "row": class_row_fallback,
                    "field": "name",
                    "value": "",
                    "code": "CLASS_NAME_REQUIRED",
                    "message": "Nama Kelas/Rombel wajib diisi."
                })
                continue

            # Resolve class using school_id + academic_year_id + class_name
            class_entity = class_repository.get_by_name(db, school_id, academic_year_id, class_name)
            if not class_entity:
                # Check if it exists in another academic year just to be specific in error message
                exists_elsewhere = class_repository.get_any_by_name_in_school(db, school_id, class_name)
                if exists_elsewhere:
                    message = f"Kelas '{class_name}' ditemukan di tahun ajaran lain, tetapi belum terdaftar pada Tahun Ajaran yang dipilih."
                else:
                    message = f"Kelas '{class_name}' tidak ditemukan pada Tahun Ajaran yang dipilih."
                
                errors.append({
                    "row": class_row_fallback,
                    "field": "name",
                    "value": class_name,
                    "code": "CLASS_NOT_FOUND",
                    "message": message
                })
                # We continue parsing subjects and students of this class to gather more potential errors

            class_id_for_key = class_entity.id if class_entity else class_name

            # Resolve students
            validated_students = []
            students_list = cls_item.get("students") or []
            for st_idx, st in enumerate(students_list):
                st_row = st.get("row_num") or class_row_fallback
                nisn = str(st.get("nisn") or "").strip()
                nis = str(st.get("nis") or "").strip()
                username = str(st.get("username") or "").strip()

                if not nisn and not nis and not username:
                    errors.append({
                        "row": st_row,
                        "field": "student",
                        "value": "",
                        "code": "STUDENT_IDENTIFIER_REQUIRED",
                        "message": "Salah satu dari NISN, NIS, atau Username wajib diisi untuk mendeteksi identitas siswa."
                    })
                    continue

                student = None
                if nisn:
                    student = auth_repository.get_by_nisn(db, school_id, nisn)
                if not student and nis:
                    student = auth_repository.get_by_nis(db, school_id, nis)
                if not student and username:
                    student = auth_repository.get_by_username(db, username)
                    if student and (student.school_id != school_id or student.role not in [UserRole.STUDENT, "STUDENT"]):
                        student = None

                if not student:
                    val_str = f"NISN: {nisn}" if nisn else (f"NIS: {nis}" if nis else f"Username: {username}")
                    errors.append({
                        "row": st_row,
                        "field": "student",
                        "value": val_str,
                        "code": "STUDENT_NOT_FOUND",
                        "message": f"Siswa dengan {val_str} tidak ditemukan atau bukan milik sekolah Anda."
                    })
                else:
                    validated_students.append(student)

            # Resolve subjects & teachers
            validated_subjects_teachers = []
            subjects_list = cls_item.get("subjects") or []
            for sb_idx, sb in enumerate(subjects_list):
                sb_row = sb.get("row_num") or class_row_fallback
                s_code = str(sb.get("subject_code") or "").strip()
                t_code = str(sb.get("teacher_code") or "").strip()

                if not s_code:
                    errors.append({
                        "row": sb_row,
                        "field": "subject_code",
                        "value": "",
                        "code": "SUBJECT_CODE_REQUIRED",
                        "message": "Kode Mata Pelajaran wajib diisi."
                    })
                    continue

                # Resolve Subject (must belong to school)
                subject = subject_repository.get_by_code_or_name(db, school_id, s_code)
                if not subject:
                    errors.append({
                        "row": sb_row,
                        "field": "subject_code",
                        "value": s_code,
                        "code": "SUBJECT_NOT_FOUND",
                        "message": f"Mata pelajaran '{s_code}' tidak ditemukan atau bukan milik sekolah Anda."
                    })
                    continue

                if not t_code:
                    errors.append({
                        "row": sb_row,
                        "field": "teacher_code",
                        "value": "",
                        "code": "TEACHER_CODE_REQUIRED",
                        "message": "Identitas/Kode Guru pengampu wajib diisi."
                    })
                    continue

                # Resolve Teacher (must belong to school)
                teacher = auth_repository.get_teacher_by_code(db, school_id, t_code)
                if not teacher:
                    teacher = auth_repository.get_by_nip(db, school_id, t_code)
                if not teacher:
                    teacher = auth_repository.get_by_username(db, t_code)
                    if teacher and (teacher.school_id != school_id or teacher.role not in [UserRole.TEACHER, "TEACHER"]):
                        teacher = None

                if not teacher:
                    errors.append({
                        "row": sb_row,
                        "field": "teacher_code",
                        "value": t_code,
                        "code": "TEACHER_NOT_FOUND",
                        "message": f"Guru dengan kode/NIP/username '{t_code}' tidak ditemukan atau bukan milik sekolah Anda."
                    })
                    continue

                # Check TeacherSubject competency (No Auto-Competency Creation)
                competency = teacher_subject_repository.get_by_teacher_and_subject(db, teacher.id, subject.id)
                if not competency:
                    errors.append({
                        "row": sb_row,
                        "field": "teacher_code",
                        "value": teacher.name or teacher.username,
                        "code": "TEACHER_NOT_COMPETENT",
                        "message": f"Guru '{teacher.name or teacher.username}' belum memiliki kompetensi untuk mengampu mata pelajaran '{subject.name}'."
                    })
                    continue

                # Duplicate check: Class + Subject in the Excel file
                cs_key = (class_id_for_key, subject.id)
                if cs_key in seen_class_subjects:
                    errors.append({
                        "row": sb_row,
                        "field": "subject_code",
                        "value": s_code,
                        "code": "DUPLICATE_CLASS_SUBJECT_IN_FILE",
                        "message": f"Mata pelajaran '{subject.name}' ganda untuk kelas '{class_name}' di dalam file Excel."
                    })
                else:
                    seen_class_subjects.add(cs_key)

                # Duplicate check: Class + Subject + Teacher in the Excel file
                cst_key = (class_id_for_key, subject.id, teacher.id)
                if cst_key in seen_class_subject_teachers:
                    errors.append({
                        "row": sb_row,
                        "field": "teacher_code",
                        "value": t_code,
                        "code": "DUPLICATE_CLASS_SUBJECT_TEACHER_IN_FILE",
                        "message": f"Guru '{teacher.name or teacher.username}' ditugaskan ganda untuk mata pelajaran '{subject.name}' di kelas '{class_name}' di dalam file Excel."
                    })
                else:
                    seen_class_subject_teachers.add(cst_key)

                validated_subjects_teachers.append({
                    "subject": subject,
                    "teacher": teacher
                })

            validated_batch_data.append({
                "class_entity": class_entity,
                "students": validated_students,
                "subjects_teachers": validated_subjects_teachers
            })

        if errors:
            return False, [], errors

        # Second Pass: Atomic Persistence under transaction/savepoint
        created_relations = []
        try:
            savepoint = db.begin_nested()

            for batch in validated_batch_data:
                cls_entity = batch["class_entity"]

                # Enroll students
                for student in batch["students"]:
                    ClassStructureService.enroll_student_to_class(
                        db=db,
                        school_id=school_id,
                        student_id=student.id,
                        class_id=cls_entity.id
                    )

                # Assign subjects and teachers
                for item in batch["subjects_teachers"]:
                    subject = item["subject"]
                    teacher = item["teacher"]

                    # Ensure ClassSubject entry exists
                    class_subject_repository.assign(db, school_id, cls_entity.id, subject.id)

                    # Create or update ClassSubjectTeacher
                    cst = class_subject_teacher_repository.assign_or_update(
                        db, school_id, cls_entity.id, subject.id, teacher.id
                    )
                    created_relations.append(cst)

            savepoint.commit()
            return True, created_relations, []

        except Exception as e:
            savepoint.rollback()
            db.rollback()
            from app.logging.logger import logger
            logger.error(f"Class structure bulk import persistence failure: {str(e)}", exc_info=True)
            raise BusinessException(
                "Gagal melakukan penyimpanan data ke database. Terjadi kesalahan internal pada server.",
                status_code=500,
            )

