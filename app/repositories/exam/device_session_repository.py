from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.exam.device_session import DeviceSession
from app.models.exam.enums import DeviceSessionStatus
from app.repositories.base_repository import BaseRepository


class DeviceSessionRepository(BaseRepository[DeviceSession]):
    def __init__(self):
        super().__init__(DeviceSession)

    def get_active_by_attempt(self, db: Session, attempt_id: int) -> DeviceSession | None:
        stmt = (
            select(DeviceSession)
            .where(DeviceSession.exam_attempt_id == attempt_id)
            .where(DeviceSession.status == DeviceSessionStatus.ACTIVE)
            .with_for_update()
        )
        return db.scalar(stmt)

    def get_blocked_by_attempt_with_lock(
        self, db: Session, attempt_id: int
    ) -> DeviceSession | None:
        stmt = (
            select(DeviceSession)
            .where(DeviceSession.exam_attempt_id == attempt_id)
            .where(DeviceSession.status == DeviceSessionStatus.BLOCKED)
            .with_for_update()
        )
        return db.scalar(stmt)

    def revoke_user_sessions_for_student(
        self, db: Session, student_id: int, reason: str = "REBIND_PROCTOR_RESET"
    ) -> None:
        from app.models.security.user_session import UserSession
        stmt = select(UserSession).where(
            UserSession.auth_account_id == student_id,
            UserSession.revoked == False,
        )
        sessions = list(db.scalars(stmt).all())
        now = datetime.now(timezone.utc)
        for s in sessions:
            s.revoked = True
            s.revoked_at = now
            s.revoked_reason = reason


device_session_repository = DeviceSessionRepository()
