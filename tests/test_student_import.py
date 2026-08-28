import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.academic.class_entity import ClassEntity
from app.models.security.auth_account import AuthAccount
from app.models.academic.academic_year import AcademicYear
from tests.test_academic_administration_api import api_test_data


def test_import_students_success(client: TestClient, api_test_data, db: Session):
    """TEST 1: All valid rows -> all inserted successfully."""
    headers_a = api_test_data["headers_admin_a"]
    year_2025 = api_test_data["year_2025"]
    school_a = api_test_data["school_a"]

    # Create class
    cls = ClassEntity(school_id=school_a.id, academic_year_id=year_2025.id, name="X-MIPA-1", grade_level="10")
    db.add(cls)
    db.commit()

    payload = {
        "academic_year_id": year_2025.id,
        "rows": [
            {
                "name": "Siswa Cemerlang Satu",
                "nisn": "8888777711",
                "nis": "99911",
                "gender": "L",
                "class_name": "X-MIPA-1",
                "registered_year": 2026
            },
            {
                "name": "Siswa Cemerlang Dua",
                "nisn": "8888777722",
                "nis": "99922",
                "gender": "P",
                "class_name": "X-MIPA-1",
                "registered_year": 2026
            }
        ]
    }

    res = client.post("/api/v1/admin/students/import", json=payload, headers=headers_a)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["imported_count"] == 2
    assert len(data["data"]) == 2

    # Verify in database
    students = db.query(AuthAccount).filter(AuthAccount.nisn.in_(["8888777711", "8888777722"])).all()
    assert len(students) == 2
    for student in students:
        assert student.school_id == school_a.id
        assert student.class_name == "X-MIPA-1"


def test_import_students_missing_class(client: TestClient, api_test_data, db: Session):
    """TEST 2: One missing class reference -> HTTP 422 -> zero students inserted."""
    headers_a = api_test_data["headers_admin_a"]
    year_2025 = api_test_data["year_2025"]
    school_a = api_test_data["school_a"]

    # Create class
    cls = ClassEntity(school_id=school_a.id, academic_year_id=year_2025.id, name="X-MIPA-1", grade_level="10")
    db.add(cls)
    db.commit()

    payload = {
        "academic_year_id": year_2025.id,
        "rows": [
            {
                "name": "Andi Valid",
                "nisn": "1111999901",
                "nis": "22201",
                "gender": "L",
                "class_name": "X-MIPA-1",
                "registered_year": 2026
            },
            {
                "name": "Budi Invalid Class",
                "nisn": "1111999902",
                "nis": "22202",
                "gender": "L",
                "class_name": "X-MIPA-9",  # Does not exist
                "registered_year": 2026
            }
        ]
    }

    res = client.post("/api/v1/admin/students/import", json=payload, headers=headers_a)
    assert res.status_code == 422
    data = res.json()
    assert data["status"] == "error"
    assert len(data["errors"]) == 1
    assert data["errors"][0]["code"] == "CLASS_NOT_FOUND"
    assert data["errors"][0]["row"] == 3

    # Verify atomicity: Andi Valid must NOT be inserted
    student = db.query(AuthAccount).filter(AuthAccount.nisn == "1111999901").first()
    assert student is None


def test_import_students_duplicate_in_file(client: TestClient, api_test_data, db: Session):
    """TEST 3: Duplicate NISN inside XLSX -> HTTP 422 -> zero inserted."""
    headers_a = api_test_data["headers_admin_a"]
    year_2025 = api_test_data["year_2025"]

    payload = {
        "academic_year_id": year_2025.id,
        "rows": [
            {
                "name": "Siswa A",
                "nisn": "7777777777",
                "nis": "12121",
                "gender": "L",
                "registered_year": 2026
            },
            {
                "name": "Siswa B Duplicate NISN",
                "nisn": "7777777777",  # Duplicate NISN
                "nis": "12122",
                "gender": "P",
                "registered_year": 2026
            }
        ]
    }

    res = client.post("/api/v1/admin/students/import", json=payload, headers=headers_a)
    assert res.status_code == 422
    data = res.json()
    assert data["status"] == "error"
    assert len(data["errors"]) == 1
    assert data["errors"][0]["code"] == "DUPLICATE_NISN_IN_FILE"
    assert data["errors"][0]["row"] == 3

    # Verify zero inserted
    student = db.query(AuthAccount).filter(AuthAccount.nisn == "7777777777").first()
    assert student is None


def test_import_students_duplicate_in_db(client: TestClient, api_test_data, db: Session):
    """TEST 4: NISN already exists in database -> HTTP 422 -> zero inserted."""
    headers_a = api_test_data["headers_admin_a"]
    year_2025 = api_test_data["year_2025"]
    student_1 = api_test_data["student_1"] # Existing student with NISN "0011223344"

    payload = {
        "academic_year_id": year_2025.id,
        "rows": [
            {
                "name": "Siswa Baru",
                "nisn": "0011223344",  # Already exists in DB
                "nis": "88771",
                "gender": "L",
                "registered_year": 2026
            }
        ]
    }

    res = client.post("/api/v1/admin/students/import", json=payload, headers=headers_a)
    assert res.status_code == 422
    data = res.json()
    assert data["status"] == "error"
    assert len(data["errors"]) == 1
    assert any(err["code"] == "DUPLICATE_NISN" for err in data["errors"])


