from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.exam.answer_evaluation import ExamAnswerEvaluation
from app.repositories.base_repository import BaseRepository


class EvaluationRepository(BaseRepository[ExamAnswerEvaluation]):
    def __init__(self):
        super().__init__(ExamAnswerEvaluation)

    def get_with_lock(self, db: Session, evaluation_id: int) -> ExamAnswerEvaluation | None:
        stmt = (
            select(ExamAnswerEvaluation)
            .where(ExamAnswerEvaluation.id == evaluation_id)
            .with_for_update()
        )
        return db.scalar(stmt)

    def get_by_attempt_and_question_with_lock(
        self, db: Session, attempt_id: int, question_id: int
    ) -> ExamAnswerEvaluation | None:
        stmt = (
            select(ExamAnswerEvaluation)
            .where(ExamAnswerEvaluation.exam_attempt_id == attempt_id)
            .where(ExamAnswerEvaluation.question_id == question_id)
            .with_for_update()
        )
        return db.scalar(stmt)

    def get_all_by_attempt(
        self, db: Session, attempt_id: int
    ) -> list[ExamAnswerEvaluation]:
        stmt = select(ExamAnswerEvaluation).where(
            ExamAnswerEvaluation.exam_attempt_id == attempt_id
        )
        return list(db.scalars(stmt).all())


evaluation_repository = EvaluationRepository()
