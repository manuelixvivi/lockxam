from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.academic.academic_semester import AcademicSemester
from app.models.academic.academic_year import AcademicYear
from app.models.academic.enums import AcademicStatus
from app.repositories.base_repository import BaseRepository


class AcademicSemesterRepository(BaseRepository[AcademicSemester]):
    def __init__(self):
        super().__init__(AcademicSemester)

    def get_active_semester(self, db: Session, school_id: int) -> AcademicSemester | None:
        # Join AcademicYear to filter by school_id and check that BOTH the parent year and the semester are ACTIVE
        return db.scalar(
            select(AcademicSemester)
            .join(AcademicYear)
            .where(
                AcademicYear.school_id == school_id,
                AcademicYear.status == AcademicStatus.ACTIVE.value,
                AcademicSemester.status == AcademicStatus.ACTIVE.value,
            )
        )

    def get_by_public_id_and_school(
        self, db: Session, public_id: UUID, school_id: int
    ) -> AcademicSemester | None:
        return db.scalar(
            select(AcademicSemester)
            .join(AcademicYear)
            .where(AcademicSemester.public_id == public_id, AcademicYear.school_id == school_id)
        )

    def get_by_public_id(self, db: Session, public_id: UUID) -> AcademicSemester | None:
        return db.scalar(select(AcademicSemester).where(AcademicSemester.public_id == public_id))

    def get_semesters_by_year(self, db: Session, academic_year_id: int) -> list[AcademicSemester]:
        return list(
            db.scalars(
                select(AcademicSemester)
                .where(AcademicSemester.academic_year_id == academic_year_id)
                .order_by(AcademicSemester.created_at.asc())
            ).all()
        )


academic_semester_repository = AcademicSemesterRepository()
