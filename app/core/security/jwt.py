import logging
import uuid
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

from app.core.security.keys import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ACTIVE_KEY_ID,
    ALGORITHM,
    REFRESH_TOKEN_EXPIRE_DAYS,
    SECRET_KEY,
    SECRETS,
)
from app.exceptions import AuthenticationException

logger = logging.getLogger(__name__)


def create_uuid() -> str:
    return str(uuid.uuid4())


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})

    active_secret = SECRETS.get(ACTIVE_KEY_ID)
    if not active_secret:
        raise RuntimeError(f"Active JWT signing key '{ACTIVE_KEY_ID}' is not configured in SECRETS.")

    # Sign with active Key ID and attach to header
    return jwt.encode(
        to_encode,
        active_secret,
        algorithm=ALGORITHM,
        headers={"kid": ACTIVE_KEY_ID},
    )


def verify_token(token: str) -> dict | None:
    try:
        # Retrieve "kid" header to pick correct key
        headers = jwt.get_unverified_header(token)
        kid = headers.get("kid")
        if not kid:
            logger.warning("JWT verification failed: missing 'kid' header")
            return None

        secret = SECRETS.get(kid)
        if not secret:
            logger.warning("JWT verification failed: unknown 'kid' header: %s", kid)
            return None

        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        logger.warning("JWT verification failed: %s", e)
        return None


def create_user_token(
    user_id: int,
    role: str,
    school_id: int | None,
    session_id: str,
    access_jti: str,
    expires_delta: timedelta | None = None,
) -> str:
    return create_access_token(
        {
            "sub": str(user_id),
            "role": role,
            "school_id": school_id,
            "sid": session_id,
            "jti": access_jti,
            "type": "access",
            "ver": 1,  # Token Version
        },
        expires_delta=expires_delta,
    )


def create_refresh_token(
    user_id: int, role: str, school_id: int | None, session_id: str, refresh_jti: str
) -> str:
    expire = datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    active_secret = SECRETS.get(ACTIVE_KEY_ID)
    if not active_secret:
        raise RuntimeError(f"Active JWT signing key '{ACTIVE_KEY_ID}' is not configured in SECRETS.")

    return jwt.encode(
        {
            "sub": str(user_id),
            "role": role,
            "school_id": school_id,
            "sid": session_id,
            "jti": refresh_jti,
            "type": "refresh",
            "ver": 1,  # Token Version
            "exp": expire,
        },
        active_secret,
        algorithm=ALGORITHM,
        headers={"kid": ACTIVE_KEY_ID},
    )


def get_payload(token: str) -> dict:
    payload = verify_token(token)
    if not payload:
        raise AuthenticationException("Invalid token")
    return payload
