import re

from passlib.context import CryptContext

from app.exceptions import ValidationException

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


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
