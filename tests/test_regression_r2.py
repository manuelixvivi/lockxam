from app.models.school.school import School


def test_toggle_school_subscription_syncs_status(client, test_superadmin, db):
    # Authenticate SuperAdmin
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": test_superadmin["username"], "password": test_superadmin["password"]},
    )
    sa_token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {sa_token}"}

    # Create school via API
    npsn = "99998888"
    school_res = client.post(
        "/api/v1/schools",
        headers=headers,
        json={
            "npsn": npsn,
            "name": "Toggle Test School",
            "domain": "toggle-test.sch.id",
            "school_level_id": 1,
        },
    )
    assert school_res.status_code == 201
    school_data = school_res.json()["school"]
    public_id = school_data["public_id"]
    school_id = school_data["id"]

    # Verify initial status is ACTIVE (auto-activated with license)
    db_school = db.query(School).filter(School.id == school_id).first()
    assert db_school.status == "ACTIVE"

    # Toggle subscription (Suspends)
    toggle_res = client.post(
        f"/api/v1/schools/{public_id}/toggle-subscription",
        headers=headers,
    )
    assert toggle_res.status_code == 200
    assert toggle_res.json()["subscription_status"] == "SUSPENDED"

    # Verify school.status is synchronized to SUSPENDED in DB
    db.refresh(db_school)
    assert db_school.status == "SUSPENDED"

    # Toggle subscription again (Activates)
    toggle_res2 = client.post(
        f"/api/v1/schools/{public_id}/toggle-subscription",
        headers=headers,
    )
    assert toggle_res2.status_code == 200
    assert toggle_res2.json()["subscription_status"] == "ACTIVE"

    # Verify school.status is synchronized to ACTIVE in DB
    db.refresh(db_school)
    assert db_school.status == "ACTIVE"


def test_create_school_returns_credentials(client, test_superadmin):
    # Authenticate SuperAdmin
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": test_superadmin["username"], "password": test_superadmin["password"]},
    )
    sa_token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {sa_token}"}

    # Create school via API
    school_res = client.post(
        "/api/v1/schools",
        headers=headers,
        json={
            "npsn": "12344321",
            "name": "Provision Test School",
            "domain": "provision.sch.id",
            "school_level_id": 1,
        },
    )
    assert school_res.status_code == 201
    data = school_res.json()

    # Prove that the response matches the new contract
    assert "school" in data
    assert "admin_credentials" in data

    # Prove that generated admin credential fields are returned
    creds = data["admin_credentials"]
    assert creds["username"] == "admin@admin.provision.sch.id"
    assert "temporary_password" in creds
    # Backend algorithm should generate password with SCH_ prefixed (from auto generated code)
    assert creds["temporary_password"].startswith("eQu!6r4de@SCH_")

    # Prove that password_hash is not returned in admin_credentials
    assert "password_hash" not in creds
    assert "password_hash" not in data["school"]


def test_list_activation_keys_rbac_and_ordering(client, test_superadmin, test_teacher):
    # 1. Access as guest -> 401 Unauthorized
    guest_res = client.get("/api/v1/licenses/keys")
    assert guest_res.status_code == 401

    # 2. Access as Teacher -> 403 Forbidden
    teacher_login = client.post(
        "/api/v1/auth/login",
        json={"username": test_teacher["username"], "password": test_teacher["password"]},
    )
    teacher_token = teacher_login.json()["access_token"]
    teacher_res = client.get(
        "/api/v1/licenses/keys",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert teacher_res.status_code == 403

    # 3. Access as SuperAdmin -> 200 OK
    sa_login = client.post(
        "/api/v1/auth/login",
        json={"username": test_superadmin["username"], "password": test_superadmin["password"]},
    )
    sa_token = sa_login.json()["access_token"]
    sa_headers = {"Authorization": f"Bearer {sa_token}"}

    sa_res = client.get(
        "/api/v1/licenses/keys",
        headers=sa_headers,
    )
    assert sa_res.status_code == 200
    keys_list = sa_res.json()
    assert isinstance(keys_list, list)

    # Verify descending ordering by created_at (if keys exist)
    if len(keys_list) > 1:
        created_times = [k["created_at"] for k in keys_list]
        assert created_times == sorted(created_times, reverse=True)


def test_must_change_password_exposed_via_me(client, db, test_superadmin, test_teacher):
    from app.models.security.auth_account import AuthAccount

    # 1. Check SuperAdmin with must_change_password=True
    sa_acc = (
        db.query(AuthAccount).filter(AuthAccount.username == test_superadmin["username"]).first()
    )
    sa_acc.must_change_password = True
    db.commit()

    sa_login = client.post(
        "/api/v1/auth/login",
        json={"username": test_superadmin["username"], "password": test_superadmin["password"]},
    )
    sa_token = sa_login.json()["access_token"]
    sa_me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {sa_token}"})
    assert sa_me.status_code == 200
    assert sa_me.json()["must_change_password"] is True

    # 2. Check Teacher with must_change_password=False
    teacher_acc = (
        db.query(AuthAccount).filter(AuthAccount.username == test_teacher["username"]).first()
    )
    teacher_acc.must_change_password = False
    db.commit()

    t_login = client.post(
        "/api/v1/auth/login",
        json={"username": test_teacher["username"], "password": test_teacher["password"]},
    )
    t_token = t_login.json()["access_token"]
    t_me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {t_token}"})
    assert t_me.status_code == 200
    assert t_me.json()["must_change_password"] is False
