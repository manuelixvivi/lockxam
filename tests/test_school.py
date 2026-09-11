import pytest
from sqlalchemy.orm import Session

from app.exceptions.base import BusinessException
from app.models.master.school_level import SchoolLevel
from app.models.school.school_setting import SchoolSetting
from app.models.security.auth_account import AuthAccount
from app.schemas.school.school import SchoolCreateRequest
from app.services.school.school_service import SchoolService


def test_create_school_success(db: Session):
    lvl = db.query(SchoolLevel).first()
    assert lvl is not None

    req = SchoolCreateRequest(
        npsn="99998888",
        name="SMK Maju Bersama",
        domain="smkmaju.sch.id",
        school_level_id=lvl.id,
        address="Jl. Pendidikan No. 10",
        phone="021-123456",
        email="info@smkmaju.sch.id",
        website="https://smkmaju.sch.id",
    )

    school = SchoolService.create_school(db, req)

    # 1. Verify school fields
    assert school.id is not None
    assert school.npsn == "99998888"
    assert school.name == "SMK Maju Bersama"
    assert school.status == "ACTIVE"
    assert school.is_active is True

    # 2. Verify school settings created
    settings = db.query(SchoolSetting).filter(SchoolSetting.school_id == school.id).first()
    assert settings is not None
    assert settings.timezone == "Asia/Jakarta"
    assert settings.language == "id-ID"

    # 3. Verify admin account created
    admin_acc = (
        db.query(AuthAccount)
        .filter(
            AuthAccount.school_id == school.id,
            AuthAccount.username == "admin@admin.smkmaju.sch.id",
        )
        .first()
    )
    assert admin_acc is not None
    assert admin_acc.role == "ADMIN"
    assert admin_acc.is_active is True


def test_create_school_duplicate_npsn(db: Session):
    lvl = db.query(SchoolLevel).first()
    req = SchoolCreateRequest(
        npsn="99998888",
        name="SMK Maju Bersama",
        domain="smkmaju.sch.id",
        school_level_id=lvl.id,
    )

    # First creation should succeed (using service)
    try:
        SchoolService.create_school(db, req)
    except Exception:
        pass

    # Second creation with same NPSN should fail
    with pytest.raises(BusinessException) as exc_info:
        SchoolService.create_school(db, req)
    assert "already exists" in str(exc_info.value)


def test_create_school_invalid_level(db: Session):
    req = SchoolCreateRequest(
        npsn="77776666",
        name="SMA Negeri 1",
        domain="sman1.sch.id",
        school_level_id=99999,  # Non-existent
    )
    with pytest.raises(BusinessException) as exc_info:
        SchoolService.create_school(db, req)
    assert "level" in str(exc_info.value)


def test_school_api_rbac(client, test_superadmin, test_teacher, test_school, db: Session):
    lvl = db.query(SchoolLevel).first()

    # 1. Try to create as guest -> 401
    res = client.post(
        "/api/v1/schools",
        json={
            "npsn": "11112222",
            "name": "API School",
            "domain": "api-school.sch.id",
            "school_level_id": lvl.id,
        },
    )
    assert res.status_code == 401

    # 2. Authenticate as Teacher
    login_teacher = client.post(
        "/api/v1/auth/login",
        json={
            "username": test_teacher["username"],
            "password": test_teacher["password"],
        },
    )
    teacher_token = login_teacher.json()["access_token"]

    # Try to create as Teacher -> 403 Forbidden
    res = client.post(
        "/api/v1/schools",
        json={
            "npsn": "11112222",
            "name": "API School",
            "domain": "api-school.sch.id",
            "school_level_id": lvl.id,
        },
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert res.status_code == 403

    # 3. Authenticate as Superadmin
    login_super = client.post(
        "/api/v1/auth/login",
        json={
            "username": test_superadmin["username"],
            "password": test_superadmin["password"],
        },
    )
    super_token = login_super.json()["access_token"]

    # Create as Superadmin -> 201 Created
    res = client.post(
        "/api/v1/schools",
        json={
            "npsn": "11112222",
            "name": "API School",
            "domain": "api-school.sch.id",
            "school_level_id": lvl.id,
        },
        headers={"Authorization": f"Bearer {super_token}"},
    )
    assert res.status_code == 201
    school_data = res.json()["school"]
    assert school_data["npsn"] == "11112222"
    public_id = school_data["public_id"]

    # 4. Cross-tenant read as Teacher -> 403 Forbidden (Multi-tenant isolation)
    res = client.get(
        f"/api/v1/schools/{public_id}",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert res.status_code == 403

    # 4b. Get Own School as Teacher -> 200 OK
    test_school.deleted_at = None
    db.flush()
    res_own = client.get(
        f"/api/v1/schools/{test_school.public_id}",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert res_own.status_code == 200
    assert res_own.json()["name"] == test_school.name

    # 5. List Global Schools as Teacher -> 403 Forbidden (RBAC Protected)
    res = client.get("/api/v1/schools", headers={"Authorization": f"Bearer {teacher_token}"})
    assert res.status_code == 403

    # 5b. List Global Schools as Superadmin -> 200 OK
    res = client.get("/api/v1/schools", headers={"Authorization": f"Bearer {super_token}"})
    assert res.status_code == 200
    assert len(res.json()) > 0

    # 6. Update School (PUT) as Superadmin
    res = client.put(
        f"/api/v1/schools/{public_id}",
        json={"name": "API School Updated"},
        headers={"Authorization": f"Bearer {super_token}"},
    )
    assert res.status_code == 200
    assert res.json()["name"] == "API School Updated"

    # 7. Update School (PATCH) as Superadmin
    res = client.patch(
        f"/api/v1/schools/{public_id}",
        json={"status": "ACTIVE"},
        headers={"Authorization": f"Bearer {super_token}"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "ACTIVE"

    # 8. Delete School as Superadmin
    res = client.delete(
        f"/api/v1/schools/{public_id}",
        headers={"Authorization": f"Bearer {super_token}"},
    )
    assert res.status_code == 200
    assert "deleted" in res.json()["message"].lower()

    # 9. Verify school no longer returned in GET /schools
    res = client.get("/api/v1/schools", headers={"Authorization": f"Bearer {super_token}"})
    # The created school was soft-deleted, so it shouldn't show up in the list
    assert all(s["public_id"] != public_id for s in res.json())
