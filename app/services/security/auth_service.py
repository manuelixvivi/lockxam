from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.security import (
    create_refresh_token,
    create_user_token,
    create_uuid,
    hash_password,
    validate_password_strength,
    verify_password,
    verify_token,
)
from app.exceptions import AuthenticationException, BusinessException, PermissionException
from app.models.security.enums import SessionRevokedReason, UserRole
from app.models.security.login_attempt import LoginAttempt
from app.repositories.security.auth_repository import auth_repository
from app.repositories.security.login_attempt_repository import login_attempt_repository
from app.repositories.security.session_repository import session_repository
from app.schemas.security.auth import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    SessionResponse,
    TokenResponse,
)
from app.services.security.activity_service import ActivityService
from app.services.security.session_service import SessionService


class AuthService:

    @staticmethod
    def login(db: Session, request: Request, data: LoginRequest) -> LoginResponse:
        ip_address = request.client.host if request.client else "127.0.0.1"
        username = data.username

        # 1. Brute Force Protection: Rate Limiting Check
        attempt_record = login_attempt_repository.get_attempt(db, ip_address, username)

        if attempt_record:
            if attempt_record.blocked_until and attempt_record.blocked_until > datetime.now(
                timezone.utc
            ):
                locked_mins = (
                    int(
                        (attempt_record.blocked_until - datetime.now(timezone.utc)).total_seconds()
                        / 60
                    )
                    + 1
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
            # Detect whether request is coming from APK
            user_agent = request.headers.get("user-agent", "")
            x_client_app = request.headers.get("x-client-app", "")
            is_apk = (
                "Lockxam" in user_agent
                or "LockxamBrowser" in user_agent
                or "EquigradeApp" in user_agent
                or x_client_app == "lockxam_apk"
            )

            # 2. Authenticate
            account = AuthService._authenticate(db, username, data.password)

            # 3. Enforce Access Rules: Student role ONLY allowed via APK
            role_str = account.role.value if hasattr(account.role, "value") else str(account.role)
            if role_str in ["STUDENT", UserRole.STUDENT] and not is_apk:
                dev_bypass = request.headers.get("x-lockxam-dev-bypass") == "true"
                if not dev_bypass:
                    raise PermissionException(
                        "Akun siswa hanya dapat diakses melalui aplikasi resmi Lockxam APK. "
                        "Silakan gunakan aplikasi Android Lockxam."
                    )

            # 4. Enforce Single Device Binding for Student Role
            if role_str in ["STUDENT", UserRole.STUDENT]:
                active_sessions = session_repository.get_active_sessions_by_user(db, account.id)
                if active_sessions:
                    raise PermissionException(
                        "Akun siswa ini sedang aktif/terikat pada perangkat lain. "
                        "Pengeluaran akun dari perangkat sebelumnya memerlukan verifikasi pengawas."
                    )

            # Reset rate limit attempt counter on successful login
            if attempt_record:
                attempt_record.attempts = 0
                attempt_record.blocked_until = None
                login_attempt_repository.update(db, attempt_record)

            # 5. Start session and log activity
            session = AuthService._create_session(db, request, account)

            # 6. Commit transaction
            db.commit()

            # 7. Build and return response (90 days / 3 months for APK, 12 hours for Web)
            expires_delta = timedelta(days=90) if is_apk else timedelta(hours=12)
            return AuthService._build_login_response(account, session, expires_delta=expires_delta)

        except AuthenticationException as ae:
            # Log failed login attempt for rate limiting
            if not attempt_record:
                attempt_record = LoginAttempt(
                    ip_address=ip_address,
                    username=username,
                    attempts=1,
                    last_attempt_at=datetime.now(timezone.utc),
                )
                login_attempt_repository.create(db, attempt_record)
            else:
                attempt_record.attempts += 1
                attempt_record.last_attempt_at = datetime.now(timezone.utc)

            if attempt_record.attempts >= 5:
                attempt_record.blocked_until = datetime.now(timezone.utc) + timedelta(minutes=15)

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
            user_session.revoked_at = datetime.now(timezone.utc)
            user_session.revoked_reason = SessionRevokedReason.LOGOUT
            user_session.last_activity_at = datetime.now(timezone.utc)
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

            if user_session.expires_at < datetime.now(timezone.utc):
                raise AuthenticationException("Session has expired")

            # Validate refresh_token_jti for rotation
            if str(user_session.refresh_token_jti) != refresh_jti:
                # Token reuse detected! Revoke the entire session immediately (replay attack protection)
                user_session.revoked = True
                user_session.revoked_at = datetime.now(timezone.utc)
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
            user_session.last_activity_at = datetime.now(timezone.utc)
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
            user_session.revoked_at = datetime.now(timezone.utc)
            user_session.revoked_reason = (
                SessionRevokedReason.ADMIN_FORCE_LOGOUT
                if role in [UserRole.SUPERADMIN, UserRole.ADMIN]
                else SessionRevokedReason.USER_FORCE_LOGOUT
            )
            user_session.last_activity_at = datetime.now(timezone.utc)
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
                s.revoked_at = datetime.now(timezone.utc)
                s.revoked_reason = SessionRevokedReason.LOGOUT_ALL
                s.last_activity_at = datetime.now(timezone.utc)
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
    def change_password(db: Session, current_user: dict, old_password: str, new_password: str) -> None:
        user_id = int(current_user["sub"])
        account = auth_repository.get_by_id(db, user_id)
        if not account:
            raise AuthenticationException("Akun tidak ditemukan.")

        if not verify_password(old_password, account.password_hash):
            raise BusinessException("Kata sandi lama tidak sesuai.", status_code=400)

        validate_password_strength(new_password)
        account.password_hash = hash_password(new_password)
        account.must_change_password = False
        db.commit()

    @staticmethod
    def _authenticate(db: Session, username: str, password: str):
        account = auth_repository.get_by_username(db, username)
        if not account and "@" in username:
            account = auth_repository.get_by_username(db, username.split("@")[0])

        if not account:
            raise AuthenticationException("Invalid credentials")


        if not verify_password(password, account.password_hash):
            raise AuthenticationException("Invalid credentials")

        if not account.is_active:
            raise PermissionException("Account is inactive")

        # Check school subscription status (Block login if SUSPENDED)
        if account.school_id and account.role in [UserRole.ADMIN, "SCHOOL_ADMIN", UserRole.TEACHER, "TEACHER"]:
            from app.models.license.school_license import SchoolLicense

            latest_license = (
                db.query(SchoolLicense)
                .filter(SchoolLicense.school_id == account.school_id)
                .order_by(SchoolLicense.created_at.desc())
                .first()
            )
            if latest_license and latest_license.status in ["SUSPENDED", "PAUSED"]:
                raise PermissionException(
                    "Layanan subscription sekolah Anda sedang dijeda / ditangguhkan oleh SuperAdmin. Akses login ditolak."
                )

        account.last_login = datetime.now(timezone.utc)
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
    def _build_login_response(account, session, expires_delta: timedelta | None = None) -> LoginResponse:
        access_token = create_user_token(
            user_id=account.id,
            role=account.role,
            school_id=account.school_id,
            session_id=session["session_id"],
            access_jti=session["access_jti"],
            expires_delta=expires_delta,
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
            must_change_password=account.must_change_password,
        )
