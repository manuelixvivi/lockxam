from uuid import UUID

from sqlalchemy.orm import Session

from app.exceptions.base import BusinessException
from app.models.academic.subject import Subject
from app.models.academic.teacher_subject import TeacherSubject
from app.models.security.auth_account import AuthAccount
from app.repositories.academic.subject_repository import subject_repository
from app.repositories.academic.teacher_subject_repository import (
    teacher_subject_repository,
)
from app.repositories.security.auth_repository import (
    auth_repository,
)


class SubjectService:
    @staticmethod
    def create_subject(
        db: Session,
        school_id: int,
        code: str,
        name: str,
        description: str | None = None,
    ) -> Subject:
        code_clean = code.strip().upper()
        name_clean = name.strip()
        if not code_clean or not name_clean:
            raise BusinessException("Kode dan Nama Mata Pelajaran wajib diisi.", status_code=400)

        existing = subject_repository.get_by_code(db, school_id, code_clean)
        if existing:
            raise BusinessException(
                f"Mata pelajaran dengan kode '{code_clean}' sudah terdaftar di sekolah ini.",
                status_code=400,
            )

        subj = Subject(
            school_id=school_id,
            code=code_clean,
            name=name_clean,
            description=description.strip() if description else None,
            is_active=True,
        )
        return subject_repository.create(db, subj)

    @staticmethod
    def update_subject(
        db: Session,
        school_id: int,
        public_id: UUID,
        code: str,
        name: str,
        description: str | None = None,
        is_active: bool = True,
    ) -> Subject:
        subj = subject_repository.get_by_public_id(db, public_id)
        if not subj or subj.school_id != school_id:
            raise BusinessException("Mata pelajaran tidak ditemukan.", status_code=404)

        code_clean = code.strip().upper()
        name_clean = name.strip()
        if not code_clean or not name_clean:
            raise BusinessException("Kode dan Nama Mata Pelajaran wajib diisi.", status_code=400)

        if code_clean != subj.code:
            existing = subject_repository.get_by_code(db, school_id, code_clean)
            if existing and existing.id != subj.id:
                raise BusinessException(
                    f"Mata pelajaran dengan kode '{code_clean}' sudah terdaftar di sekolah ini.",
                    status_code=400,
                )

        subj.code = code_clean
        subj.name = name_clean
        subj.description = description.strip() if description else None
        subj.is_active = is_active
        return subject_repository.update(db, subj)

    @staticmethod
    def delete_subject(db: Session, school_id: int, public_id: UUID) -> None:
        subj = subject_repository.get_by_public_id(db, public_id)
        if not subj or subj.school_id != school_id:
            raise BusinessException("Mata pelajaran tidak ditemukan.", status_code=404)

        from app.models.academic.teacher_subject import TeacherSubject
        from app.models.academic.class_subject import ClassSubject
        from app.models.academic.class_subject_teacher import ClassSubjectTeacher
        from app.models.academic.exam_schedule import ExamSchedule
        from app.models.exam.exam_session import ExamSession
        from app.models.exam.package_snapshot import ExamPackageSnapshot

        # 1. Clean active class & teacher bindings
        db.query(TeacherSubject).filter(TeacherSubject.subject_id == subj.id).delete(synchronize_session=False)
        db.query(ClassSubjectTeacher).filter(ClassSubjectTeacher.subject_id == subj.id).delete(synchronize_session=False)
        db.query(ClassSubject).filter(ClassSubject.subject_id == subj.id).delete(synchronize_session=False)

        # 2. Check for active/completed exam sessions with student attempts
        linked_schedules = db.query(ExamSchedule).filter(ExamSchedule.subject_id == subj.id).all()
        has_historical_sessions = False
        if linked_schedules:
            sch_ids = [s.id for s in linked_schedules]
            hist_sess = db.query(ExamSession).filter(
                ExamSession.schedule_id.in_(sch_ids),
                ExamSession.status.in_(["ACTIVE", "COMPLETED"])
            ).first()
            if hist_sess:
                has_historical_sessions = True

        from app.models.academic.exam_snapshot import ExamSnapshot

        if has_historical_sessions:
            # Soft delete: deactivate subject so it vanishes from active lists & drop-downs while preserving past exam session records intact
            subj.is_active = False
            db.flush()
        else:
            # Clean non-historical session snapshots and schedules
            for sch in linked_schedules:
                db.query(ExamSnapshot).filter(ExamSnapshot.exam_schedule_id == sch.id).delete(synchronize_session=False)
                sessions = db.query(ExamSession).filter(ExamSession.schedule_id == sch.id).all()
                for sess in sessions:
                    snapshots = db.query(ExamPackageSnapshot).filter(ExamPackageSnapshot.exam_session_id == sess.id).all()
                    for snap in snapshots:
                        db.delete(snap)
                    db.delete(sess)
                db.delete(sch)

            db.flush()
            try:
                subject_repository.delete(db, subj)
            except Exception:
                subj.is_active = False
                db.flush()

    @staticmethod
    def list_subjects(
        db: Session, school_id: int, is_active: bool | None = None
    ) -> list[Subject]:
        return subject_repository.list_by_school(db, school_id, is_active=is_active)

    @staticmethod
    def assign_teacher_competency(
        db: Session, school_id: int, teacher_id: int, subject_id: int
    ) -> TeacherSubject:
        teacher = auth_repository.get_by_id(db, teacher_id)
        if not teacher or teacher.school_id != school_id:
            raise BusinessException("Akun guru tidak ditemukan.", status_code=404)

        subj = subject_repository.get_by_id(db, subject_id)
        if not subj or subj.school_id != school_id:
            raise BusinessException("Mata pelajaran tidak ditemukan.", status_code=404)

        # Sync with profile subjects_taught list
        current_taught = list(teacher.subjects_taught or [])
        if subj.name not in current_taught:
            current_taught.append(subj.name)
            teacher.subjects_taught = current_taught

        return teacher_subject_repository.assign(db, school_id, teacher_id, subject_id)

    @staticmethod
    def unassign_teacher_competency(
        db: Session, teacher_id: int, subject_id: int
    ) -> bool:
        teacher = auth_repository.get_by_id(db, teacher_id)
        subj = subject_repository.get_by_id(db, subject_id)

        if teacher and subj and teacher.subjects_taught:
            teacher.subjects_taught = [
                s for s in teacher.subjects_taught
                if s.strip().lower() != subj.name.strip().lower() and s.strip().lower() != subj.code.strip().lower()
            ]

        return teacher_subject_repository.unassign(db, teacher_id, subject_id)

    @staticmethod
    def list_qualified_teachers_for_subject(
        db: Session, school_id: int, subject_id: int
    ) -> list[AuthAccount]:
        subj = subject_repository.get_by_id(db, subject_id)
        if not subj or subj.school_id != school_id:
            return []

        # 1. Teachers explicitly registered in teacher_subjects table
        teacher_ids = teacher_subject_repository.list_teacher_ids_by_subject(
            db, school_id, subject_id
        )
        qualified_teachers = [
            t
            for t in [auth_repository.get_by_id(db, tid) for tid in teacher_ids]
            if t and t.is_active and t.school_id == school_id
        ]
        qualified_ids = {t.id for t in qualified_teachers}

        # 2. Also check teachers whose profile subjects_taught contains subject name or code (case-insensitive)
        all_school_teachers = auth_repository.list_teachers_by_school(db, school_id)
        for t in all_school_teachers:
            if t.id not in qualified_ids and t.is_active:
                taught = [s.strip().lower() for s in (t.subjects_taught or [])]
                if subj.name.strip().lower() in taught or subj.code.strip().lower() in taught:
                    # Auto-sync to teacher_subject table for persistent relational integrity
                    teacher_subject_repository.assign(db, school_id, t.id, subj.id)
                    qualified_teachers.append(t)
                    qualified_ids.add(t.id)

        return qualified_teachers
