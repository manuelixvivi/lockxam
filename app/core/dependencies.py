import os
from datetime import datetime, timedelta

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_token
from app.exceptions import AuthenticationException
from app.models.user_session import UserSession

security = HTTPBearer()

# Load session idle timeout from environment (default: 120 minutes)
SESSION_IDLE_TIMEOUT_MINUTES = int(os.getenv("SESSION_IDLE_TIMEOUT_MINUTES", 120))


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)
) -> dict:
    token = credentials.credentials
    payload = verify_token(token)

    if not payload:
        raise AuthenticationException("Invalid or expired token")

    # Enforce Token Version check
    if payload.get("ver") != 1:
        raise AuthenticationException("Unsupported token version")

    # Enforce Token Type check
    if payload.get("type") != "access":
        raise AuthenticationException("Invalid token type")

    session_id = payload.get("sid")
    jti = payload.get("jti")

    if not session_id or not jti:
        raise AuthenticationException("Invalid token payload")

    # Query active session
    stmt = select(UserSession).where(
        UserSession.id == session_id, UserSession.access_token_jti == jti
    )
    user_session = db.scalar(stmt)

    if not user_session:
        raise AuthenticationException("Session not found")

    if user_session.revoked:
        raise AuthenticationException("Session has been revoked")

    # Enforce Session Absolute Timeout
    if user_session.expires_at < datetime.utcnow():
        raise AuthenticationException("Session absolute timeout expired")

    # Enforce Session Idle Timeout
    idle_threshold = datetime.utcnow() - timedelta(minutes=SESSION_IDLE_TIMEOUT_MINUTES)
    if user_session.last_activity_at < idle_threshold:
        # Revoke the session due to inactivity
        user_session.revoked = True
        user_session.revoked_at = datetime.utcnow()
        user_session.revoked_reason = "IDLE_TIMEOUT"
        db.add(user_session)
        db.commit()
        raise AuthenticationException("Session expired due to inactivity")

    # Update last activity time
    user_session.last_activity_at = datetime.utcnow()
    db.commit()

    return payload
