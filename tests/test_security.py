from datetime import datetime, timedelta

import pytest
from jose import jwt

from app.core.security import (
    ACTIVE_KEY_ID,
    validate_password_strength,
    verify_token,
)
from app.exceptions import ValidationException
from app.models.security.user_session import UserSession


def test_password_policy():
    # Test weak passwords
    with pytest.raises(ValidationException):
        validate_password_strength("weak")  # Too short

    with pytest.raises(ValidationException):
        validate_password_strength("NoNumberAndSymbol")  # Missing digits and symbols

    with pytest.raises(ValidationException):
        validate_password_strength("WithNum123")  # Missing symbols

    # Test strong password
    validate_password_strength("StrongPass123!")  # Should pass


def test_jwt_kid_rotation_and_verification(client, test_superadmin):
    # 1. Login to get token
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": test_superadmin["username"], "password": test_superadmin["password"]},
    )
    assert login_res.status_code == 200
    access_token = login_res.json()["access_token"]

    # 2. Check JWT headers and payloads
    headers = jwt.get_unverified_header(access_token)
    assert headers.get("kid") == ACTIVE_KEY_ID

    payload = verify_token(access_token)
    assert payload.get("ver") == 1


def test_login_rate_limiting_lockout(client, test_superadmin, db):
    username = test_superadmin["username"]

    # Perform 5 failed logins (should return 401 Invalid credentials)
    for _ in range(5):
        res = client.post(
            "/api/v1/auth/login", json={"username": username, "password": "WrongPassword!"}
        )
        assert res.status_code == 401
        # The first 4 will say invalid, the 5th fails with credentials but increments to 5
        # actually, the 5th attempt still raises Invalid credentials but marks it blocked
        # let's verify if the response is either invalid or locked
        detail = res.json()["detail"].lower()
        assert "invalid" in detail or "locked" in detail

    # The 6th attempt (should trigger lockout and return locked message)
    res_6 = client.post(
        "/api/v1/auth/login", json={"username": username, "password": "WrongPassword!"}
    )
    assert res_6.status_code == 401
    assert "locked" in res_6.json()["detail"].lower()

    # A subsequent attempt with the CORRECT password should still fail (locked out)
    res_correct = client.post(
        "/api/v1/auth/login", json={"username": username, "password": test_superadmin["password"]}
    )
    assert res_correct.status_code == 401
    assert "locked" in res_correct.json()["detail"].lower()


def test_session_idle_timeout(client, test_superadmin, db):
    # 1. Login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": test_superadmin["username"], "password": test_superadmin["password"]},
    )
    access_token = login_res.json()["access_token"]

    # Get session ID
    payload = verify_token(access_token)
    session_id = payload["sid"]

    # 2. Simulate 3 hours of inactivity in the database
    db_session = db.query(UserSession).filter(UserSession.id == session_id).first()
    db_session.last_activity_at = datetime.utcnow() - timedelta(hours=3)
    db.commit()

    # 3. Accessing /me should now fail because of inactivity
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert me_res.status_code == 401
    assert "inactivity" in me_res.json()["detail"].lower()

    # 4. Verify session is marked revoked in database
    db.refresh(db_session)
    assert db_session.revoked is True
    assert db_session.revoked_reason == "IDLE_TIMEOUT"