def test_import_students_cross_tenant(client: TestClient, api_test_data, db: Session):
    """TEST 5: Cross-tenant class reference -> reject -> zero inserted."""
    headers_a = api_test_data["headers_admin_a"]
    year_2025 = api_test_data["year_2025"]
    school_b = api_test_data["school_b"]

    # Create class belonging to School B
    cls_b = ClassEntity(school_id=school_b.id, academic_year_id=year_2025.id, name="Class-School-B", grade_level="10")
    db.add(cls_b)
    db.commit()

    payload = {
        "academic_year_id": year_2025.id,
        "rows": [
            {
                "name": "Siswa School A",
                "nisn": "9999000011",
                "gender": "L",
                "class_name": "Class-School-B", # Belongs to School B!
                "registered_year": 2026
            }
        ]
    }

    res = client.post("/api/v1/admin/students/import", json=payload, headers=headers_a)
    assert res.status_code == 422
    data = res.json()
    assert data["status"] == "error"
    assert data["errors"][0]["code"] == "CLASS_NOT_FOUND"

    # Verify zero inserted
    student = db.query(AuthAccount).filter(AuthAccount.nisn == "9999000011").first()
    assert student is None


def test_import_students_db_failure_rollback(client: TestClient, api_test_data, db: Session, monkeypatch):
    """TEST 6: Database persistence failure -> rollback -> zero inserted."""
    headers_a = api_test_data["headers_admin_a"]
    year_2025 = api_test_data["year_2025"]

    payload = {
        "academic_year_id": year_2025.id,
        "rows": [
            {
                "name": "Andi Rollback",
                "nisn": "5555444411",
                "gender": "L",
                "registered_year": 2026
            }
        ]
    }

    # Monkeypatch ClassStructureService.enroll_student_to_class or DB add to raise an exception
    # to simulate a database persistence failure
    from app.services.academic.class_structure_service import ClassStructureService
    def mock_enroll(*args, **kwargs):
        raise Exception("Simulated DB connection write failure")
    
    # We force the call to fail by making class_name valid, but mocking enroll to fail
    school_a = api_test_data["school_a"]
    cls = ClassEntity(school_id=school_a.id, academic_year_id=year_2025.id, name="X-MIPA-1", grade_level="10")
    db.add(cls)
    db.commit()

    payload["rows"][0]["class_name"] = "X-MIPA-1"

    monkeypatch.setattr(ClassStructureService, "enroll_student_to_class", mock_enroll)

    res = client.post("/api/v1/admin/students/import", json=payload, headers=headers_a)
    assert res.status_code == 500
    assert "Gagal melakukan penyimpanan data ke database" in res.json()["detail"]

    # Verify zero inserted
    student = db.query(AuthAccount).filter(AuthAccount.nisn == "5555444411").first()
    assert student is None


def test_import_students_wrong_academic_year_school(client: TestClient, api_test_data, db: Session):
    """TEST 7: Academic year belongs to another school -> reject."""
    headers_a = api_test_data["headers_admin_a"]
    school_b = api_test_data["school_b"]

    # Create academic year for School B
    year_b = AcademicYear(
        school_id=school_b.id,
        name="2027/2028",
        start_date=datetime.now(),
        end_date=datetime.now(),
        status="ACTIVE"
    )
    db.add(year_b)
    db.commit()

    payload = {
        "academic_year_id": year_b.id, # Belongs to School B!
        "rows": [
            {
                "name": "Siswa A",
                "nisn": "4444555511",
                "gender": "L",
                "registered_year": 2026
            }
        ]
    }

    res = client.post("/api/v1/admin/students/import", json=payload, headers=headers_a)
    assert res.status_code == 400
    assert "Tahun ajaran tidak ditemukan atau bukan milik sekolah Anda." in res.json()["detail"]


def test_import_students_class_wrong_academic_year(client: TestClient, api_test_data, db: Session):
    """TEST 8: Class name exists in another academic year but not the selected academic year -> CLASS_NOT_FOUND -> zero inserted."""
    headers_a = api_test_data["headers_admin_a"]
    year_2025 = api_test_data["year_2025"]
    school_a = api_test_data["school_a"]

    # Create Class X-MIPA-1 for a DIFFERENT academic year (or create a new academic year first)
    year_2026 = AcademicYear(
        school_id=school_a.id,
        name="2026/2027",
        start_date=datetime.now(),
        end_date=datetime.now(),
        status="PLANNED"
    )
    db.add(year_2026)
    db.commit()

    # Class exists in 2026/2027
    cls_2026 = ClassEntity(school_id=school_a.id, academic_year_id=year_2026.id, name="X-MIPA-1", grade_level="10")
    db.add(cls_2026)
    db.commit()

    # Import under 2025/2026 (where X-MIPA-1 does NOT exist yet)
    payload = {
        "academic_year_id": year_2025.id,
        "rows": [
            {
                "name": "Siswa A",
                "nisn": "3333222211",
                "gender": "L",
                "class_name": "X-MIPA-1", # Exists only in year_2026, not year_2025!
                "registered_year": 2026
            }
        ]
    }

    res = client.post("/api/v1/admin/students/import", json=payload, headers=headers_a)
    assert res.status_code == 422
    data = res.json()
    assert data["status"] == "error"
    assert data["errors"][0]["code"] == "CLASS_NOT_FOUND"
    assert "ditemukan di tahun ajaran lain, tetapi belum terdaftar" in data["errors"][0]["message"]
