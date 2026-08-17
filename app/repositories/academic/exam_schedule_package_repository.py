from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.academic.exam_schedule_package import ExamSchedulePackage
from app.repositories.base_repository import BaseRepository


class ExamSchedulePackageRepository(BaseRepository[ExamSchedulePackage]):
    def __init__(self):
        super().__init__(ExamSchedulePackage)

    def get_by_public_id(self, db: Session, public_id: UUID) -> ExamSchedulePackage | None:
        return db.scalar(
            select(ExamSchedulePackage).where(ExamSchedulePackage.public_id == public_id)
        )

    def list_by_school(
        self,
        db: Session,
        school_id: int,
        academic_year_id: int | None = None,
    ) -> list[ExamSchedulePackage]:
        query = select(ExamSchedulePackage).where(ExamSchedulePackage.school_id == school_id)
        if academic_year_id is not None:
            query = query.where(ExamSchedulePackage.academic_year_id == academic_year_id)
        query = query.order_by(ExamSchedulePackage.created_at.desc())
        return list(db.scalars(query).all())


exam_schedule_package_repository = ExamSchedulePackageRepository()
