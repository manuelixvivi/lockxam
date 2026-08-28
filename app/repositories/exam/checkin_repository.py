from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from app.models.exam.exam_checkin import ExamCheckin
from app.repositories.base_repository import BaseRepository


class CheckinRepository(BaseRepository[ExamCheckin]):
    def __init__(self):
        super().__init__(ExamCheckin)

    def get_by_student_and_schedule_or_session(
        self, db: Session, student_id: int, schedule_id: int, session_id: int | None = None
    ) -> ExamCheckin | None:
        stmt = select(ExamCheckin).where(
            ExamCheckin.student_id == student_id,
            ExamCheckin.schedule_id == schedule_id
        )
        return db.scalar(stmt)

    def get_by_student(self, db: Session, student_id: int) -> list[ExamCheckin]:
        stmt = select(ExamCheckin).where(ExamCheckin.student_id == student_id)
        return list(db.scalars(stmt).all())

    def get_by_schedule(self, db: Session, schedule_id: int) -> list[ExamCheckin]:
        stmt = select(ExamCheckin).where(ExamCheckin.schedule_id == schedule_id)
        return list(db.scalars(stmt).all())

    def get_by_schedule_and_student(
        self, db: Session, schedule_id: int, student_id: int
    ) -> ExamCheckin | None:
        stmt = select(ExamCheckin).where(
            ExamCheckin.schedule_id == schedule_id,
            ExamCheckin.student_id == student_id
        )
        return db.scalar(stmt)


checkin_repository = CheckinRepository()
