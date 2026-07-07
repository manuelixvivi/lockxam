from datetime import datetime, timedelta
from uuid import UUID

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.security import (
    create_refresh_token,
    create_user_token,
    create_uuid,
    verify_password,
    verify_token,
)
from app.exceptions import AuthenticationException, BusinessException, PermissionException
from app.models.enums import SessionRevokedReason, UserRole
from app.models.login_attempt import LoginAttempt
from app.repositories.auth_repository import auth_repository
from app.repositories.login_attempt_repository import login_attempt_repository
from app.repositories.session_repository import session_repository
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    SessionResponse,
    TokenResponse,
)
from app.services.activity_service import ActivityService
from app.services.session_service import SessionService


class AuthService:

    @staticmethod
    def login(db: Session, request: Request, data: LoginRequest) -> LoginResponse:
        ip_address = request.client.host if request.client else "127.0.0.1"
        username = data.username

        # 1. Brute Force Protection: Rate Limiting Check
        attempt_record = login_attempt_repository.get_attempt(db, ip_address, username)

        if attempt_record:
            if attempt_record.blocked_until and attempt_record.blocked_until > datetime.utcnow():
                locked_mins = (
                    int((attempt_record.blocked_until - datetime.utcnow()).total_seconds() / 60) + 1
                )
                raise AuthenticationException(
                    f"Too many failed login attempts. Account temporarily locked. "
                    f"Try again in {locked_mins} minute(s)."
                )
            elif attempt_record.blocked_until:
                # Lock has expired, reset attempt counter
                attempt_record.attempts = 0
                attempt_record.blocked_until = None
                login_attempt_repository.update(db, attempt_record)

        try:
            # 2. Authenticate
            account = AuthService._authenticate(db, username, data.password)

            # Reset rate limit attempt counter on successful login
            if attempt_record:
                attempt_record.attempts = 0
                attempt_record.blocked_until = None
                login_attempt_repository.update(db, attempt_record)

            # 3. Start session and log activity (adds to db session but doesn't commit yet)
            session = AuthService._create_session(db, request, account)

            # 4. Commit the entire transaction atomically (commits session, log, and last_login)
            db.commit()

            # 5. Build and return response
            return AuthService._build_login_response(account, session)

        except AuthenticationException as ae:
            # Log failed login attempt for rate limiting
            if not attempt_record:
                attempt_record = LoginAttempt(
                    ip_address=ip_address,
                    username=username,
                    attempts=1,
                    last_attempt_at=datetime.utcnow(),
                )
                login_attempt_repository.create(db, attempt_record)
            else:
                attempt_record.attempts += 1
                attempt_record.last_attempt_at = datetime.utcnow()

            if attempt_record.attempts >= 5:
                attempt_record.blocked_until = datetime.utcnow() + timedelta(minutes=15)

            login_attempt_repository.update(db, attempt_record)
            db.commit()
            raise ae
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def logout(
        db: Session,
        current_user: dict,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        session_id = current_user.get("sid")
        if not session_id:
            raise AuthenticationException("Invalid session")

        try:
            user_session = session_repository.get_by_id(db, session_id)

            if not user_session:
                raise AuthenticationException("Session not found")

            # Revoke session
            user_session.revoked = True
            user_session.revoked_at = datetime.utcnow()
            user_session.revoked_reason = SessionRevokedReason.LOGOUT
            user_session.last_activity_at = datetime.utcnow()
            session_repository.update(db, user_session)

            # Log activity
            ActivityService.log_activity(
                db=db,
                auth_account_id=user_session.auth_account_id,
                action_type="AUTH",
                action_name="LOGOUT",
                session_id=session_id,
                endpoint="/api/v1/auth/logout",
                method="POST",
                ip_address=ip_address,
                user_agent=user_agent,
            )

            db.commit()
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def refresh(db: Session, data: RefreshRequest) -> TokenResponse:
        payload = verify_token(data.refresh_token)

        if not payload or payload.get("type") != "refresh":
            raise AuthenticationException("Invalid refresh token")

        # Enforce Token Version check
        if payload.get("ver") != 1:
            raise AuthenticationException("Unsupported token version")

        session_id = payload.get("sid")
        refresh_jti = payload.get("jti")

        if not session_id or not refresh_jti:
            raise AuthenticationException("Invalid refresh token payload")

        try:
            user_session = session_repository.get_by_id(db, session_id)

            if not user_session:
                raise AuthenticationException("Session not found")

            if user_session.revoked:
                raise AuthenticationException("Session has been revoked")

            if user_session.expires_at < datetime.utcnow():
                raise AuthenticationException("Session has expired")

            # Validate refresh_token_jti for rotation
            if str(user_session.refresh_token_jti) != refresh_jti:
                # Token reuse detected! Revoke the entire session immediately (replay attack protection)
                user_session.revoked = True
                user_session.revoked_at = datetime.utcnow()
                user_session.revoked_reason = SessionRevokedReason.REFRESH_TOKEN_REUSE_DETECTED
                session_repository.update(db, user_session)
                db.commit()
                raise AuthenticationException(
                    "Refresh token reuse detected. Session has been revoked."
                )

            # Perform Refresh Token Rotation
            new_access_jti = create_uuid()
            new_refresh_jti = create_uuid()

            user_session.access_token_jti = UUID(new_access_jti)
            user_session.refresh_token_jti = UUID(new_refresh_jti)
            user_session.last_activity_at = datetime.utcnow()
            session_repository.update(db, user_session)

            # Log activity
            ActivityService.log_activity(
                db=db,
                auth_account_id=user_session.auth_account_id,
                action_type="AUTH",
                action_name="TOKEN_REFRESH",
                session_id=session_id,
            )

            db.commit()

            # Create new tokens
            new_access_token = create_user_token(
                user_id=user_session.auth_account_id,
                role=payload["role"],
                school_id=payload["school_id"],
                session_id=str(user_session.id),
                access_jti=new_access_jti,
            )

            new_refresh_token = create_refresh_token(
                user_id=user_session.auth_account_id,
                role=payload["role"],
                school_id=payload["school_id"],
                session_id=str(user_session.id),
                refresh_jti=new_refresh_jti,
            )

            return TokenResponse(access_token=new_access_token, refresh_token=new_refresh_token)
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def get_active_sessions(db: Session, current_user: dict) -> list[SessionResponse]:
        user_id = int(current_user["sub"])
        current_sid = current_user["sid"]

        sessions = session_repository.get_active_sessions_by_user(db, user_id)

        return [
            SessionResponse(
                session_id=str(s.id),
                ip=s.ip_address,
                user_agent=s.user_agent,
                created_at=s.created_at,
                last_activity_at=s.last_activity_at,
                is_current=(str(s.id) == current_sid),
            )
            for s in sessions
        ]

    @staticmethod
    def revoke_session(db: Session, session_id: str, current_user: dict) -> None:
        user_id = int(current_user["sub"])
        role = current_user["role"]

        try:
            user_session = session_repository.get_by_id(db, session_id)

            if not user_session:
                raise BusinessException("Session not found", status_code=404)

            if user_session.auth_account_id != user_id and role not in [
                UserRole.SUPERADMIN,
                UserRole.ADMIN,
            ]:
                raise PermissionException("Permission denied to revoke this session")

            # Mark session as revoked
            user_session.revoked = True
            user_session.revoked_at = datetime.utcnow()
            user_session.revoked_reason = (
                SessionRevokedReason.ADMIN_FORCE_LOGOUT
                if role in [UserRole.SUPERADMIN, UserRole.ADMIN]
                else SessionRevokedReason.USER_FORCE_LOGOUT
            )
            user_session.last_activity_at = datetime.utcnow()
            session_repository.update(db, user_session)

            # Log activity
            ActivityService.log_activity(
                db=db,
                auth_account_id=user_session.auth_account_id,
                action_type="AUTH",
                action_name="FORCE_LOGOUT",
                session_id=session_id,
                metadata={"revoked_by": user_id, "reason": user_session.revoked_reason},
            )

            db.commit()
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def logout_all(db: Session, current_user: dict) -> None:
        user_id = int(current_user["sub"])

        try:
            sessions = session_repository.get_active_sessions_by_user(db, user_id)

            for s in sessions:
                s.revoked = True
                s.revoked_at = datetime.utcnow()
                s.revoked_reason = SessionRevokedReason.LOGOUT_ALL
                s.last_activity_at = datetime.utcnow()
                session_repository.update(db, s)

                ActivityService.log_activity(
                    db=db,
                    auth_account_id=user_id,
                    action_type="AUTH",
                    action_name="FORCE_LOGOUT",
                    session_id=str(s.id),
                    metadata={"reason": SessionRevokedReason.LOGOUT_ALL},
                )

            db.commit()
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def _authenticate(db: Session, username: str, password: str):
        account = auth_repository.get_by_username(db, username)

        if not account:
            raise AuthenticationException("Invalid credentials")

        if not verify_password(password, account.password_hash):
            raise AuthenticationException("Invalid credentials")

        if not account.is_active:
            raise PermissionException("Account is inactive")

        account.last_login = datetime.utcnow()
        auth_repository.update_last_login(db, account)

        return account

    @staticmethod
    def _create_session(db: Session, request: Request, account) -> dict:
        session = SessionService.create_session()

        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        SessionService.save_session(
            db=db,
            auth_account_id=account.id,
            session=session,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        ActivityService.log_login(
            db=db,
            auth_account_id=account.id,
            school_id=account.school_id,
            session_id=session["session_id"],
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return session

    @staticmethod
    def _build_login_response(account, session) -> LoginResponse:
        access_token = create_user_token(
            user_id=account.id,
            role=account.role,
            school_id=account.school_id,
            session_id=session["session_id"],
            access_jti=session["access_jti"],
        )

        refresh_token = create_refresh_token(
            user_id=account.id,
            role=account.role,
            school_id=account.school_id,
            session_id=session["session_id"],
            refresh_jti=session["refresh_jti"],
        )

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            role=account.role,
            school_id=account.school_id,
        )
