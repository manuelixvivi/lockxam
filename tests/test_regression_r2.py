import uuid
from datetime import datetime, timezone

from app.core.security.password import hash_password
from app.models.school.school import School
from app.models.security.enums import UserRole


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


# =============================================================================
# R2 REGRESSION TESTS: BACKEND ENFORCEMENT OF FORCED PASSWORD CHANGE
# =============================================================================


def test_forced_password_change_blocks_all_non_exempt_endpoints(client, db, test_teacher):
    """User with must_change_password=True is strictly blocked (HTTP 403) from all non-exempt endpoints."""
    from app.models.security.auth_account import AuthAccount

    teacher_acc = (
        db.query(AuthAccount).filter(AuthAccount.username == test_teacher["username"]).first()
    )
    teacher_acc.must_change_password = True
    db.commit()

    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": test_teacher["username"], "password": test_teacher["password"]},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Blocked: /auth/sessions
    res_sessions = client.get("/api/v1/auth/sessions", headers=headers)
    assert res_sessions.status_code == 403
    assert "Harap ubah kata sandi Anda sebelum melanjutkan" in res_sessions.json().get("detail", "")

    # 2. Blocked: /schools
    res_schools = client.get("/api/v1/schools", headers=headers)
    assert res_schools.status_code == 403
    assert "Harap ubah kata sandi Anda sebelum melanjutkan" in res_schools.json().get("detail", "")

    # 3. Blocked: /licenses/keys
    res_keys = client.get("/api/v1/licenses/keys", headers=headers)
    assert res_keys.status_code == 403
    assert "Harap ubah kata sandi Anda sebelum melanjutkan" in res_keys.json().get("detail", "")

    # 4. Blocked: /auth/logout-all
    res_logout_all = client.post("/api/v1/auth/logout-all", headers=headers)
    assert res_logout_all.status_code == 403
    assert "Harap ubah kata sandi Anda sebelum melanjutkan" in res_logout_all.json().get("detail", "")

    # 5. Blocked: /auth/superadmin-only
    res_sa = client.get("/api/v1/auth/superadmin-only", headers=headers)
    assert res_sa.status_code == 403
    assert "Harap ubah kata sandi Anda sebelum melanjutkan" in res_sa.json().get("detail", "")


def test_forced_password_change_allows_strictly_exempt_endpoints(client, db, test_teacher):
    """User with must_change_password=True can access strictly /auth/me and /auth/logout."""
    from app.models.security.auth_account import AuthAccount

    teacher_acc = (
        db.query(AuthAccount).filter(AuthAccount.username == test_teacher["username"]).first()
    )
    teacher_acc.must_change_password = True
    db.commit()

    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": test_teacher["username"], "password": test_teacher["password"]},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Allowed: /auth/me returns 200 and reveals must_change_password=True
    res_me = client.get("/api/v1/auth/me", headers=headers)
    assert res_me.status_code == 200
    assert res_me.json()["must_change_password"] is True

    # 2. Allowed: /auth/logout returns 204
    res_logout = client.post("/api/v1/auth/logout", headers=headers)
    assert res_logout.status_code == 204


def test_forced_password_change_workflow_and_recovery(client, db, test_teacher):
    """Full workflow: must_change_password=True -> blocked -> password changed -> unblocked."""
    from app.models.security.auth_account import AuthAccount

    old_password = test_teacher["password"]
    new_password = "NewStrongPassword456!"

    teacher_acc = (
        db.query(AuthAccount).filter(AuthAccount.username == test_teacher["username"]).first()
    )
    teacher_acc.must_change_password = True
    db.commit()

    # 1. Login with old password
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": test_teacher["username"], "password": old_password},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Verify blocked from general endpoint
    assert client.get("/api/v1/auth/sessions", headers=headers).status_code == 403

    # 3. Change password via exempt endpoint /auth/change-password
    change_res = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"old_password": old_password, "new_password": new_password},
    )
    assert change_res.status_code == 200
    assert "berhasil" in change_res.json().get("message", "").lower()

    # 4. Old session revoked by password change, relogin with new password
    new_login = client.post(
        "/api/v1/auth/login",
        json={"username": test_teacher["username"], "password": new_password},
    )
    assert new_login.status_code == 200
    assert new_login.json()["must_change_password"] is False
    new_token = new_login.json()["access_token"]
    new_headers = {"Authorization": f"Bearer {new_token}"}

    # 5. Verify /auth/me shows must_change_password=False
    me_res = client.get("/api/v1/auth/me", headers=new_headers)
    assert me_res.status_code == 200
    assert me_res.json()["must_change_password"] is False

    # 6. Verify previously blocked endpoint is now accessible!
    sessions_res = client.get("/api/v1/auth/sessions", headers=new_headers)
    assert sessions_res.status_code == 200


def test_forced_password_change_blocks_student_exam_endpoints(client, db, test_school):
    """Student with must_change_password=True is blocked from exam endpoints even via APK."""
    from app.models.security.auth_account import AuthAccount

    student_uname = f"std_pwd_{uuid.uuid4().hex[:6]}"
    student_pw = "InitialPassword123!"
    acc = AuthAccount(
        public_id=uuid.uuid4(),
        school_id=test_school.id,
        username=student_uname,
        password_hash=hash_password(student_pw),
        role=UserRole.STUDENT,
        is_active=True,
        must_change_password=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    acc._keep_must_change_password = True
    db.add(acc)
    db.commit()

    # Login as student via APK
    login_res = client.post(
        "/api/v1/auth/login",
        headers={"x-client-app": "lockxam_apk"},
        json={"username": student_uname, "password": student_pw},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}", "x-client-app": "lockxam_apk"}

    # Blocked from exam my-schedules endpoint
    res_exam = client.get("/api/v1/exam/my-schedules", headers=headers)
    assert res_exam.status_code == 403
    assert "Harap ubah kata sandi Anda sebelum melanjutkan" in res_exam.json().get("detail", "")

    # Allowed on /auth/me
    res_me = client.get("/api/v1/auth/me", headers=headers)
    assert res_me.status_code == 200
    assert res_me.json()["must_change_password"] is True

