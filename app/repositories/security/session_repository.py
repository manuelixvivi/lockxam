import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.security.user_session import UserSession
from app.repositories.base_repository import BaseRepository


class SessionRepository(BaseRepository[UserSession]):

    def __init__(self):
        super().__init__(UserSession)

    def get_session_by_id_and_jti(
        self, db: Session, session_id: uuid.UUID, access_jti: uuid.UUID
    ) -> UserSession | None:
        return db.scalar(
            select(UserSession).where(
                UserSession.id == session_id, UserSession.access_token_jti == access_jti
            )
        )

    def get_active_sessions_by_user(self, db: Session, user_id: int) -> list[UserSession]:
        stmt = (
            select(UserSession)
            .where(
                UserSession.auth_account_id == user_id,
                UserSession.revoked == False,
                UserSession.expires_at > datetime.utcnow(),
            )
            .order_by(UserSession.created_at.desc())
        )
        return list(db.scalars(stmt).all())


session_repository = SessionRepository()
