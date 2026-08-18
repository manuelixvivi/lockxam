import re

from passlib.context import CryptContext

from app.exceptions import ValidationException

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# bcrypt has a hard limit of 72 bytes. Truncate to avoid ValueError on strict runtimes.
_BCRYPT_MAX_BYTES = 72


def _truncate(password: str) -> str:
    """Encode to UTF-8 and truncate to 72 bytes, then decode back safely."""
    encoded = password.encode("utf-8")
    if len(encoded) > _BCRYPT_MAX_BYTES:
        encoded = encoded[:_BCRYPT_MAX_BYTES]
        # Avoid splitting a multi-byte character
        return encoded.decode("utf-8", errors="ignore")
    return password


def hash_password(password: str) -> str:
    return pwd_context.hash(_truncate(password))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(_truncate(plain_password), hashed_password)


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
