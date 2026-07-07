from app.models.security.activity_log import ActivityLog


def test_login_activity_logged(client, test_superadmin, db):
    # Perform login
    response = client.post(
        "/api/v1/auth/login",
        json={"username": test_superadmin["username"], "password": test_superadmin["password"]},
        headers={"User-Agent": "TestAgent123"},
    )
    assert response.status_code == 200

    # Query activity logs for this user
    user_id = test_superadmin["account"].id
    logs = db.query(ActivityLog).filter(ActivityLog.auth_account_id == user_id).all()
    assert len(logs) >= 1

    login_log = next(log for log in logs if log.action_name == "LOGIN_SUCCESS")
    assert login_log.action_type == "AUTH"
    assert login_log.endpoint == "/api/v1/auth/login"
    assert login_log.method == "POST"
    assert login_log.user_agent == "TestAgent123"


def test_logout_activity_logged(client, test_superadmin, db):
    # Login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": test_superadmin["username"], "password": test_superadmin["password"]},
    )
    access_token = login_res.json()["access_token"]

    # Logout
    logout_res = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access_token}", "User-Agent": "LogoutAgent"},
    )
    assert logout_res.status_code == 204

    # Verify logout activity is recorded
    user_id = test_superadmin["account"].id
    logs = (
        db.query(ActivityLog)
        .filter(ActivityLog.auth_account_id == user_id, ActivityLog.action_name == "LOGOUT")
        .all()
    )

    assert len(logs) == 1
    assert logs[0].action_type == "AUTH"
    assert logs[0].user_agent == "LogoutAgent"
