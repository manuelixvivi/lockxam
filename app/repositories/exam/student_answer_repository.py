from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.exam.student_answer import StudentAnswer
from app.repositories.base_repository import BaseRepository


class StudentAnswerRepository(BaseRepository[StudentAnswer]):
    def __init__(self):
        super().__init__(StudentAnswer)

    def get_by_attempt_and_question(
        self, db: Session, attempt_id: int, question_id: int
    ) -> StudentAnswer | None:
        stmt = (
            select(StudentAnswer)
            .where(StudentAnswer.exam_attempt_id == attempt_id)
            .where(StudentAnswer.question_id == question_id)
        )
        return db.scalar(stmt)

    def get_by_attempt_and_question_with_lock(
        self, db: Session, attempt_id: int, question_id: int
    ) -> StudentAnswer | None:
        stmt = (
            select(StudentAnswer)
            .where(StudentAnswer.exam_attempt_id == attempt_id)
            .where(StudentAnswer.question_id == question_id)
            .with_for_update()
        )
        return db.scalar(stmt)

    def get_all_by_attempt(self, db: Session, attempt_id: int) -> list[StudentAnswer]:
        stmt = select(StudentAnswer).where(StudentAnswer.exam_attempt_id == attempt_id)
        return list(db.scalars(stmt).all())


student_answer_repository = StudentAnswerRepository()
