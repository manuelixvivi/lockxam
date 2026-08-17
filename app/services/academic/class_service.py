from uuid import UUID

from sqlalchemy.orm import Session

from app.exceptions.base import BusinessException
from app.models.academic.class_entity import ClassEntity
from app.repositories.academic.academic_year_repository import (
    academic_year_repository,
)
from app.repositories.academic.class_repository import class_repository


class ClassService:
    @staticmethod
    def create_class(
        db: Session,
        school_id: int,
        academic_year_id: int,
        name: str,
        grade_level: str | None = None,
    ) -> ClassEntity:
        name_clean = name.strip()
        if not name_clean:
            raise BusinessException("Nama kelas wajib diisi.", status_code=400)

        year = academic_year_repository.get_by_id(db, academic_year_id)
        if not year or year.school_id != school_id:
            raise BusinessException("Tahun Ajaran tidak ditemukan.", status_code=404)

        # Invariant ACADEMIC-CLASS-001: Unique Class Name per (school_id, academic_year_id)
        existing = class_repository.get_by_name(db, school_id, academic_year_id, name_clean)
        if existing:
            raise BusinessException(
                f"Kelas '{name_clean}' sudah ada pada tahun ajaran '{year.name}'.",
                status_code=400,
            )

        new_class = ClassEntity(
            school_id=school_id,
            academic_year_id=academic_year_id,
            name=name_clean,
            grade_level=grade_level.strip() if grade_level else None,
            is_active=True,
        )
        return class_repository.create(db, new_class)

    @staticmethod
    def update_class(
        db: Session,
        school_id: int,
        public_id: UUID,
        name: str,
        grade_level: str | None = None,
        is_active: bool = True,
    ) -> ClassEntity:
        cls = class_repository.get_by_public_id(db, public_id)
        if not cls or cls.school_id != school_id:
            raise BusinessException("Kelas tidak ditemukan.", status_code=404)

        name_clean = name.strip()
        if not name_clean:
            raise BusinessException("Nama kelas wajib diisi.", status_code=400)

        if name_clean != cls.name:
            existing = class_repository.get_by_name(db, school_id, cls.academic_year_id, name_clean)
            if existing and existing.id != cls.id:
                raise BusinessException(
                    f"Kelas '{name_clean}' sudah ada pada tahun ajaran ini.",
                    status_code=400,
                )

        cls.name = name_clean
        cls.grade_level = grade_level.strip() if grade_level else None
        cls.is_active = is_active
        return class_repository.update(db, cls)

    @staticmethod
    def delete_class(db: Session, school_id: int, public_id: UUID) -> None:
        cls = class_repository.get_by_public_id(db, public_id)
        if not cls or cls.school_id != school_id:
            raise BusinessException("Kelas tidak ditemukan.", status_code=404)

        from app.models.academic.class_subject import ClassSubject
        from app.models.academic.class_subject_teacher import ClassSubjectTeacher
        from app.models.academic.student_class_enrollment import StudentClassEnrollment
        from app.models.academic.exam_schedule import ExamSchedule
        from app.models.exam.exam_session import ExamSession
        from app.models.exam.package_snapshot import ExamPackageSnapshot

        # 1. Clean active bindings
        db.query(ClassSubjectTeacher).filter(ClassSubjectTeacher.class_id == cls.id).delete(synchronize_session=False)
        db.query(ClassSubject).filter(ClassSubject.class_id == cls.id).delete(synchronize_session=False)
        db.query(StudentClassEnrollment).filter(
            StudentClassEnrollment.class_id == cls.id,
            StudentClassEnrollment.status == "ACTIVE"
        ).delete(synchronize_session=False)

        # 2. Check for past exam sessions with student attempt history
        linked_schedules = db.query(ExamSchedule).filter(ExamSchedule.class_id == cls.id).all()
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
            # Soft delete class so it disappears from active class management views while preserving student attempt history and grade reports intact
            cls.is_active = False
            db.flush()
        else:
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
                class_repository.delete(db, cls)
            except Exception:
                cls.is_active = False
                db.flush()

    @staticmethod
    def list_classes_by_year(
        db: Session,
        school_id: int,
        academic_year_id: int,
        is_active: bool | None = None,
    ) -> list[ClassEntity]:
        return class_repository.list_by_academic_year(
            db, school_id, academic_year_id, is_active=is_active
        )
