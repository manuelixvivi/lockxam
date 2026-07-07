from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.security import create_uuid
from app.models.user_session import UserSession
from app.repositories.session_repository import session_repository


class SessionService:

    @staticmethod
    def create_session() -> dict:
        now = datetime.utcnow()
        return {
            "session_id": create_uuid(),
            "access_jti": create_uuid(),
            "refresh_jti": create_uuid(),
            "created_at": now,
            "last_activity_at": now,
            "expires_at": now + timedelta(days=30),
        }

    @staticmethod
    def save_session(
        db: Session,
        auth_account_id: int,
        session: dict,
        device_name: str | None = None,
        device_type: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> UserSession:
        db_session = UserSession(
            id=UUID(session["session_id"]),
            auth_account_id=auth_account_id,
            access_token_jti=UUID(session["access_jti"]),
            refresh_token_jti=UUID(session["refresh_jti"]),
            device_name=device_name,
            device_type=device_type,
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=session["created_at"],
            last_activity_at=session["last_activity_at"],
            expires_at=session["expires_at"],
            revoked=False,
        )
        return session_repository.create(db, db_session)
