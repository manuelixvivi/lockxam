import os
import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.models.school.school import School
from app.models.security.auth_account import AuthAccount
from main import app

DATABASE_URL = os.getenv("DATABASE_URL", "")
engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    # Make sure all tables exist before running test suite
    Base.metadata.create_all(bind=engine)
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
        school = School(
            public_id=uuid.uuid4(),
            code=f"SCH_{uuid.uuid4().hex[:4]}",
            name="Test School",
            address="Test Address",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
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
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
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
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(acc)
    db.flush()

    return {"account": acc, "username": username, "password": password}
