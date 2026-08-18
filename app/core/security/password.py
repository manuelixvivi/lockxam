import re

import bcrypt

from app.exceptions import ValidationException

# bcrypt hard limit is 72 bytes.
_BCRYPT_MAX_BYTES = 72


def _to_bytes(password: str) -> bytes:
    """Encode password to UTF-8 and truncate to 72 bytes."""
    encoded = password.encode("utf-8")
    return encoded[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(_to_bytes(password), bcrypt.gensalt(rounds=12))
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(_to_bytes(plain_password), hashed_password.encode("utf-8"))
    except Exception:
        return False


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
