from app.models.security.user_session import UserSession


def test_logout_success(client, test_superadmin, db):
    # Log in to get token
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": test_superadmin["username"], "password": test_superadmin["password"]},
    )
    assert login_res.status_code == 200
    access_token = login_res.json()["access_token"]

    # Logout
    logout_res = client.post(
        "/api/v1/auth/logout", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert logout_res.status_code == 204

    # Verify session is marked revoked in database
    session_res = (
        db.query(UserSession)
        .filter(UserSession.auth_account_id == test_superadmin["account"].id)
        .first()
    )
    assert session_res.revoked is True
    assert session_res.revoked_reason == "LOGOUT"

    # Attempting to access /me with logged out token should fail
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert me_res.status_code == 401
    assert "revoked" in me_res.json()["detail"].lower()


def test_logout_unauthorized(client):
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 401
