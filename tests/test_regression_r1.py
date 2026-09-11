import uuid
from datetime import datetime, timezone

from app.core.security.password import hash_password
from app.models.security.auth_account import AuthAccount
from app.models.security.enums import UserRole
from app.models.security.user_session import UserSession
from app.repositories.exam.attempt_repository import attempt_repository
from app.repositories.exam.checkin_repository import checkin_repository


def test_web_login_session_duration(client, test_superadmin, db):
    # Web login - default headers (not APK)
    res = client.post(
        "/api/v1/auth/login",
        json={"username": test_superadmin["username"], "password": test_superadmin["password"]},
    )
    assert res.status_code == 200
    data = res.json()

    # Assert refresh_token is NOT in JSON body (F)
    assert data.get("refresh_token") is None

    # Assert session_expires_in is ~12 hours (A)
    assert data["session_expires_in"] is not None
    assert abs(data["session_expires_in"] - 12 * 60 * 60) < 10

    # Check database session expiration (A)
    session = (
        db.query(UserSession)
        .filter(UserSession.auth_account_id == test_superadmin["account"].id)
        .order_by(UserSession.created_at.desc())
        .first()
    )
    assert session is not None

    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    diff = expires_at - datetime.now(timezone.utc)
    assert abs(diff.total_seconds() - 12 * 60 * 60) < 10


def test_apk_login_session_duration(client, test_superadmin, db):
    # APK login - pass LockxamBrowser user agent
    res = client.post(
        "/api/v1/auth/login",
        headers={"user-agent": "LockxamBrowser/1.0"},
        json={"username": test_superadmin["username"], "password": test_superadmin["password"]},
    )
    assert res.status_code == 200
    data = res.json()

    # Assert session_expires_in is ~30 days (B)
    assert data["session_expires_in"] is not None
    assert abs(data["session_expires_in"] - 30 * 24 * 60 * 60) < 10

    # Check database session expiration (B)
    session = (
        db.query(UserSession)
        .filter(UserSession.auth_account_id == test_superadmin["account"].id)
        .order_by(UserSession.created_at.desc())
        .first()
    )
    assert session is not None

    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    diff = expires_at - datetime.now(timezone.utc)
    assert abs(diff.total_seconds() - 30 * 24 * 60 * 60) < 10


def test_web_refresh_rotation_preserves_expiry(client, test_superadmin, db):
    # 1. Login web
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": test_superadmin["username"], "password": test_superadmin["password"]},
    )
    assert login_res.status_code == 200
    refresh_cookie = login_res.cookies.get("refresh_token")
    assert refresh_cookie is not None

    session = (
        db.query(UserSession)
        .filter(UserSession.auth_account_id == test_superadmin["account"].id)
        .order_by(UserSession.created_at.desc())
        .first()
    )
    original_expires_at = session.expires_at

    # 2. Wait or fake time check, let's refresh
    refresh_res = client.post("/api/v1/auth/refresh", cookies={"refresh_token": refresh_cookie})
    assert refresh_res.status_code == 200
    data = refresh_res.json()

    # Assert refresh_token is NOT in JSON response (F)
    assert data.get("refresh_token") is None

    # Refresh token cookie rotated
    new_cookie = refresh_res.cookies.get("refresh_token")
    assert new_cookie is not None
    assert new_cookie != refresh_cookie

    # Verify absolute session expiration remains unchanged (C)
    db.refresh(session)
    assert session.expires_at == original_expires_at


def test_apk_refresh_rotation_preserves_expiry(client, test_superadmin, db):
    # 1. Login APK
    login_res = client.post(
        "/api/v1/auth/login",
        headers={"x-client-app": "lockxam_apk"},
        json={"username": test_superadmin["username"], "password": test_superadmin["password"]},
    )
    assert login_res.status_code == 200
    refresh_cookie = login_res.cookies.get("refresh_token")
    assert refresh_cookie is not None

    session = (
        db.query(UserSession)
        .filter(UserSession.auth_account_id == test_superadmin["account"].id)
        .order_by(UserSession.created_at.desc())
        .first()
    )
    original_expires_at = session.expires_at

    # 2. Refresh
    refresh_res = client.post("/api/v1/auth/refresh", cookies={"refresh_token": refresh_cookie})
    assert refresh_res.status_code == 200
    new_cookie = refresh_res.cookies.get("refresh_token")
    assert new_cookie is not None
    assert new_cookie != refresh_cookie

    # Verify absolute session expiration remains unchanged (D)
    db.refresh(session)
    assert session.expires_at == original_expires_at


