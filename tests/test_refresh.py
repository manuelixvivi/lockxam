from app.models.security.user_session import UserSession


def test_refresh_token_rotation(client, test_superadmin):
    # 1. Login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": test_superadmin["username"], "password": test_superadmin["password"]},
    )
    assert login_res.status_code == 200
    access_token = login_res.json()["access_token"]
    refresh_token = login_res.json()["refresh_token"]

    # 2. Refresh tokens
    refresh_res = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_res.status_code == 200
    data = refresh_res.json()
    assert "access_token" in data
    assert "refresh_token" in data

    new_access = data["access_token"]
    new_refresh = data["refresh_token"]
    assert new_access != access_token
    assert new_refresh != refresh_token


def test_refresh_token_reuse_detection(client, test_superadmin, db):
    # 1. Login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": test_superadmin["username"], "password": test_superadmin["password"]},
    )
    refresh_token = login_res.json()["refresh_token"]

    # 2. Refresh first time (rotates token)
    first_refresh = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert first_refresh.status_code == 200
    new_access = first_refresh.json()["access_token"]

    # 3. Refresh second time with same OLD refresh token (replay attack!)
    second_refresh = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert second_refresh.status_code == 401
    assert "reuse" in second_refresh.json()["detail"].lower()

    # 4. Verify the entire session is revoked in database
    session_res = (
        db.query(UserSession)
        .filter(UserSession.auth_account_id == test_superadmin["account"].id)
        .first()
    )
    assert session_res.revoked is True
    assert session_res.revoked_reason == "REFRESH_TOKEN_REUSE_DETECTED"

    # 5. Accessing with the new access token generated from the first refresh should also now fail
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {new_access}"})
    assert me_res.status_code == 401
