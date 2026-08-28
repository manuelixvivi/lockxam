from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.academic.class_subject import ClassSubject
from app.models.academic.subject import Subject
from app.models.academic.teacher_subject import TeacherSubject
from app.models.security.auth_account import AuthAccount

# ============================================================
# SUBJECT IMPORT TESTS
# ============================================================


def test_import_subjects_valid_batch(client: TestClient, api_test_data, db: Session):
    """TEST 1: Valid batch of subjects -> imported successfully."""
    headers = api_test_data["headers_admin_a"]
    school = api_test_data["school_a"]

    payload = {
        "subjects": [
            {
                "code": "IND-10",
                "name": "Bahasa Indonesia Kelas 10",
                "description": "Deskripsi Indo",
                "row_num": 2,
            },
            {"code": "ING-10", "name": "Bahasa Inggris Kelas 10", "row_num": 3},
        ]
    }

    res = client.post("/api/v1/admin/subjects/import", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["imported_count"] == 2

    # Verify exist in DB
    subj1 = db.query(Subject).filter_by(school_id=school.id, code="IND-10").first()
    assert subj1 is not None
    assert subj1.name == "Bahasa Indonesia Kelas 10"

    subj2 = db.query(Subject).filter_by(school_id=school.id, code="ING-10").first()
    assert subj2 is not None

    # Verify absolutely zero ClassSubject or TeacherSubject was created
    assert len(db.query(ClassSubject).filter_by(subject_id=subj1.id).all()) == 0
    assert len(db.query(TeacherSubject).filter_by(subject_id=subj1.id).all()) == 0
    assert len(db.query(ClassSubject).filter_by(subject_id=subj2.id).all()) == 0
    assert len(db.query(TeacherSubject).filter_by(subject_id=subj2.id).all()) == 0


def test_import_subjects_missing_code(client: TestClient, api_test_data, db: Session):
    """TEST 2: Subject code missing -> REJECT."""
    headers = api_test_data["headers_admin_a"]

    payload = {"subjects": [{"code": "", "name": "Mata Pelajaran Tanpa Kode", "row_num": 2}]}

    res = client.post("/api/v1/admin/subjects/import", json=payload, headers=headers)
    assert res.status_code == 422
    data = res.json()
    assert data["status"] == "error"
    assert data["errors"][0]["code"] == "SUBJECT_CODE_REQUIRED"


def test_import_subjects_missing_name(client: TestClient, api_test_data, db: Session):
    """TEST 3: Subject name missing -> REJECT."""
    headers = api_test_data["headers_admin_a"]

    payload = {"subjects": [{"code": "MAT-12", "name": "", "row_num": 2}]}

    res = client.post("/api/v1/admin/subjects/import", json=payload, headers=headers)
    assert res.status_code == 422
    data = res.json()
    assert data["status"] == "error"
    assert data["errors"][0]["code"] == "SUBJECT_NAME_REQUIRED"


def test_import_subjects_duplicate_code_in_file(client: TestClient, api_test_data, db: Session):
    """TEST 4: Duplicate subject code inside file -> REJECT."""
    headers = api_test_data["headers_admin_a"]

    payload = {
        "subjects": [
            {"code": "MAT-10", "name": "Matematika 1", "row_num": 2},
            {"code": "MAT-10", "name": "Matematika 2", "row_num": 3},
        ]
    }

    res = client.post("/api/v1/admin/subjects/import", json=payload, headers=headers)
    assert res.status_code == 422
    data = res.json()
    assert data["status"] == "error"
    assert data["errors"][0]["code"] == "DUPLICATE_SUBJECT_CODE_IN_FILE"


def test_import_subjects_duplicate_database(client: TestClient, api_test_data, db: Session):
    """TEST 5: Duplicate code against database -> REJECT."""
    headers = api_test_data["headers_admin_a"]
    school = api_test_data["school_a"]

    # Pre-existing Subject
    subj = Subject(school_id=school.id, code="MAT-EXISTS", name="Matematika Lama", is_active=True)
    db.add(subj)
    db.commit()

    payload = {"subjects": [{"code": "MAT-EXISTS", "name": "Matematika Baru", "row_num": 2}]}

    res = client.post("/api/v1/admin/subjects/import", json=payload, headers=headers)
    assert res.status_code == 422
    data = res.json()
    assert data["status"] == "error"
    assert data["errors"][0]["code"] == "DUPLICATE_SUBJECT_CODE_IN_DB"


def test_import_subjects_cross_tenant_protection(client: TestClient, api_test_data, db: Session):
    """TEST 6: Subject exists in School B, but School A imports it -> ALLOW (since subject code uniqueness is per-school)."""
    headers_a = api_test_data["headers_admin_a"]
    school_a = api_test_data["school_a"]
    school_b = api_test_data["school_b"]

    # Subject exists in School B
    subj_b = Subject(
        school_id=school_b.id, code="UNIQ-CODE", name="Subject School B", is_active=True
    )
    db.add(subj_b)
    db.commit()

    payload = {"subjects": [{"code": "UNIQ-CODE", "name": "Subject School A", "row_num": 2}]}

    res = client.post("/api/v1/admin/subjects/import", json=payload, headers=headers_a)
    assert res.status_code == 200
    # Verifies School A successfully gets the subject code
    assert db.query(Subject).filter_by(school_id=school_a.id, code="UNIQ-CODE").first() is not None


def test_import_subjects_mixed_valid_invalid(client: TestClient, api_test_data, db: Session):
    """TEST 7: Mixed valid + invalid subjects -> rollback -> zero new subjects created."""
    headers = api_test_data["headers_admin_a"]
    school = api_test_data["school_a"]

    payload = {
        "subjects": [
            {"code": "VALID-SUBJ", "name": "Valid Subject", "row_num": 2},
            {"code": "", "name": "Invalid Subject", "row_num": 3},
        ]
    }

    res = client.post("/api/v1/admin/subjects/import", json=payload, headers=headers)
    assert res.status_code == 422

    # Verify zero created
    assert db.query(Subject).filter_by(school_id=school.id, code="VALID-SUBJ").first() is None


def test_import_subjects_db_failure_rollback(
    client: TestClient, api_test_data, db: Session, monkeypatch
):
    """TEST 8: Database failure during subject persistence -> rollback -> zero created."""
    headers = api_test_data["headers_admin_a"]
    school = api_test_data["school_a"]

    from app.repositories.academic.subject_repository import SubjectRepository

    def mock_create(*args, **kwargs):
        raise Exception("Database failure")

    monkeypatch.setattr(SubjectRepository, "create", mock_create)

    payload = {"subjects": [{"code": "FAIL-SUBJ", "name": "Failure Subject", "row_num": 2}]}

    res = client.post("/api/v1/admin/subjects/import", json=payload, headers=headers)
    assert res.status_code == 500
    assert "Gagal melakukan penyimpanan data ke database" in res.json()["detail"]


# ============================================================
# TEACHER IMPORT TESTS
# ============================================================


def test_import_teachers_valid_batch(client: TestClient, api_test_data, db: Session):
    """TEST 1: Valid batch of teachers -> imported successfully."""
    headers = api_test_data["headers_admin_a"]
    school = api_test_data["school_a"]

    payload = {
        "teachers": [
            {
                "name": "Dr. John Doe",
                "nip": "9999888877",
                "teacher_code": "JOHNDOE",
                "gender": "L",
                "registered_year": 2024,
                "row_num": 2,
            }
        ]
    }

    res = client.post("/api/v1/admin/teachers/import", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["imported_count"] == 1

    # Verify database
    t = db.query(AuthAccount).filter_by(school_id=school.id, nip="9999888877").first()
    assert t is not None
    assert t.name == "Dr. John Doe"
    assert t.teacher_code == "JOHNDOE"


def test_import_teachers_missing_required_identity(client: TestClient, api_test_data, db: Session):
    """TEST 2: Missing required identity (name, nip, or gender) -> REJECT."""
    headers = api_test_data["headers_admin_a"]

    # Missing Name
    payload = {"teachers": [{"name": "", "nip": "123456", "gender": "L", "row_num": 2}]}
    res = client.post("/api/v1/admin/teachers/import", json=payload, headers=headers)
    assert res.status_code == 422
    assert res.json()["errors"][0]["code"] == "TEACHER_NAME_REQUIRED"

    # Missing NIP
    payload = {"teachers": [{"name": "John Doe", "nip": "", "gender": "L", "row_num": 2}]}
    res = client.post("/api/v1/admin/teachers/import", json=payload, headers=headers)
    assert res.status_code == 422
    assert res.json()["errors"][0]["code"] == "TEACHER_NIP_REQUIRED"

    # Missing Gender
    payload = {"teachers": [{"name": "John Doe", "nip": "123456", "gender": "", "row_num": 2}]}
    res = client.post("/api/v1/admin/teachers/import", json=payload, headers=headers)
    assert res.status_code == 422
    assert res.json()["errors"][0]["code"] == "TEACHER_GENDER_REQUIRED"


def test_import_teachers_duplicate_username_in_file(client: TestClient, api_test_data, db: Session):
    """TEST 3: Duplicate username (same NIP) inside XLSX -> REJECT."""
    headers = api_test_data["headers_admin_a"]

    payload = {
        "teachers": [
            {"name": "Guru A", "nip": "111222333", "gender": "L", "row_num": 2},
            {"name": "Guru B", "nip": "111222333", "gender": "P", "row_num": 3},
        ]
    }

    res = client.post("/api/v1/admin/teachers/import", json=payload, headers=headers)
    assert res.status_code == 422
    assert res.json()["errors"][0]["code"] == "DUPLICATE_NIP_IN_FILE"


def test_import_teachers_duplicate_teacher_code_in_file(
    client: TestClient, api_test_data, db: Session
):
    """TEST 3.5: Duplicate teacher code inside XLSX -> REJECT."""
    headers = api_test_data["headers_admin_a"]

    payload = {
        "teachers": [
            {
                "name": "Guru A",
                "nip": "111222333",
                "teacher_code": "DUPCODE",
                "gender": "L",
                "row_num": 2,
            },
            {
                "name": "Guru B",
                "nip": "444555666",
                "teacher_code": "DUPCODE",
                "gender": "P",
                "row_num": 3,
            },
        ]
    }

    res = client.post("/api/v1/admin/teachers/import", json=payload, headers=headers)
    assert res.status_code == 422
    assert res.json()["errors"][0]["code"] == "DUPLICATE_TEACHER_CODE_IN_FILE"


def test_import_teachers_duplicate_database_username(
    client: TestClient, api_test_data, db: Session
):
    """TEST 4: Duplicate NIP/username against database -> REJECT."""
    headers = api_test_data["headers_admin_a"]
    school = api_test_data["school_a"]

    # Pre-existing Teacher (which matches username nip@guru.{domain})
    domain = school.domain
    existing_teacher = AuthAccount(
        school_id=school.id,
        username=f"987654321@guru.{domain}",
        password_hash="mock",
        role="TEACHER",
        is_active=True,
        nip="987654321",
        teacher_code="T-987654321",
        gender="L",
        registered_year=2024,
    )
    db.add(existing_teacher)
    db.commit()

    payload = {
        "teachers": [{"name": "New Teacher", "nip": "987654321", "gender": "L", "row_num": 2}]
    }

    res = client.post("/api/v1/admin/teachers/import", json=payload, headers=headers)
    assert res.status_code == 422
    assert res.json()["errors"][0]["code"] == "DUPLICATE_USERNAME_IN_DB"


def test_import_teachers_duplicate_nip_or_code(client: TestClient, api_test_data, db: Session):
    """TEST 5: Duplicate teacher code in DB -> REJECT."""
    headers = api_test_data["headers_admin_a"]
    school = api_test_data["school_a"]

    # Pre-existing Teacher with code DUPCODE
    existing_teacher = AuthAccount(
        school_id=school.id,
        username="other@guru.domain",
        password_hash="mock",
        role="TEACHER",
        is_active=True,
        nip="11223344",
        teacher_code="DUPCODE",
        gender="L",
        registered_year=2024,
    )
    db.add(existing_teacher)
    db.commit()

    payload = {
        "teachers": [
            {
                "name": "New Teacher",
                "nip": "55667788",
                "teacher_code": "DUPCODE",
                "gender": "L",
                "row_num": 2,
            }
        ]
    }

    res = client.post("/api/v1/admin/teachers/import", json=payload, headers=headers)
    assert res.status_code == 422
    assert res.json()["errors"][0]["code"] == "DUPLICATE_TEACHER_CODE_IN_DB"


def test_import_teachers_cross_tenant_protection(client: TestClient, api_test_data, db: Session):
    """TEST 6: Teacher exists in School B, School A imports same NIP -> ALLOW (usernames will differ by domain, e.g. nip@guru.sch-a.id vs nip@guru.sch-b.id)."""
    headers_a = api_test_data["headers_admin_a"]
    school_a = api_test_data["school_a"]
    school_b = api_test_data["school_b"]

    # Pre-existing teacher in School B
    existing_b = AuthAccount(
        school_id=school_b.id,
        username=f"555555@guru.{school_b.domain}",
        password_hash="mock",
        role="TEACHER",
        is_active=True,
        nip="555555",
        teacher_code="T-555555-B",
        gender="L",
        registered_year=2024,
    )
    db.add(existing_b)
    db.commit()

    payload = {
        "teachers": [{"name": "John School A", "nip": "555555", "gender": "L", "row_num": 2}]
    }

    res = client.post("/api/v1/admin/teachers/import", json=payload, headers=headers_a)
    assert res.status_code == 200
    assert db.query(AuthAccount).filter_by(school_id=school_a.id, nip="555555").first() is not None


def test_import_teachers_mixed_valid_invalid(client: TestClient, api_test_data, db: Session):
    """TEST 7: Mixed valid + invalid teachers -> rollback -> zero new teachers created."""
    headers = api_test_data["headers_admin_a"]
    school = api_test_data["school_a"]

    payload = {
        "teachers": [
            {"name": "Valid Teacher", "nip": "99988822", "gender": "L", "row_num": 2},
            {"name": "", "nip": "99988833", "gender": "P", "row_num": 3},  # Name missing
        ]
    }

    res = client.post("/api/v1/admin/teachers/import", json=payload, headers=headers)
    assert res.status_code == 422

    # Verify zero created
    assert db.query(AuthAccount).filter_by(school_id=school.id, nip="99988822").first() is None


def test_import_teachers_db_failure_rollback(
    client: TestClient, api_test_data, db: Session, monkeypatch
):
    """TEST 8: Database failure during teacher persistence -> rollback -> zero created."""
    headers = api_test_data["headers_admin_a"]
    school = api_test_data["school_a"]

    from app.repositories.security.auth_repository import AuthRepository

    def mock_create(*args, **kwargs):
        raise Exception("Database failure")

    monkeypatch.setattr(AuthRepository, "create", mock_create)

    payload = {
        "teachers": [{"name": "Fail Teacher", "nip": "12121212", "gender": "L", "row_num": 2}]
    }

    res = client.post("/api/v1/admin/teachers/import", json=payload, headers=headers)
    assert res.status_code == 500
    assert "Gagal melakukan penyimpanan data ke database" in res.json()["detail"]


def test_import_teachers_no_teacher_subject_created(client: TestClient, api_test_data, db: Session):
    """TEST 9: Verifies TeacherSubject is NOT auto-created under any circumstances during teacher import."""
    headers = api_test_data["headers_admin_a"]
    school = api_test_data["school_a"]

    payload = {
        "teachers": [
            {
                "name": "Dr. John Doe",
                "nip": "9999888877",
                "teacher_code": "JOHNDOE",
                "gender": "L",
                "registered_year": 2024,
                "row_num": 2,
            }
        ]
    }

    res = client.post("/api/v1/admin/teachers/import", json=payload, headers=headers)
    assert res.status_code == 200

    # Verify teacher exists
    t = db.query(AuthAccount).filter_by(school_id=school.id, nip="9999888877").first()
    assert t is not None

    # Verify absolutely zero competencies exist for this teacher
    comps = db.query(TeacherSubject).filter_by(teacher_id=t.id).all()
    assert len(comps) == 0


def test_import_subjects_atomic_100_rows(client: TestClient, api_test_data, db: Session):
    """TEST 10: 100 rows (99 valid, 1 invalid) -> Expected: HTTP 422, 0 Subject records created."""
    headers = api_test_data["headers_admin_a"]
    school = api_test_data["school_a"]

    subjects_list = []
    # 99 valid rows
    for i in range(99):
        subjects_list.append(
            {"code": f"SUBJ-ATOMIC-{i}", "name": f"Subject Atomic Name {i}", "row_num": i + 2}
        )
    # 1 invalid row (missing name)
    subjects_list.append({"code": "SUBJ-INVALID-100", "name": "", "row_num": 101})

    payload = {"subjects": subjects_list}

    res = client.post("/api/v1/admin/subjects/import", json=payload, headers=headers)
    assert res.status_code == 422

    # Verify that absolutely none of the 99 valid subjects were created in DB
    existing_count = (
        db.query(Subject)
        .filter(Subject.school_id == school.id, Subject.code.like("SUBJ-ATOMIC-%"))
        .count()
    )
    assert existing_count == 0


def test_import_teachers_atomic_100_rows(client: TestClient, api_test_data, db: Session):
    """TEST 11: 100 rows (99 valid, 1 invalid) -> Expected: HTTP 422, 0 Teacher records created."""
    headers = api_test_data["headers_admin_a"]
    school = api_test_data["school_a"]

    teachers_list = []
    # 99 valid rows
    for i in range(99):
        teachers_list.append(
            {
                "name": f"Teacher Atomic {i}",
                "nip": f"888877{i:03d}",
                "gender": "L",
                "row_num": i + 2,
            }
        )
    # 1 invalid row (invalid NIP)
    teachers_list.append(
        {"name": "Teacher Invalid", "nip": "not-a-number", "gender": "P", "row_num": 101}
    )

    payload = {"teachers": teachers_list}

    res = client.post("/api/v1/admin/teachers/import", json=payload, headers=headers)
    assert res.status_code == 422

    # Verify that absolutely none of the 99 valid teachers were created in DB
    existing_count = (
        db.query(AuthAccount)
        .filter(AuthAccount.school_id == school.id, AuthAccount.nip.like("888877%"))
        .count()
    )
    assert existing_count == 0
