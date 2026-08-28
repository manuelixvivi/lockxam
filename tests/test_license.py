from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sqlalchemy.orm import Session

from app.core.security.password import hash_password
from app.models.master.license_type import LicenseType
from app.models.school.school import School
from app.models.security.auth_account import AuthAccount
from app.models.license.school_license import SchoolLicense
from app.models.security.enums import UserRole
from app.services.license.license_service import LicenseService


def create_test_school_and_admin(db, npsn: str) -> tuple[School, AuthAccount]:
    school = School(
        public_id=uuid4(),
        npsn=npsn,
        code=npsn,
        name=f"School {npsn}",
        domain=f"school-{npsn}.sch.id",
        school_level_id=1,
        status="PENDING_ACTIVATION",
    )
    db.add(school)
    db.flush()

    admin = AuthAccount(
        public_id=uuid4(),
        school_id=school.id,
        username=f"admin_{npsn}",
        password_hash=hash_password(f"3qu!6rade{npsn}"),
        role=UserRole.ADMIN,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(admin)
    db.flush()
    return school, admin


def test_generate_activation_key(db, test_superadmin):
    school, admin = create_test_school_and_admin(db, "77770001")
    lic_type = db.query(LicenseType).first()
    assert lic_type is not None

    superadmin = (
        db.query(AuthAccount).filter(AuthAccount.username == test_superadmin["username"]).first()
    )
    assert superadmin is not None

    # Generate key
    key_record, raw_key = LicenseService.generate_activation_key(
        db=db, license_type_id=lic_type.id, school_id=school.id, generated_by_id=superadmin.id
    )
    db.commit()

    assert key_record.status == "GENERATED"
    assert raw_key.startswith("EQG-")
    assert key_record.key == LicenseService.hash_key(raw_key)
    assert key_record.school_id == school.id
    assert key_record.generated_by_id == superadmin.id

    # Cancel key
    cancelled = LicenseService.cancel_activation_key(db, key_record.public_id, superadmin.id)
    db.commit()
    assert cancelled.status == "CANCELLED"
    assert cancelled.cancelled_by_id == superadmin.id
    assert cancelled.cancelled_at is not None


def test_activate_license_flow(db, test_superadmin):
    school, admin = create_test_school_and_admin(db, "77770002")
    superadmin = (
        db.query(AuthAccount).filter(AuthAccount.username == test_superadmin["username"]).first()
    )
    lic_type = db.query(LicenseType).first()

    # Create target key for school
    key_rec, raw_key = LicenseService.generate_activation_key(
        db=db, license_type_id=lic_type.id, school_id=school.id, generated_by_id=superadmin.id
    )
    db.commit()

    # Activate
    lic = LicenseService.activate_license(
        db=db, plain_key=raw_key, school_id=school.id, used_by_id=admin.id
    )
    db.commit()

    assert lic.status == "ACTIVE"
    assert school.status == "ACTIVE"
    assert key_rec.status == "USED"
    assert key_rec.used_by_id == admin.id
    assert key_rec.used_at is not None

    # BR-LIC-019: Idempotency test (second activation fails)
    with pytest.raises(Exception) as excinfo:
        LicenseService.activate_license(
            db=db, plain_key=raw_key, school_id=school.id, used_by_id=admin.id
        )
    assert "Activation Key has already been used" in str(excinfo.value)


def test_activate_license_ownership_mismatch(db, test_superadmin):
    school_a, admin_a = create_test_school_and_admin(db, "77770003")
    school_b, admin_b = create_test_school_and_admin(db, "77770004")

    superadmin = (
        db.query(AuthAccount).filter(AuthAccount.username == test_superadmin["username"]).first()
    )
    lic_type = db.query(LicenseType).first()

    # Key generated for School B
    key_rec, raw_key = LicenseService.generate_activation_key(
        db=db, license_type_id=lic_type.id, school_id=school_b.id, generated_by_id=superadmin.id
    )
    db.commit()

    # Try applying School B key to School A (should fail with BR-LIC-013)
    with pytest.raises(Exception) as excinfo:
        LicenseService.activate_license(
            db=db, plain_key=raw_key, school_id=school_a.id, used_by_id=admin_a.id
        )
    assert "Activation Key is not designated for this school" in str(excinfo.value)


def test_consecutive_license_scheduling(db, test_superadmin):
    school, admin = create_test_school_and_admin(db, "77770005")
    superadmin = (
        db.query(AuthAccount).filter(AuthAccount.username == test_superadmin["username"]).first()
    )
    lic_type = db.query(LicenseType).first()

    # First license
    key_rec1, raw_key1 = LicenseService.generate_activation_key(
        db=db, license_type_id=lic_type.id, school_id=school.id, generated_by_id=superadmin.id
    )
    db.commit()

    lic1 = LicenseService.activate_license(
        db=db, plain_key=raw_key1, school_id=school.id, used_by_id=admin.id
    )
    db.commit()

    # Generate a second key for School
    key_rec2, raw_key2 = LicenseService.generate_activation_key(
        db=db, license_type_id=lic_type.id, school_id=school.id, generated_by_id=superadmin.id
    )
    db.commit()

    # Apply second key
    lic2 = LicenseService.activate_license(
        db=db, plain_key=raw_key2, school_id=school.id, used_by_id=admin.id
    )
    db.commit()

    # Verify consecutive start/end (BR-LIC-005/BR-LIC-006)
    assert lic2.status == "PENDING"
    assert lic2.start_date == lic1.end_date
    assert lic2.end_date == lic2.start_date + timedelta(days=lic_type.duration_days)


def test_renewal_request_flow(db, test_superadmin):
    school, admin = create_test_school_and_admin(db, "77770006")
    lic_type = db.query(LicenseType).first()
    superadmin = (
        db.query(AuthAccount).filter(AuthAccount.username == test_superadmin["username"]).first()
    )

    # 1. Request Renewal
    req = LicenseService.request_renewal(
        db=db,
        school_id=school.id,
        requested_by_id=admin.id,
        license_type_id=lic_type.id,
        payment_proof_url="http://example.com/payment.png",
    )
    db.commit()

    # Verify BR-LIC-014 format
    assert req.request_number.startswith("RNW-")
    assert req.status == "REQUESTED"

    # 2. Reject Request
    processed, _, _ = LicenseService.process_renewal(
        db=db,
        public_id=req.public_id,
        status="REJECTED",
        superadmin_notes="Invalid payment proof",
        processed_by_id=superadmin.id,
    )
    db.commit()
    assert processed.status == "REJECTED"
    assert processed.superadmin_notes == "Invalid payment proof"

    # 3. Create another request and approve
    req2 = LicenseService.request_renewal(
        db=db, school_id=school.id, requested_by_id=admin.id, license_type_id=lic_type.id
    )
    db.commit()

    processed2, key_rec, raw_key = LicenseService.process_renewal(
        db=db,
        public_id=req2.public_id,
        status="APPROVED",
        superadmin_notes="Payment verified",
        processed_by_id=superadmin.id,
    )
    db.commit()

    assert processed2.status == "COMPLETED"
    assert key_rec is not None
    assert key_rec.status == "GENERATED"
    assert raw_key is not None


def test_api_license_endpoints(client, test_superadmin, db: Session):
    # Authenticate SuperAdmin
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": test_superadmin["username"], "password": test_superadmin["password"]},
    )
    assert login_res.status_code == 200
    sa_token = login_res.json()["access_token"]
    sa_headers = {"Authorization": f"Bearer {sa_token}"}

    # Create a school via API (unique NPSN)
    npsn = "88887777"
    school_res = client.post(
        "/api/v1/schools",
        headers=sa_headers,
        json={
            "npsn": npsn,
            "name": "API Test School",
            "domain": "api-license.sch.id",
            "school_level_id": 1,
            "email": "test@school.com",
        },
    )
    assert school_res.status_code == 201
    school_data = school_res.json()["school"]
    school_id = school_data["id"]

    # Reset admin credentials to legacy test expectations
    db_school = db.query(School).filter(School.npsn == npsn).first()
    admin_acc = db.query(AuthAccount).filter(AuthAccount.school_id == db_school.id).first()
    admin_acc.username = f"admin_{npsn}"
    admin_acc.password_hash = hash_password(f"3qu!6rade{npsn}")
    db.commit()

    # Generate key via API
    key_res = client.post(
        "/api/v1/licenses/keys",
        headers=sa_headers,
        json={"license_type_id": 1, "school_id": school_id, "validity_days": 10},
    )
    assert key_res.status_code == 200
    key_data = key_res.json()
    raw_key = key_data["key_plain"]

    # Delete auto-created school license so the new one becomes ACTIVE directly
    db.query(SchoolLicense).filter(SchoolLicense.school_id == school_id).delete()
    db.commit()

    # Authenticate School Admin
    login_admin = client.post(
        "/api/v1/auth/login",
        json={"username": f"admin_{npsn}", "password": f"3qu!6rade{npsn}"},
    )
    assert login_admin.status_code == 200
    admin_token = login_admin.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Activate via API
    activate_res = client.post(
        "/api/v1/licenses/activate", headers=admin_headers, json={"key_plain": raw_key}
    )
    assert activate_res.status_code == 200
    assert activate_res.json()["status"] == "ACTIVE"

    # Request renewal via API
    renew_res = client.post(
        "/api/v1/licenses/renewals", headers=admin_headers, json={"license_type_id": 1}
    )
    assert renew_res.status_code == 200
    assert renew_res.json()["status"] == "REQUESTED"


