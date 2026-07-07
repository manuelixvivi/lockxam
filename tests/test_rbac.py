def test_rbac_superadmin_access_allowed(client, test_superadmin):
    # Login as Superadmin
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": test_superadmin["username"], "password": test_superadmin["password"]},
    )
    access_token = login_res.json()["access_token"]

    # Access superadmin-only endpoint
    response = client.get(
        "/api/v1/auth/superadmin-only", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    assert "Superadmin" in response.json()["message"]


def test_rbac_teacher_access_denied(client, test_teacher):
    # Login as Teacher
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": test_teacher["username"], "password": test_teacher["password"]},
    )
    access_token = login_res.json()["access_token"]

    # Attempt to access superadmin-only endpoint
    response = client.get(
        "/api/v1/auth/superadmin-only", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 403
    assert "permission" in response.json()["detail"].lower()


def test_rbac_unauthenticated_access_denied(client):
    response = client.get("/api/v1/auth/superadmin-only")
    assert response.status_code == 401
