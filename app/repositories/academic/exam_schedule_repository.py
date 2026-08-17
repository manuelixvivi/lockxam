from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.academic.exam_schedule import ExamSchedule
from app.repositories.base_repository import BaseRepository


class ExamScheduleRepository(BaseRepository[ExamSchedule]):
    def __init__(self):
        super().__init__(ExamSchedule)

    def get_by_public_id(self, db: Session, public_id: UUID) -> ExamSchedule | None:
        return db.scalar(
            select(ExamSchedule).where(ExamSchedule.public_id == public_id)
        )

    def list_by_school(
        self,
        db: Session,
        school_id: int,
        academic_year_id: int | None = None,
        academic_semester_id: int | None = None,
        class_id: int | None = None,
    ) -> list[ExamSchedule]:
        query = select(ExamSchedule).where(ExamSchedule.school_id == school_id)
        if academic_year_id is not None:
            query = query.where(ExamSchedule.academic_year_id == academic_year_id)
        if academic_semester_id is not None:
            query = query.where(ExamSchedule.academic_semester_id == academic_semester_id)
        if class_id is not None:
            query = query.where(ExamSchedule.class_id == class_id)
        query = query.order_by(ExamSchedule.start_time.asc())
        return list(db.scalars(query).all())

    def list_by_teacher(self, db: Session, teacher_id: int) -> list[ExamSchedule]:
        return list(
            db.scalars(
                select(ExamSchedule)
                .where(ExamSchedule.teacher_id == teacher_id)
                .order_by(ExamSchedule.start_time.asc())
            ).all()
        )

    def list_by_proctor(self, db: Session, proctor_id: int) -> list[ExamSchedule]:
        return list(
            db.scalars(
                select(ExamSchedule)
                .where(ExamSchedule.proctor_id == proctor_id)
                .order_by(ExamSchedule.start_time.asc())
            ).all()
        )

    def list_by_package(self, db: Session, package_id: int) -> list[ExamSchedule]:
        return list(
            db.scalars(
                select(ExamSchedule)
                .where(ExamSchedule.package_id == package_id)
                .order_by(ExamSchedule.start_time.asc())
            ).all()
        )


exam_schedule_repository = ExamScheduleRepository()