def test_refresh_only_reads_httponly_cookie(client, test_superadmin):
    # Try refresh with empty cookie
    res = client.post("/api/v1/auth/refresh")
    assert res.status_code == 401
    assert "missing" in res.json()["detail"].lower()

    # Try refresh with body instead of cookie (E)
    res2 = client.post("/api/v1/auth/refresh", json={"refresh_token": "some_token"})
    assert res2.status_code == 401
    assert "missing" in res2.json()["detail"].lower()


def test_logout_deletes_cookie_and_revokes_db_session(client, test_superadmin, db):
    # 1. Login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": test_superadmin["username"], "password": test_superadmin["password"]},
    )
    assert login_res.status_code == 200
    access_token = login_res.json()["access_token"]
    refresh_cookie = login_res.cookies.get("refresh_token")

    session = (
        db.query(UserSession)
        .filter(UserSession.auth_account_id == test_superadmin["account"].id)
        .order_by(UserSession.created_at.desc())
        .first()
    )
    assert session.revoked is False

    # 2. Logout (G)
    logout_res = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
        cookies={"refresh_token": refresh_cookie},
    )
    assert logout_res.status_code == 204

    # Assert session is revoked in DB (G)
    db.refresh(session)
    assert session.revoked is True
    assert session.revoked_reason == "LOGOUT"


# =============================================================================
# R1 REGRESSION TESTS: ABSOLUTE ELIMINATION OF STUDENT BROWSER BYPASS
# =============================================================================


def _create_student_account(db, school_id):
    username = f"student_{uuid.uuid4().hex[:6]}"
    password = "StudentPassword123!"
    acc = AuthAccount(
        public_id=uuid.uuid4(),
        school_id=school_id,
        username=username,
        password_hash=hash_password(password),
        role=UserRole.STUDENT,
        is_active=True,
        must_change_password=False,
        name="Test Student",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    acc._keep_must_change_password = True
    db.add(acc)
    db.commit()
    return {"account": acc, "username": username, "password": password}


def test_student_login_rejected_from_web_browser(client, db, test_school):
    """Student logging in from normal browser without APK headers must strictly receive HTTP 403."""
    student = _create_student_account(db, test_school.id)
    res = client.post(
        "/api/v1/auth/login",
        headers={"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"},
        json={"username": student["username"], "password": student["password"]},
    )
    assert res.status_code == 403
    assert "Akun siswa hanya dapat diakses melalui aplikasi resmi Lockxam APK" in res.json().get("detail", "")


def test_student_login_with_x_lockxam_dev_bypass_fails_403(client, db, test_school):
    """Header x-lockxam-dev-bypass: true must be completely eliminated and rejected with HTTP 403."""
    student = _create_student_account(db, test_school.id)
    res = client.post(
        "/api/v1/auth/login",
        headers={
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
            "x-lockxam-dev-bypass": "true",
        },
        json={"username": student["username"], "password": student["password"]},
    )
    assert res.status_code == 403
    assert "Akun siswa hanya dapat diakses melalui aplikasi resmi Lockxam APK" in res.json().get("detail", "")


def test_student_login_with_cookie_secure_false_bypass_fails_403(client, db, test_school, monkeypatch):
    """COOKIE_SECURE=false environment variable must not bypass the APK check for student login."""
    monkeypatch.setenv("COOKIE_SECURE", "false")
    student = _create_student_account(db, test_school.id)
    res = client.post(
        "/api/v1/auth/login",
        headers={"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"},
        json={"username": student["username"], "password": student["password"]},
    )
    assert res.status_code == 403
    assert "Akun siswa hanya dapat diakses melalui aplikasi resmi Lockxam APK" in res.json().get("detail", "")


def test_student_login_success_with_apk_headers(client, db, test_school):
    """Student login succeeds (200 OK) when authentic APK headers are present."""
    student = _create_student_account(db, test_school.id)

    # 1. Via x-client-app header
    res_apk = client.post(
        "/api/v1/auth/login",
        headers={"x-client-app": "lockxam_apk"},
        json={"username": student["username"], "password": student["password"]},
    )
    assert res_apk.status_code == 200
    assert "access_token" in res_apk.json()

    # 2. Via Lockxam user-agent
    res_ua = client.post(
        "/api/v1/auth/login",
        headers={"user-agent": "LockxamBrowser/1.0.4"},
        json={"username": student["username"], "password": student["password"]},
    )
    assert res_ua.status_code == 200
    assert "access_token" in res_ua.json()


def test_student_endpoint_access_rejected_without_apk(client, db, test_school):
    """Authenticated student accessing endpoints from non-APK browser must fail closed with HTTP 403."""
    student = _create_student_account(db, test_school.id)

    # Login via APK
    login_res = client.post(
        "/api/v1/auth/login",
        headers={"x-client-app": "lockxam_apk"},
        json={"username": student["username"], "password": student["password"]},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    # Access endpoint without APK headers (e.g. browser User-Agent)
    res_me = client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": f"Bearer {token}",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
        },
    )
    assert res_me.status_code == 403
    assert "Akun siswa hanya dapat diakses melalui aplikasi resmi Lockxam APK" in res_me.json().get("detail", "")


def test_student_endpoint_access_allowed_with_apk(client, db, test_school):
    """Authenticated student accessing endpoints with APK headers succeeds with HTTP 200."""
    student = _create_student_account(db, test_school.id)

    # Login via APK
    login_res = client.post(
        "/api/v1/auth/login",
        headers={"x-client-app": "lockxam_apk"},
        json={"username": student["username"], "password": student["password"]},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    # Access endpoint with APK header
    res_me = client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": f"Bearer {token}",
            "x-client-app": "lockxam_apk",
        },
    )
    assert res_me.status_code == 200
    assert res_me.json()["username"] == student["username"]
    assert res_me.json()["role"] == "STUDENT"


def test_student_single_device_binding_unconditional(client, db, test_school, monkeypatch):
    """Single-device binding must be strictly unconditional (no COOKIE_SECURE bypass)."""
    monkeypatch.setenv("COOKIE_SECURE", "false")
    student = _create_student_account(db, test_school.id)

    # First login on device 1
    login1 = client.post(
        "/api/v1/auth/login",
        headers={"x-client-app": "lockxam_apk"},
        json={"username": student["username"], "password": student["password"]},
    )
    assert login1.status_code == 200

    # Simulate student has active QR checkin
    monkeypatch.setattr(checkin_repository, "has_student_checkin", lambda db, uid: True)

    # Attempt second login on device 2 -> MUST be rejected with HTTP 403
    login2 = client.post(
        "/api/v1/auth/login",
        headers={"x-client-app": "lockxam_apk"},
        json={"username": student["username"], "password": student["password"]},
    )
    assert login2.status_code == 403
    assert "Kunci Keamanan Presensi QR" in login2.json().get("detail", "")

    # Reset checkin, simulate active exam attempt
    monkeypatch.setattr(checkin_repository, "has_student_checkin", lambda db, uid: False)
    monkeypatch.setattr(attempt_repository, "has_active_or_paused", lambda db, uid: True)

    # Attempt second login on device 2 with active exam -> MUST be rejected with HTTP 403
    login3 = client.post(
        "/api/v1/auth/login",
        headers={"x-client-app": "lockxam_apk"},
        json={"username": student["username"], "password": student["password"]},
    )
    assert login3.status_code == 403
    assert "Kunci Keamanan Presensi QR" in login3.json().get("detail", "")

