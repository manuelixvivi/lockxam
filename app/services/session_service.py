from datetime import datetime, timedelta

from app.core.security import create_uuid
from app.models.user_session import UserSession


def create_session():
    now = datetime.utcnow()

    return {
        "session_id": create_uuid(),
        "access_jti": create_uuid(),
        "refresh_jti": create_uuid(),
        "created_at": now,
        "last_activity_at": now,
        "expires_at": now + timedelta(days=30),
    }


def save_session(
    db,
    auth_account_id,
    session,
    device_name=None,
    device_type=None,
    ip_address=None,
    user_agent=None,
):
    db_session = UserSession(
        id=session["session_id"],
        auth_account_id=auth_account_id,
        access_token_jti=session["access_jti"],
        refresh_token_jti=session["refresh_jti"],
        device_name=device_name,
        device_type=device_type,
        ip_address=ip_address,
        user_agent=user_agent,
        created_at=session["created_at"],
        last_activity_at=session["last_activity_at"],
        expires_at=session["expires_at"],
        revoked=False,
    )

    db.add(db_session)

    return db_session
