from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.academic.academic_year import AcademicYear
from app.models.academic.enums import AcademicStatus
from app.repositories.base_repository import BaseRepository


class AcademicYearRepository(BaseRepository[AcademicYear]):
    def __init__(self):
        super().__init__(AcademicYear)

    def get_active_year(self, db: Session, school_id: int) -> AcademicYear | None:
        return db.scalar(
            select(AcademicYear).where(
                AcademicYear.school_id == school_id,
                AcademicYear.status == AcademicStatus.ACTIVE.value,
            )
        )

    def get_active_or_pending_year(self, db: Session, school_id: int) -> AcademicYear | None:
        return db.scalar(
            select(AcademicYear).where(
                AcademicYear.school_id == school_id,
                AcademicYear.status.in_(
                    [AcademicStatus.ACTIVE.value, AcademicStatus.PENDING_ARCHIVE.value]
                ),
            )
        )

    def get_by_public_id(self, db: Session, public_id: UUID) -> AcademicYear | None:
        return db.scalar(select(AcademicYear).where(AcademicYear.public_id == public_id))

    def get_years_by_school(self, db: Session, school_id: int) -> list[AcademicYear]:
        return list(
            db.scalars(
                select(AcademicYear)
                .where(AcademicYear.school_id == school_id)
                .order_by(AcademicYear.start_date.desc())
            ).all()
        )

    def check_overlap(
        self,
        db: Session,
        school_id: int,
        start_date: datetime,
        end_date: datetime,
        exclude_id: int | None = None,
    ) -> bool:
        query = select(AcademicYear).where(
            AcademicYear.school_id == school_id,
            and_(AcademicYear.start_date < end_date, AcademicYear.end_date > start_date),
        )
        if exclude_id is not None:
            query = query.where(AcademicYear.id != exclude_id)

        overlap_rec = db.scalar(query)
        return overlap_rec is not None

    def verify_archive_checklist(self, db: Session, academic_year_id: int) -> list[str]:
        from sqlalchemy import inspect, text
        errors = []
        inspector = inspect(db.connection())

        if inspector.has_table("exam_sessions"):
            active_exams = db.execute(
                text(
                    "SELECT COUNT(*) FROM exam_sessions es "
                    "JOIN exam_schedules sch ON es.schedule_id = sch.id "
                    "WHERE sch.academic_year_id = :year_id "
                    "AND CAST(es.status AS VARCHAR) IN ('ACTIVE', 'ON_GOING')"
                ),
                {"year_id": academic_year_id},
            ).scalar()
            if active_exams and active_exams > 0:
                errors.append("Masih ada sesi ujian yang sedang aktif / berlangsung di tahun ajaran ini.")

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
                errors.append("Active AI evaluation pipelines are running for this academic period.")

        return errors


academic_year_repository = AcademicYearRepository()
