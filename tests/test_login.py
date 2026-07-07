from app.models.auth_account import AuthAccount


def test_login_success(client, test_superadmin):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": test_superadmin["username"], "password": test_superadmin["password"]},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["role"] == "SUPERADMIN"
    assert data["token_type"] == "bearer"


def test_login_invalid_credentials(client, test_superadmin):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": test_superadmin["username"], "password": "WrongPassword!"},
    )
    assert response.status_code == 401
    assert "credentials" in response.json()["detail"].lower()


def test_login_inactive_account(client, db, test_superadmin):
    # Set user to inactive
    acc = db.query(AuthAccount).filter(AuthAccount.username == test_superadmin["username"]).first()
    acc.is_active = False
    db.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"username": test_superadmin["username"], "password": test_superadmin["password"]},
    )
    assert response.status_code == 403
    assert "inactive" in response.json()["detail"].lower()


def test_login_updates_last_login(client, db, test_superadmin):
    acc_before = (
        db.query(AuthAccount).filter(AuthAccount.username == test_superadmin["username"]).first()
    )
    assert acc_before.last_login is None

    response = client.post(
        "/api/v1/auth/login",
        json={"username": test_superadmin["username"], "password": test_superadmin["password"]},
    )
    assert response.status_code == 200

    db.refresh(acc_before)
    assert acc_before.last_login is not None
