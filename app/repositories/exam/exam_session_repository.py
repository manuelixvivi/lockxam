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

    def get_by_schedule_id(self, db: Session, schedule_id: int) -> ExamSession | None:
        stmt = select(ExamSession).where(ExamSession.schedule_id == schedule_id)
        return db.scalar(stmt)

    def get_by_ids(self, db: Session, session_ids: list[int]) -> list[ExamSession]:
        if not session_ids:
            return []
        stmt = select(ExamSession).where(ExamSession.id.in_(session_ids))
        return list(db.scalars(stmt).all())

    def get_all(self, db: Session) -> list[ExamSession]:
        stmt = select(ExamSession)
        return list(db.scalars(stmt).all())


    def list_by_schedule_id(self, db: Session, schedule_id: int) -> list[ExamSession]:
        stmt = select(ExamSession).where(ExamSession.schedule_id == schedule_id)
        return list(db.scalars(stmt).all())


exam_session_repository = ExamSessionRepository()
