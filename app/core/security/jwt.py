import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from jose import JWTError, jwt

from app.core.security.keys import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ACTIVE_KEY_ID,
    ALGORITHM,
    REFRESH_TOKEN_EXPIRE_DAYS,
    SECRET_KEY,
    SECRETS,
)


def create_uuid() -> str:
    return str(uuid.uuid4())


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})

    # Sign with active Key ID and attach to header
    return jwt.encode(
        to_encode,
        SECRETS.get(ACTIVE_KEY_ID, SECRET_KEY),
        algorithm=ALGORITHM,
        headers={"kid": ACTIVE_KEY_ID},
    )


def verify_token(token: str) -> dict | None:
    try:
        # Retrieve "kid" header to pick correct key
        headers = jwt.get_unverified_header(token)
        kid = headers.get("kid", "v1")
        secret = SECRETS.get(kid, SECRET_KEY)

        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        print("JWT ERROR:", e)
        return None


def create_user_token(
    user_id: int, role: str, school_id: int | None, session_id: str, access_jti: str
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
        }
    )


def create_refresh_token(
    user_id: int, role: str, school_id: int | None, session_id: str, refresh_jti: str
) -> str:
    expire = datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
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
        SECRETS.get(ACTIVE_KEY_ID, SECRET_KEY),
        algorithm=ALGORITHM,
        headers={"kid": ACTIVE_KEY_ID},
    )


def get_payload(token: str) -> dict:
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload
