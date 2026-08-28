from datetime import datetime, timezone, timedelta
from app.models.security.user_session import UserSession
from app.models.security.auth_account import AuthAccount

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
    session = db.query(UserSession).filter(UserSession.auth_account_id == test_superadmin["account"].id).order_by(UserSession.created_at.desc()).first()
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
    session = db.query(UserSession).filter(UserSession.auth_account_id == test_superadmin["account"].id).order_by(UserSession.created_at.desc()).first()
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
    
    session = db.query(UserSession).filter(UserSession.auth_account_id == test_superadmin["account"].id).order_by(UserSession.created_at.desc()).first()
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
    
    session = db.query(UserSession).filter(UserSession.auth_account_id == test_superadmin["account"].id).order_by(UserSession.created_at.desc()).first()
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
    
    session = db.query(UserSession).filter(UserSession.auth_account_id == test_superadmin["account"].id).order_by(UserSession.created_at.desc()).first()
    assert session.revoked is False
    
    # 2. Logout (G)
    logout_res = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
        cookies={"refresh_token": refresh_cookie}
    )
    assert logout_res.status_code == 204
    
    # Assert session is revoked in DB (G)
    db.refresh(session)
    assert session.revoked is True
    assert session.revoked_reason == "LOGOUT"
