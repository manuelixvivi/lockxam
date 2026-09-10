import datetime as dt
import os
import urllib.parse
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import DateTime, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.types import TypeDecorator

from app.core.environment import is_production_environment, is_serverless_environment
from app.logging.logger import logger

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# Detect available PostgreSQL driver (psycopg 3 or psycopg2)
_has_psycopg3 = False
_has_psycopg2 = False
try:
    import psycopg  # noqa: F401

    _has_psycopg3 = True
except ImportError:
    pass

try:
    import psycopg2  # noqa: F401

    _has_psycopg2 = True
except ImportError:
    pass

_preferred_driver = (
    "postgresql+psycopg://"
    if _has_psycopg3
    else ("postgresql+psycopg2://" if _has_psycopg2 else "postgresql://")
)

# Sanitize DATABASE_URL for SQLAlchemy 2.0 & available driver
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", _preferred_driver, 1)
elif DATABASE_URL.startswith("postgresql://") and not DATABASE_URL.startswith("postgresql+"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", _preferred_driver, 1)
elif DATABASE_URL.startswith("postgresql+psycopg://") and not _has_psycopg3 and _has_psycopg2:
    DATABASE_URL = DATABASE_URL.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)
elif DATABASE_URL.startswith("postgresql+psycopg2://") and not _has_psycopg2 and _has_psycopg3:
    DATABASE_URL = DATABASE_URL.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)

# Safely convert Neon direct endpoint to Neon pgBouncer pooler endpoint
if ".neon.tech" in DATABASE_URL and "-pooler" not in DATABASE_URL:
    try:
        parts = DATABASE_URL.split("@", 1)
        if len(parts) == 2:
            host_and_rest = parts[1]
            host_parts = host_and_rest.split(".", 1)
            if len(host_parts) == 2 and not host_parts[0].endswith("-pooler"):
                DATABASE_URL = f"{parts[0]}@{host_parts[0]}-pooler.{host_parts[1]}"
    except Exception as _neon_err:
        logger.warning("Neon pooler parse notice: %s", _neon_err)

# Auto-encode '@' in password if multiple '@' exist in DATABASE_URL
if DATABASE_URL.count("@") > 1 and "://" in DATABASE_URL:
    try:
        scheme_and_auth, host_and_db = DATABASE_URL.rsplit("@", 1)
        scheme, auth = scheme_and_auth.split("://", 1)
        if ":" in auth:
            user, password = auth.split(":", 1)
            encoded_password = urllib.parse.quote_plus(password)
            DATABASE_URL = f"{scheme}://{user}:{encoded_password}@{host_and_db}"
    except Exception as _parse_err:
        logger.warning("URL parse notice: %s", _parse_err)

# Production fail-fast verification
is_production = is_production_environment()

# Fallback if DATABASE_URL is empty, invalid, or incorrectly set to https://...
if not DATABASE_URL or DATABASE_URL.startswith("http://") or DATABASE_URL.startswith("https://"):
    if is_production:
        raise RuntimeError(
            f"Production Database Error: Valid PostgreSQL DATABASE_URL must be configured in production/Vercel. "
            f"Received: '{DATABASE_URL}'"
        )
    logger.warning(
        "Invalid or missing DATABASE_URL in dev ('%s'). Falling back to temporary SQLite DB.",
        DATABASE_URL,
    )
    DATABASE_URL = "sqlite:///./equigrade_dev.db"

connect_args: dict[str, Any] = {}
engine_kwargs: dict[str, Any] = {"echo": False}

if DATABASE_URL.startswith("sqlite"):
    if is_production:
        raise RuntimeError(
            "Production Database Error: SQLite is not supported in production/Vercel environment."
        )
    connect_args = {"check_same_thread": False}
else:
    # Serverless database pool optimization for PostgreSQL / Neon / Supabase
    use_nullpool = os.getenv("DB_USE_NULLPOOL", "false").lower() in ("true", "1", "yes")
    if use_nullpool:
        from sqlalchemy.pool import NullPool

        engine_kwargs["poolclass"] = NullPool
    else:
        is_serverless = is_serverless_environment()
        default_pool_size = 1 if is_serverless else 10
        default_max_overflow = 1 if is_serverless else 20
        pool_size = int(os.getenv("DB_POOL_SIZE", str(default_pool_size)))
        max_overflow = int(os.getenv("DB_MAX_OVERFLOW", str(default_max_overflow)))

        engine_kwargs.update(
            {
                "pool_pre_ping": True,
                "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "300")),
                "pool_size": pool_size,
                "max_overflow": max_overflow,
                "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "10")),
            }
        )

try:
    engine = create_engine(DATABASE_URL, connect_args=connect_args, **engine_kwargs)
except Exception as _engine_err:
    logger.warning("Database engine creation deferred: %s", _engine_err)
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class UTCDateTime(TypeDecorator):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            if value.tzinfo is None:
                value = value.replace(tzinfo=dt.timezone.utc)
            else:
                value = value.astimezone(dt.timezone.utc)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            if value.tzinfo is None:
                value = value.replace(tzinfo=dt.timezone.utc)
            else:
                value = value.astimezone(dt.timezone.utc)
        return value


class Base(DeclarativeBase):
    type_annotation_map = {
        datetime: UTCDateTime(),
    }


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
