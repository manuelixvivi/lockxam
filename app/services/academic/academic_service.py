from datetime import datetime
from uuid import UUID

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.exceptions.base import AcademicValidationException, BusinessException
from app.models.academic.academic_semester import AcademicSemester
from app.models.academic.academic_year import AcademicYear
from app.models.academic.enums import AcademicStatus
from app.repositories.academic.academic_semester_repository import academic_semester_repository
from app.repositories.academic.academic_year_repository import academic_year_repository
from app.repositories.school.school_repository import school_repository


class AcademicService:

    @staticmethod
    def verify_archive_checklist(db: Session, academic_year_id: int) -> list[str]:
        errors = []
        inspector = inspect(db.connection())

        # BR-ACA-011: Archive Validation Checklist (Dynamic table existence checks)
        # 1. Exam sessions check
        if inspector.has_table("exam_sessions"):
            active_exams = db.execute(
                text(
                    "SELECT COUNT(*) FROM exam_sessions "
                    "WHERE academic_year_id = :year_id "
                    "AND CAST(status AS VARCHAR) IN ('ACTIVE', 'ON_GOING')"
                ),
                {"year_id": academic_year_id},
            ).scalar()
            if active_exams and active_exams > 0:
                errors.append("Active or ongoing exam sessions exist in this academic period.")

        # 2. Draft grades check
        if inspector.has_table("grades"):
            draft_grades = db.execute(
                text(
                    "SELECT COUNT(*) FROM grades "
                    "WHERE academic_year_id = :year_id "
                    "AND status = 'DRAFT'"
                ),
                {"year_id": academic_year_id},
            ).scalar()
            if draft_grades and draft_grades > 0:
                errors.append("Draft academic grades exist in this academic period.")

        # 3. Active AI evaluation tasks check
        if inspector.has_table("ai_evaluations"):
            active_ai = db.execute(
                text(
                    "SELECT COUNT(*) FROM ai_evaluations "
                    "WHERE academic_year_id = :year_id "
                    "AND status = 'PROCESSING'"
                ),
                {"year_id": academic_year_id},
            ).scalar()
            if active_ai and active_ai > 0:
                errors.append(
                    "Active AI evaluation pipelines are running for this academic period."
                )

        return errors

    @staticmethod
    def create_academic_year(
        db: Session, school_id: int, name: str, start_date: datetime, end_date: datetime
    ) -> AcademicYear:
        # Validate school exists
        school = school_repository.get_by_id(db, school_id)
        if not school:
            raise BusinessException("School not found", status_code=404)

        if start_date >= end_date:
            raise BusinessException("Start date must be before end date", status_code=400)

        # BR-ACA-005: Date overlap verification
        if academic_year_repository.check_overlap(db, school_id, start_date, end_date):
            raise BusinessException(
                "Academic Year date range overlaps with an existing period", status_code=400
            )

        year = AcademicYear(
            school_id=school_id,
            name=name,
            start_date=start_date,
            end_date=end_date,
            status=AcademicStatus.PLANNED.value,
        )
        academic_year_repository.create(db, year)
        return year

    @staticmethod
    def delete_academic_year(db: Session, public_id: UUID) -> None:
        year = academic_year_repository.get_by_public_id(db, public_id)
        if not year:
            raise BusinessException("Academic Year not found", status_code=404)

        # BR-ACA-015: Strict deletion boundaries (only PLANNED status allowed)
        if year.status != AcademicStatus.PLANNED.value:
            raise BusinessException(
                f"Cannot delete Academic Year in status {year.status}", status_code=400
            )

        academic_year_repository.delete(db, year)

    @staticmethod
    def close_academic_year(db: Session, public_id: UUID) -> AcademicYear:
        # BR-ACA-010: Trigger closing sequence -> status PENDING_ARCHIVE
        year = academic_year_repository.get_by_public_id(db, public_id)
        if not year:
            raise BusinessException("Academic Year not found", status_code=404)

        if year.status != AcademicStatus.ACTIVE.value:
            raise BusinessException(
                f"Cannot close Academic Year in status {year.status}", status_code=400
            )

        year.status = AcademicStatus.PENDING_ARCHIVE.value
        for sem in year.semesters:
            if sem.status == AcademicStatus.ACTIVE.value:
                sem.status = AcademicStatus.PENDING_ARCHIVE.value
                academic_semester_repository.update(db, sem)

        academic_year_repository.update(db, year)

        # Run validation engine checklist (BR-ACA-011)
        errors = AcademicService.verify_archive_checklist(db, year.id)
        if errors:
            db.flush()
            raise AcademicValidationException(errors)

        return year

    @staticmethod
    def finalize_archive(db: Session, public_id: UUID) -> AcademicYear:
        year = academic_year_repository.get_by_public_id(db, public_id)
        if not year:
            raise BusinessException("Academic Year not found", status_code=404)

        if year.status != AcademicStatus.PENDING_ARCHIVE.value:
            raise BusinessException(
                f"Cannot finalize archive for Academic Year in status {year.status}",
                status_code=400,
            )

        # Double check validation checklist
        errors = AcademicService.verify_archive_checklist(db, year.id)
        if errors:
            raise AcademicValidationException(errors)

        year.status = AcademicStatus.ARCHIVED.value
        for sem in year.semesters:
            if sem.status == AcademicStatus.PENDING_ARCHIVE.value:
                sem.status = AcademicStatus.ARCHIVED.value
                academic_semester_repository.update(db, sem)

        academic_year_repository.update(db, year)
        return year

    @staticmethod
    def rollover_academic_year(
        db: Session, school_id: int, new_year_public_id: UUID
    ) -> AcademicYear:
        # BR-ACA-002, BR-ACA-006: Rollover atomicity
        new_year = academic_year_repository.get_by_public_id(db, new_year_public_id)
        if not new_year:
            raise BusinessException("Target Academic Year not found", status_code=404)

        if new_year.school_id != school_id:
            raise BusinessException(
                "Target Academic Year does not belong to your school", status_code=403
            )

        if new_year.status != AcademicStatus.PLANNED.value:
            raise BusinessException(
                f"Target Academic Year must be in PLANNED status, got {new_year.status}",
                status_code=400,
            )

        # 1. Close current active year
        current_active = academic_year_repository.get_active_or_pending_year(db, school_id)
        if current_active:
            # Change status to PENDING_ARCHIVE and verify checklist
            current_active.status = AcademicStatus.PENDING_ARCHIVE.value
            for sem in current_active.semesters:
                if sem.status == AcademicStatus.ACTIVE.value:
                    sem.status = AcademicStatus.PENDING_ARCHIVE.value
                    academic_semester_repository.update(db, sem)
            academic_year_repository.update(db, current_active)
            db.flush()

            # Verify checklist
            errors = AcademicService.verify_archive_checklist(db, current_active.id)
            if errors:
                # Keep in PENDING_ARCHIVE for manual review
                db.flush()
                raise AcademicValidationException(errors)

            # Verification passed, finalize archiving (BR-ACA-012)
            current_active.status = AcademicStatus.ARCHIVED.value
            for sem in current_active.semesters:
                if sem.status == AcademicStatus.PENDING_ARCHIVE.value:
                    sem.status = AcademicStatus.ARCHIVED.value
                    academic_semester_repository.update(db, sem)
            academic_year_repository.update(db, current_active)

        # 2. Automatically promote classes & active students to next grade level for new academic year
        if current_active:
            AcademicService.promote_classes_and_students_for_rollover(
                db=db, school_id=school_id, old_year_id=current_active.id, new_year_id=new_year.id
            )

        # 3. Activate target planned year
        new_year.status = AcademicStatus.ACTIVE.value
        academic_year_repository.update(db, new_year)

        # Activate its first semester if any
        if new_year.semesters:
            first_sem = sorted(new_year.semesters, key=lambda s: s.id)[0]
            first_sem.status = AcademicStatus.ACTIVE.value
            academic_semester_repository.update(db, first_sem)

        return new_year

    @staticmethod
    def promote_classes_and_students_for_rollover(
        db: Session, school_id: int, old_year_id: int, new_year_id: int
    ) -> dict:
        """
        Automates class & student grade promotion during Academic Year rollover.
        SD: I->II->III->IV->V->VI->LULUS
        SMP: VII->VIII->IX->LULUS
        SMA/SMK: X->XI->XII->LULUS
        """
        from app.models.academic.class_entity import ClassEntity
        from app.models.academic.student_class_enrollment import StudentClassEnrollment
        from app.models.academic.enums import EnrollmentStatus
        from app.models.security.auth_account import AuthAccount
        from app.services.academic.class_structure_service import ClassStructureService

        promotion_map = {
            "I": "II", "II": "III", "III": "IV", "IV": "V", "V": "VI", "VI": "LULUS",
            "VII": "VIII", "VIII": "IX", "IX": "LULUS",
            "7": "8", "8": "9", "9": "LULUS",
            "X": "XI", "XI": "XII", "XII": "LULUS",
            "10": "11", "11": "12", "12": "LULUS",
        }

        old_classes = db.query(ClassEntity).filter(
            ClassEntity.school_id == school_id,
            ClassEntity.academic_year_id == old_year_id,
            ClassEntity.is_active == True,
        ).all()

        promoted_classes_count = 0
        graduated_students_count = 0
        promoted_students_count = 0

        for old_cls in old_classes:
            gl = (old_cls.grade_level or "X").strip().upper()
            next_gl = promotion_map.get(gl, "LULUS")

            active_enrollments = db.query(StudentClassEnrollment).filter(
                StudentClassEnrollment.class_id == old_cls.id,
                StudentClassEnrollment.status == EnrollmentStatus.ACTIVE.value,
            ).all()

            if next_gl == "LULUS":
                for enr in active_enrollments:
                    enr.status = EnrollmentStatus.GRADUATED.value
                    enr.end_date = datetime.utcnow()
                    st = db.query(AuthAccount).filter(AuthAccount.id == enr.student_id).first()
                    if st:
                        st.class_name = "LULUS (Alumni)"
                    graduated_students_count += 1
            else:
                rombel_suffix = old_cls.name
                if old_cls.grade_level and rombel_suffix.upper().startswith(old_cls.grade_level.upper()):
                    rombel_suffix = rombel_suffix[len(old_cls.grade_level):].strip()

                new_class_name = f"{next_gl} {rombel_suffix}".strip()

                new_cls = db.query(ClassEntity).filter(
                    ClassEntity.school_id == school_id,
                    ClassEntity.academic_year_id == new_year_id,
                    ClassEntity.name == new_class_name,
                ).first()

                if not new_cls:
                    new_cls = ClassEntity(
                        school_id=school_id,
                        academic_year_id=new_year_id,
                        name=new_class_name,
                        grade_level=next_gl,
                        is_active=True,
                    )
                    db.add(new_cls)
                    db.flush()

                promoted_classes_count += 1

                for enr in active_enrollments:
                    ClassStructureService.enroll_student_to_class(
                        db=db, school_id=school_id, student_id=enr.student_id, class_id=new_cls.id
                    )
                    promoted_students_count += 1

        db.flush()
        return {
            "promoted_classes_count": promoted_classes_count,
            "promoted_students_count": promoted_students_count,
            "graduated_students_count": graduated_students_count,
        }

    @staticmethod
    def create_academic_semester(
        db: Session, academic_year_id: int, code: str, display_name: str
    ) -> AcademicSemester:
        # Validate year exists
        year = academic_year_repository.get_by_id(db, academic_year_id)
        if not year:
            raise BusinessException("Academic Year not found", status_code=404)

        if code not in ["ODD", "EVEN"]:
            raise BusinessException("Semester code must be ODD or EVEN", status_code=400)

        sem = AcademicSemester(
            academic_year_id=academic_year_id,
            code=code,
            display_name=display_name,
            status=AcademicStatus.PLANNED.value,
        )
        academic_semester_repository.create(db, sem)
        return sem

    @staticmethod
    def activate_semester(db: Session, public_id: UUID) -> AcademicSemester:
        # BR-ACA-003, BR-ACA-004: Activate semester within parent active year
        sem = academic_semester_repository.get_by_public_id(db, public_id)
        if not sem:
            raise BusinessException("Academic Semester not found", status_code=404)

        parent_year = academic_year_repository.get_by_id(db, sem.academic_year_id)
        if not parent_year or parent_year.status != AcademicStatus.ACTIVE.value:
            raise BusinessException(
                "Cannot activate semester in a non-active Academic Year", status_code=400
            )

        if sem.status == AcademicStatus.ACTIVE.value:
            return sem

        # Archive current active semester
        current_active = academic_semester_repository.get_active_semester(db, parent_year.school_id)
        if current_active and current_active.academic_year_id == parent_year.id:
            current_active.status = AcademicStatus.ARCHIVED.value
            academic_semester_repository.update(db, current_active)

        sem.status = AcademicStatus.ACTIVE.value
        academic_semester_repository.update(db, sem)
        return sem
