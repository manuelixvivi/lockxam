from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.teacher.proctor_event import ProctorAuditEvent
from app.repositories.base_repository import BaseRepository


class ProctorEventRepository(BaseRepository[ProctorAuditEvent]):

    def __init__(self):
        super().__init__(ProctorAuditEvent)

    def get_by_assignment(self, db: Session, assignment_id: int) -> list[ProctorAuditEvent]:
        stmt = (
            select(ProctorAuditEvent)
            .where(ProctorAuditEvent.proctor_assignment_id == assignment_id)
            .order_by(ProctorAuditEvent.timestamp.asc())
        )
        return list(db.scalars(stmt).all())


proctor_event_repository = ProctorEventRepository()
