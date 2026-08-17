import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.exam.ai_event_log import AiGradingEventLog
from app.repositories.base_repository import BaseRepository


class AiEventRepository(BaseRepository[AiGradingEventLog]):
    def __init__(self):
        super().__init__(AiGradingEventLog)

    def get_by_id(self, db: Session, event_id: str) -> AiGradingEventLog | None:
        stmt = select(AiGradingEventLog).where(
            AiGradingEventLog.event_id == uuid.UUID(event_id)
        )
        return db.scalar(stmt)

    def create_if_not_exists(self, db: Session, event: AiGradingEventLog) -> bool:
        """EXAM-FIX-09: Atomic ON CONFLICT DO NOTHING — bebas dari parsing raw IntegrityError."""
        stmt = (
            insert(AiGradingEventLog)
            .values(
                event_id=event.event_id,
                attempt_id=event.attempt_id,
                processed_at=event.processed_at,
                grading_version=event.grading_version,
            )
            .on_conflict_do_nothing(index_elements=["event_id"])
        )
        result = db.execute(stmt)
        return result.rowcount > 0


ai_event_repository = AiEventRepository()
