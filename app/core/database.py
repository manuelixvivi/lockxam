import datetime as dt
import os
import urllib.parse
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import DateTime, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.types import TypeDecorator

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# Sanitize DATABASE_URL for SQLAlchemy 2.0
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Auto-convert Neon connection string to use Neon's pgBouncer pooler for serverless speed
if ".neon.tech" in DATABASE_URL and "-pooler" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace(".neon.tech", "-pooler.neon.tech")

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
        print(f"URL parse notice: {_parse_err}")

# Fallback if DATABASE_URL is empty, invalid, or incorrectly set to https://...
if not DATABASE_URL or DATABASE_URL.startswith("http://") or DATABASE_URL.startswith("https://"):
    print(f"WARNING: Invalid DATABASE_URL protocol detected ('{DATABASE_URL}'). Falling back to temporary SQLite DB.")
    DATABASE_URL = "sqlite:////tmp/lockxam.db"

connect_args = {}
engine_kwargs = {"echo": False}

if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
else:
    # Serverless database pool optimization for PostgreSQL / Neon / Supabase
    engine_kwargs.update(
        {
            "pool_pre_ping": True,
            "pool_size": 10,
            "max_overflow": 20,
            "pool_recycle": 300,
            "pool_timeout": 10,
        }
    )

engine = create_engine(DATABASE_URL, connect_args=connect_args, **engine_kwargs)

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
