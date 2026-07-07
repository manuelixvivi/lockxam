import os
import re
import uuid
from datetime import UTC, datetime, timedelta

from dotenv import load_dotenv
from fastapi import HTTPException
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.exceptions import ValidationException

load_dotenv()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 30))

# JWT Key ID (kid) Rotation settings
ACTIVE_KEY_ID = os.getenv("JWT_ACTIVE_KEY_ID", "v1")
SECRETS = {"v1": SECRET_KEY}

# Load extra secrets for keys if defined in env (e.g. JWT_SECRET_v2=...)
for key, value in os.environ.items():
    if key.startswith("JWT_SECRET_"):
        kid = key.replace("JWT_SECRET_", "")
        SECRETS[kid] = value


def create_uuid():
    return str(uuid.uuid4())


def hash_password(password: str):
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict):
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


def verify_token(token: str):
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
):
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
):
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


def get_payload(token: str):
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload


def validate_password_strength(password: str) -> None:
    if len(password) < 8:
        raise ValidationException("Password must be at least 8 characters long")
    if not re.search(r"[a-z]", password):
        raise ValidationException("Password must contain at least one lowercase letter")
    if not re.search(r"[A-Z]", password):
        raise ValidationException("Password must contain at least one uppercase letter")
    if not re.search(r"\d", password):
        raise ValidationException("Password must contain at least one digit")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        raise ValidationException("Password must contain at least one special character")
