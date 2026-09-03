import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_token
from app.exceptions import AuthenticationException, LicenseExpiredException, PermissionException
from app.models.security.enums import SessionRevokedReason
from app.repositories.security.session_repository import session_repository

security = HTTPBearer(auto_error=False)

# Load session idle timeout from environment (default: 120 minutes)
SESSION_IDLE_TIMEOUT_MINUTES = int(os.getenv("SESSION_IDLE_TIMEOUT_MINUTES", 120))


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> dict:
    if not credentials:
        raise AuthenticationException("Not authenticated")
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
    user_session = session_repository.get_session_by_id_and_jti(db, session_id, jti)

    if not user_session:
        raise AuthenticationException("Session not found")

    if user_session.revoked:
        raise AuthenticationException("Session has been revoked")

    # Enforce Session Absolute Timeout
    if user_session.expires_at < datetime.now(timezone.utc):
        raise AuthenticationException("Session absolute timeout expired")

    # Enforce Session Idle Timeout
    idle_threshold = datetime.now(timezone.utc) - timedelta(minutes=SESSION_IDLE_TIMEOUT_MINUTES)
    if user_session.last_activity_at < idle_threshold:
        # Revoke the session due to inactivity
        user_session.revoked = True
        user_session.revoked_at = datetime.now(timezone.utc)
        user_session.revoked_reason = SessionRevokedReason.IDLE_TIMEOUT
        session_repository.update(db, user_session)
        db.commit()
        raise AuthenticationException("Session expired due to inactivity")

    # Update last activity time (Throttled: at most once per 60 seconds to prevent DB write amplification)
    now_utc = datetime.now(timezone.utc)
    last_act = user_session.last_activity_at
    if last_act.tzinfo is None:
        last_act = last_act.replace(tzinfo=timezone.utc)
    if (now_utc - last_act).total_seconds() > 60:
        user_session.last_activity_at = now_utc
        session_repository.update(db, user_session)
        db.commit()

    # Enforce School Status Checks (BR-LIC-007, BR-LIC-008, BR-LIC-011)
    school_id = payload.get("school_id")
    role = payload.get("role")
    if school_id and role != "SUPERADMIN":
        from app.models.school.school import School

        school = db.query(School).filter(School.id == school_id).first()
        if school:
            if school.status == "SUSPENDED":
                raise PermissionException("School is suspended")
            elif school.status in ["READ_ONLY", "PENDING_ACTIVATION"]:
                # Block mutating requests for non-auth/non-license endpoints
                if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
                    path = request.url.path
                    if not (path.startswith("/api/v1/licenses") or path.startswith("/api/v1/auth")):
                        raise LicenseExpiredException()

    return payload
