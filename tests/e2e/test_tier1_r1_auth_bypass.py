"""
Tier 1: Feature Coverage — R1: Elimination of Student Browser Bypass & Non-APK Fail-Closed Guard
Authoritative Sources:
- ORIGINAL_REQUEST.md § R1
- PROJECT.md § Feature Inventory (Features 1, 2, 3, 4) & § Interface Contracts (Auth & Forced Password Change)
"""



def test_student_login_browser_no_bypass_fails_403(client, test_student, browser_headers):
    """
    R1 / Feature 4: Standard browser student login must fail closed with HTTP 403 Forbidden.
    """
    res = client.post(
        "/api/v1/auth/login",
        headers=browser_headers,
        json={"username": test_student["username"], "password": test_student["password"]},
    )
    assert res.status_code == 403
    data = res.json()
    assert "detail" in data
    assert "lockxam apk" in data["detail"].lower() or "aplikasi resmi" in data["detail"].lower()


def test_student_login_with_x_lockxam_dev_bypass_fails_403(client, test_student, browser_headers):
    """
    R1 / Feature 1: Sending 'x-lockxam-dev-bypass: true' must NOT bypass APK requirement.
    Must fail closed with HTTP 403.
    """
    headers = {**browser_headers, "x-lockxam-dev-bypass": "true"}
    res = client.post(
        "/api/v1/auth/login",
        headers=headers,
        json={"username": test_student["username"], "password": test_student["password"]},
    )
    assert res.status_code == 403
    data = res.json()
    assert "lockxam apk" in data["detail"].lower() or "aplikasi resmi" in data["detail"].lower()


def test_student_login_cookie_secure_false_env_fails_403(
    client, test_student, browser_headers, monkeypatch
):
    """
    R1 / Feature 2: Setting COOKIE_SECURE=false must NOT bypass student APK verification.
    """
    monkeypatch.setenv("COOKIE_SECURE", "false")
    res = client.post(
        "/api/v1/auth/login",
        headers=browser_headers,
        json={"username": test_student["username"], "password": test_student["password"]},
    )
    assert res.status_code == 403
    data = res.json()
    assert "lockxam apk" in data["detail"].lower() or "aplikasi resmi" in data["detail"].lower()


def test_student_login_query_params_bypass_fails_403(client, test_student, browser_headers):
    """
    R1 / Feature 3: Query parameters such as ?bypass=true or ?dev=1 must not bypass APK verification.
    """
    res = client.post(
        "/api/v1/auth/login?bypass=true&dev=1&lockxam_dev_bypass=true",
        headers=browser_headers,
        json={"username": test_student["username"], "password": test_student["password"]},
    )
    assert res.status_code == 403


def test_student_valid_apk_login_succeeds_200(client, test_student, apk_headers):
    """
    R1 / Feature 4: Valid APK headers allow student authentication returning HTTP 200.
    """
    res = client.post(
        "/api/v1/auth/login",
        headers=apk_headers,
        json={"username": test_student["username"], "password": test_student["password"]},
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["role"].upper() == "STUDENT"
    assert "session_expires_in" in data


def test_teacher_superadmin_browser_login_allowed_200(
    client, test_teacher, test_superadmin, browser_headers
):
    """
    R1: Non-student roles (Teacher, SuperAdmin) are allowed to login via standard web browser.
    """
    # Teacher web login
    t_res = client.post(
        "/api/v1/auth/login",
        headers=browser_headers,
        json={"username": test_teacher["username"], "password": test_teacher["password"]},
    )
    assert t_res.status_code == 200
    assert t_res.json()["role"].upper() == "TEACHER"

    # SuperAdmin web login
    sa_res = client.post(
        "/api/v1/auth/login",
        headers=browser_headers,
        json={"username": test_superadmin["username"], "password": test_superadmin["password"]},
    )
    assert sa_res.status_code == 200
    assert sa_res.json()["role"].upper() == "SUPERADMIN"
