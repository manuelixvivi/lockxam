from app.models.user_session import UserSession


def test_list_active_sessions(client, test_superadmin):
    # Login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": test_superadmin["username"], "password": test_superadmin["password"]},
    )
    assert login_res.status_code == 200
    access_token = login_res.json()["access_token"]

    # Get sessions
    sessions_res = client.get(
        "/api/v1/auth/sessions", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert sessions_res.status_code == 200
    data = sessions_res.json()
    assert len(data) == 1
    assert data[0]["is_current"] is True
    assert "session_id" in data[0]


def test_revoke_specific_session(client, test_superadmin, db):
    # Login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": test_superadmin["username"], "password": test_superadmin["password"]},
    )
    access_token = login_res.json()["access_token"]

    # Get sessions list
    sessions_res = client.get(
        "/api/v1/auth/sessions", headers={"Authorization": f"Bearer {access_token}"}
    )
    session_id = sessions_res.json()[0]["session_id"]

    # Revoke session
    revoke_res = client.post(
        f"/api/v1/auth/revoke-session/{session_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert revoke_res.status_code == 200
    assert "revoked" in revoke_res.json()["message"].lower()

    # Verify session is revoked
    db_session = db.query(UserSession).filter(UserSession.id == session_id).first()
    assert db_session.revoked is True


def test_revoke_session_unauthorized_cross_user(client, test_superadmin, test_teacher, db):
    # Login as teacher
    teacher_login = client.post(
        "/api/v1/auth/login",
        json={"username": test_teacher["username"], "password": test_teacher["password"]},
    )
    teacher_token = teacher_login.json()["access_token"]

    # Login as admin to get admin session ID
    admin_login = client.post(
        "/api/v1/auth/login",
        json={"username": test_superadmin["username"], "password": test_superadmin["password"]},
    )
    admin_token = admin_login.json()["access_token"]

    admin_sessions = client.get(
        "/api/v1/auth/sessions", headers={"Authorization": f"Bearer {admin_token}"}
    )
    admin_session_id = admin_sessions.json()[0]["session_id"]

    # Teacher attempts to revoke Admin's session (should return 403)
    revoke_res = client.post(
        f"/api/v1/auth/revoke-session/{admin_session_id}",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert revoke_res.status_code == 403


def test_logout_all_sessions(client, test_superadmin, db):
    # Perform 2 logins to create 2 sessions
    client.post(
        "/api/v1/auth/login",
        json={"username": test_superadmin["username"], "password": test_superadmin["password"]},
    )

    login_2 = client.post(
        "/api/v1/auth/login",
        json={"username": test_superadmin["username"], "password": test_superadmin["password"]},
    )
    token_2 = login_2.json()["access_token"]

    # Get active sessions count (should be 2)
    sessions_res = client.get(
        "/api/v1/auth/sessions", headers={"Authorization": f"Bearer {token_2}"}
    )
    assert len(sessions_res.json()) == 2

    # Logout all
    logout_all_res = client.post(
        "/api/v1/auth/logout-all", headers={"Authorization": f"Bearer {token_2}"}
    )
    assert logout_all_res.status_code == 200

    # Verify both sessions are revoked
    user_id = test_superadmin["account"].id
    active_sessions = (
        db.query(UserSession)
        .filter(UserSession.auth_account_id == user_id, UserSession.revoked == False)
        .all()
    )
    assert len(active_sessions) == 0
