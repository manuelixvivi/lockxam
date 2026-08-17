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
            db, class_id, status=EnrollmentStatus.ACTIVE.value
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

        # Invariant CLASS-TEACHER-001: Ensure teacher_subjects record exists (auto-register if missing)
        competency = teacher_subject_repository.get_by_teacher_and_subject(
            db, teacher_id, subject_id
        )
        if not competency:
            # Admin assignment is authoritative — auto-register teacher competency
            competency = teacher_subject_repository.assign(db, school_id, teacher_id, subject_id)

        # Ensure ClassSubject entry exists
        class_subject_repository.assign(db, school_id, class_id, subject_id)

        # Create or update ClassSubjectTeacher
        result = class_subject_teacher_repository.assign_or_update(
            db, school_id, class_id, subject_id, teacher_id
        )

        # ── Sync subjects_taught JSON on teacher profile ──
        # Rebuild from teacher_subjects relational table for consistency
        all_teacher_subjects = teacher_subject_repository.list_by_teacher(db, teacher_id)
        synced_names = []
        for ts in all_teacher_subjects:
            s = subject_repository.get_by_id(db, ts.subject_id)
            if s:
                synced_names.append(s.name)
        if set(synced_names) != set(teacher.subjects_taught or []):
            teacher.subjects_taught = synced_names
            db.flush()

        return result

    @staticmethod
    def list_class_subject_teachers(
        db: Session, class_id: int
    ) -> list[ClassSubjectTeacher]:
        return class_subject_teacher_repository.list_by_class(db, class_id)
