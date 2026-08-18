import datetime as dt
import os
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

# Fallback if DATABASE_URL is empty, invalid, or incorrectly set to https://...
if not DATABASE_URL or DATABASE_URL.startswith("http://") or DATABASE_URL.startswith("https://"):
    print(f"WARNING: Invalid DATABASE_URL protocol detected ('{DATABASE_URL}'). Falling back to temporary SQLite DB.")
    DATABASE_URL = "sqlite:////tmp/lockxam.db"

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)

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
