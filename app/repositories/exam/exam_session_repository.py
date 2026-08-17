from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.exam.exam_session import ExamSession
from app.repositories.base_repository import BaseRepository


class ExamSessionRepository(BaseRepository[ExamSession]):
    def __init__(self):
        super().__init__(ExamSession)

    def get_with_lock(self, db: Session, session_id: int) -> ExamSession | None:
        stmt = select(ExamSession).where(ExamSession.id == session_id).with_for_update()
        return db.scalar(stmt)


exam_session_repository = ExamSessionRepository()
