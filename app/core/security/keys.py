import os

from dotenv import load_dotenv

from app.core.environment import is_production_environment

load_dotenv()


def _resolve_secret_key() -> str:
    key = os.getenv("SECRET_KEY") or os.getenv("JWT_SECRET_KEY") or os.getenv("JWT_SECRET")
    if key and key.strip():
        return key.strip()

    if is_production_environment():
        raise RuntimeError(
            "Production Security Error: 'SECRET_KEY' (or 'JWT_SECRET_KEY') must be explicitly set in production environment."
        )

    # Dev / Test fallback with explicit warning
    return "equigrade_lockxam_dev_test_ephemeral_secret_key_32bytes_minimum!!"


SECRET_KEY = _resolve_secret_key()


def get_internal_service_token() -> str:
    token = os.getenv("INTERNAL_SERVICE_TOKEN")
    if token and token.strip():
        return token.strip()
    if is_production_environment():
        raise RuntimeError(
            "Production Security Error: 'INTERNAL_SERVICE_TOKEN' must be explicitly set in production environment."
        )
    return "dev-internal-token-change-in-production"


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

COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"


def get_ai_webhook_secret() -> str:
    """Returns the secret used for validating incoming AI grading callbacks."""
    secret = os.getenv("AI_WEBHOOK_SECRET")
    if secret and secret.strip():
        return secret.strip()
    if is_production_environment():
        raise RuntimeError(
            "Production Security Error: 'AI_WEBHOOK_SECRET' must be explicitly set in production environment."
        )
    return ""


def get_qr_signing_secret() -> str:
    """Returns dedicated secret for exam QR code & short PIN signing/verification, decoupled from JWT rotation."""
    secret = os.getenv("QR_SIGNING_SECRET")
    if secret and secret.strip():
        return secret.strip()
    return SECRET_KEY


QR_SIGNING_SECRET = get_qr_signing_secret()

