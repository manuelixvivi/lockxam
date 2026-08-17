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
        # Returns True if there's any overlapping academic year
        # Overlap criteria: (start1 < end2) and (end1 > start2)
        query = select(AcademicYear).where(
            AcademicYear.school_id == school_id,
            and_(AcademicYear.start_date < end_date, AcademicYear.end_date > start_date),
        )
        if exclude_id is not None:
            query = query.where(AcademicYear.id != exclude_id)

        overlap_rec = db.scalar(query)
        return overlap_rec is not None


academic_year_repository = AcademicYearRepository()
