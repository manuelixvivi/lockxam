from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.exam.exam_attempt import ExamAttempt
from app.repositories.base_repository import BaseRepository


class AttemptRepository(BaseRepository[ExamAttempt]):
    def __init__(self):
        super().__init__(ExamAttempt)

    def get_with_lock(self, db: Session, attempt_id: int) -> ExamAttempt | None:
        stmt = select(ExamAttempt).where(ExamAttempt.id == attempt_id).with_for_update()
        return db.scalar(stmt)

    def get_by_session_and_student(
        self, db: Session, session_id: int, student_id: int
    ) -> ExamAttempt | None:
        stmt = (
            select(ExamAttempt)
            .where(ExamAttempt.exam_session_id == session_id)
            .where(ExamAttempt.student_id == student_id)
        )
        return db.scalar(stmt)


attempt_repository = AttemptRepository()