def test_read_only_and_suspended_restrictions(client, db, test_superadmin):
    # Setup fresh school and admin
    npsn = "88886666"
    school, admin = create_test_school_and_admin(db, npsn)
    db.commit()

    # Authenticate School Admin
    login_admin = client.post(
        "/api/v1/auth/login",
        json={"username": f"admin_{npsn}", "password": f"3qu!6rade{npsn}"},
    )
    assert login_admin.status_code == 200
    admin_token = login_admin.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. READ_ONLY Restriction (BR-LIC-007)
    school.status = "READ_ONLY"
    db.commit()

    # Try mutating school details (mutating request to non-auth/non-license endpoint)
    res = client.put(
        f"/api/v1/schools/{school.public_id}",
        headers=admin_headers,
        json={"name": "New School Name"},
    )
    assert res.status_code == 403
    payload = res.json()
    assert "error" in payload
    assert payload["error"]["code"] == "LICENSE_EXPIRED"
    assert "School license has expired" in payload["error"]["message"]

    # 2. SUSPENDED Restriction (BR-LIC-011)
    school.status = "SUSPENDED"
    db.commit()

    # Try any operation (e.g. GET /api/v1/auth/me)
    res_me = client.get("/api/v1/auth/me", headers=admin_headers)
    assert res_me.status_code == 403
    assert "School is suspended" in res_me.json()["detail"]
