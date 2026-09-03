import os
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.models.school.school import School
from app.models.security.auth_account import AuthAccount
from main import app

DATABASE_URL = os.getenv("DATABASE_URL") or "sqlite:///./equigrade_test.db"
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    # Ensure all tables exist without dropping existing development data
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        try:
            from sqlalchemy import text

            conn.execute(
                text(
                    "ALTER TABLE exam_schedules ADD COLUMN IF NOT EXISTS target_type VARCHAR(20) DEFAULT 'ALL_CLASS';"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE exam_schedules ADD COLUMN IF NOT EXISTS allowed_student_ids JSON;"
                )
            )
            conn.commit()
        except Exception:
            pass
    from app.database.seed_master import seed_master_data

    db = TestingSessionLocal()
    try:
        seed_master_data(db)
    finally:
        db.close()
    yield


@pytest.fixture(name="db")
def db_fixture():
    # Connect to database and start a transaction
    connection = engine.connect()
    transaction = connection.begin()
    db = TestingSessionLocal(bind=connection)

    # Begin a SAVEPOINT (nested transaction)
    nested = connection.begin_nested()

    # Re-start nested transaction after any commit/rollback in session
    @event.listens_for(db, "after_transaction_end")
    def restart_savepoint(session, trans):
        nonlocal nested
        if trans.parent is None:
            nested = connection.begin_nested()

    # Override get_db dependency to use the transactional session
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    yield db

    db.close()
    transaction.rollback()
    connection.close()
    app.dependency_overrides.clear()


@pytest.fixture
def client(db):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def test_school(db):
    school = db.query(School).first()
    if not school:
        from app.models.master.school_level import SchoolLevel

        lvl = db.query(SchoolLevel).first()
        school = School(
            public_id=uuid.uuid4(),
            npsn="12345678",
            code="SCH_12345678",
            name="Test School",
            school_level_id=lvl.id,
            address="Test Address",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(school)
        db.flush()
    return school


@pytest.fixture
def test_superadmin(db, test_school):
    username = f"admin_{uuid.uuid4().hex[:4]}"
    password = "Password123!"
    hashed = hash_password(password)

    acc = AuthAccount(
        public_id=uuid.uuid4(),
        school_id=test_school.id,
        username=username,
        password_hash=hashed,
        role="SUPERADMIN",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(acc)
    db.flush()

    return {"account": acc, "username": username, "password": password}


@pytest.fixture
def test_teacher(db, test_school):
    username = f"teacher_{uuid.uuid4().hex[:4]}"
    password = "Password123!"
    hashed = hash_password(password)

    acc = AuthAccount(
        public_id=uuid.uuid4(),
        school_id=test_school.id,
        username=username,
        password_hash=hashed,
        role="TEACHER",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(acc)
    db.flush()

    return {"account": acc, "username": username, "password": password}


