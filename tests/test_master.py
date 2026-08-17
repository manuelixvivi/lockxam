from app.services.master.master_data_service import MasterDataService


def test_master_data_service(db):
    levels = MasterDataService.get_all_school_levels(db)
    assert len(levels) > 0
    codes = [lvl.code for lvl in levels]
    assert "TK" in codes
    assert "SD" in codes

    licenses = MasterDataService.get_all_license_types(db)
    assert len(licenses) > 0
    license_codes = [lic.code for lic in licenses]
    assert "ONE_WEEK" in license_codes
    assert "PERMANENT" in license_codes


def test_master_api_school_levels(client, test_superadmin):
    # Access without auth
    res = client.get("/api/v1/master/school-levels")
    assert res.status_code == 401

    # Authenticate
    login_res = client.post(
        "/api/v1/auth/login",
        json={
            "username": test_superadmin["username"],
            "password": test_superadmin["password"],
        },
    )
    access_token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # Access with auth
    res = client.get("/api/v1/master/school-levels", headers=headers)
    assert res.status_code == 200
    levels = res.json()
    assert len(levels) > 0
    codes = [lvl["code"] for lvl in levels]
    assert "SD" in codes


def test_master_api_license_types(client, test_superadmin):
    # Authenticate
    login_res = client.post(
        "/api/v1/auth/login",
        json={
            "username": test_superadmin["username"],
            "password": test_superadmin["password"],
        },
    )
    access_token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    res = client.get("/api/v1/master/license-types", headers=headers)
    assert res.status_code == 200
    licenses = res.json()
    assert len(licenses) > 0
    codes = [lic["code"] for lic in licenses]
    assert "ONE_YEAR" in codes
