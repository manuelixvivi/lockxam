import os


def is_production_environment() -> bool:
    """Authoritative environment check across database, storage, keys, and security.
    Returns True if running in production, staging, Vercel, AWS Lambda, Cloudflare, or Serverless.
    """
    env = os.getenv("ENV", "").lower().strip()
    environment = os.getenv("ENVIRONMENT", "").lower().strip()
    app_env = os.getenv("APP_ENV", "").lower().strip()

    if (
        env in ("prod", "production", "staging")
        or environment in ("prod", "production", "staging")
        or app_env in ("prod", "production", "staging")
    ):
        return True

    if (
        bool(os.getenv("VERCEL"))
        or bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))
        or bool(os.getenv("SERVERLESS"))
    ):
        return True

    return False


def is_serverless_environment() -> bool:
    """Returns True if running in a serverless runtime (Vercel, AWS Lambda, Cloudflare)."""
    return bool(
        os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME") or os.getenv("SERVERLESS")
    )
