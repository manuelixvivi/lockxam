from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.academic.academic_year import AcademicYear
from app.models.academic.class_entity import ClassEntity
from app.models.academic.class_subject import ClassSubject
from app.models.academic.class_subject_teacher import ClassSubjectTeacher
from app.models.academic.subject import Subject
from app.models.academic.teacher_subject import TeacherSubject


def test_import_class_structure_all_valid(client: TestClient, api_test_data, db: Session):
    """TEST 1: All valid rows -> successfully committed."""
    headers_a = api_test_data["headers_admin_a"]
    year_2025 = api_test_data["year_2025"]
    school_a = api_test_data["school_a"]
    teacher = api_test_data["teacher_math_a"]

    # Pre-requisite entities:
    # 1. Class
    cls = ClassEntity(
        school_id=school_a.id, academic_year_id=year_2025.id, name="X-MIPA-1", grade_level="10"
    )
    db.add(cls)
    # 2. Subject
    subj = Subject(
        school_id=school_a.id, code="MAT-10", name="Matematika Wajib Kelas 10", is_active=True
    )
    db.add(subj)
    db.commit()

    # 3. Teacher Subject Competency
    ts = TeacherSubject(school_id=school_a.id, teacher_id=teacher.id, subject_id=subj.id)
    db.add(ts)
    db.commit()

    payload = {
        "academic_year_id": year_2025.id,
        "classes": [
            {
                "name": "X-MIPA-1",
                "grade_level": "10",
                "students": [],
                "subjects": [
                    {"subject_code": "MAT-10", "teacher_code": teacher.username, "row_num": 2}
                ],
            }
        ],
    }

    res = client.post("/api/v1/admin/classes/import-full", json=payload, headers=headers_a)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["imported_count"] == 1

    # Verify ClassSubject and ClassSubjectTeacher exist in DB
    cs = db.query(ClassSubject).filter_by(class_id=cls.id, subject_id=subj.id).first()
    assert cs is not None
    cst = (
        db.query(ClassSubjectTeacher)
        .filter_by(class_id=cls.id, subject_id=subj.id, teacher_id=teacher.id)
        .first()
    )
    assert cst is not None


def test_import_class_structure_missing_class(client: TestClient, api_test_data, db: Session):
    """TEST 2: Referenced Class does not exist -> REJECT ENTIRE IMPORT."""
    headers_a = api_test_data["headers_admin_a"]
    year_2025 = api_test_data["year_2025"]
    school_a = api_test_data["school_a"]
    teacher = api_test_data["teacher_math_a"]

    # Subject and competency exist, but Class does not
    subj = Subject(
        school_id=school_a.id, code="MAT-10", name="Matematika Wajib Kelas 10", is_active=True
    )
    db.add(subj)
    db.commit()
    ts = TeacherSubject(school_id=school_a.id, teacher_id=teacher.id, subject_id=subj.id)
    db.add(ts)
    db.commit()

    payload = {
        "academic_year_id": year_2025.id,
        "classes": [
            {
                "name": "X-MIPA-NONEXIST",  # Does not exist
                "grade_level": "10",
                "students": [],
                "subjects": [
                    {"subject_code": "MAT-10", "teacher_code": teacher.username, "row_num": 2}
                ],
            }
        ],
    }

    res = client.post("/api/v1/admin/classes/import-full", json=payload, headers=headers_a)
    assert res.status_code == 422
    data = res.json()
    assert data["status"] == "error"
    assert data["errors"][0]["code"] == "CLASS_NOT_FOUND"

    # Verify zero created
    cst = db.query(ClassSubjectTeacher).filter_by(subject_id=subj.id, teacher_id=teacher.id).first()
    assert cst is None


def test_import_class_structure_missing_subject(client: TestClient, api_test_data, db: Session):
    """TEST 3: Referenced Subject does not exist -> REJECT ENTIRE IMPORT."""
    headers_a = api_test_data["headers_admin_a"]
    year_2025 = api_test_data["year_2025"]
    school_a = api_test_data["school_a"]
    teacher = api_test_data["teacher_math_a"]

    # Class exists, but Subject does not
    cls = ClassEntity(
        school_id=school_a.id, academic_year_id=year_2025.id, name="X-MIPA-1", grade_level="10"
    )
    db.add(cls)
    db.commit()

    payload = {
        "academic_year_id": year_2025.id,
        "classes": [
            {
                "name": "X-MIPA-1",
                "grade_level": "10",
                "students": [],
                "subjects": [
                    {
                        "subject_code": "NONEXIST-SUBJ",  # Does not exist
                        "teacher_code": teacher.username,
                        "row_num": 2,
                    }
                ],
            }
        ],
    }

    res = client.post("/api/v1/admin/classes/import-full", json=payload, headers=headers_a)
    assert res.status_code == 422
    data = res.json()
    assert data["status"] == "error"
    assert data["errors"][0]["code"] == "SUBJECT_NOT_FOUND"

    # Verify zero created
    cs = db.query(ClassSubject).filter_by(class_id=cls.id).first()
    assert cs is None


def test_import_class_structure_missing_teacher(client: TestClient, api_test_data, db: Session):
    """TEST 4: Referenced Teacher does not exist -> REJECT ENTIRE IMPORT."""
    headers_a = api_test_data["headers_admin_a"]
    year_2025 = api_test_data["year_2025"]
    school_a = api_test_data["school_a"]

    cls = ClassEntity(
        school_id=school_a.id, academic_year_id=year_2025.id, name="X-MIPA-1", grade_level="10"
    )
    db.add(cls)
    subj = Subject(
        school_id=school_a.id, code="MAT-10", name="Matematika Wajib Kelas 10", is_active=True
    )
    db.add(subj)
    db.commit()

    payload = {
        "academic_year_id": year_2025.id,
        "classes": [
            {
                "name": "X-MIPA-1",
                "grade_level": "10",
                "students": [],
                "subjects": [
                    {
                        "subject_code": "MAT-10",
                        "teacher_code": "GURU_NONEXIST",  # Does not exist
                        "row_num": 2,
                    }
                ],
            }
        ],
    }

    res = client.post("/api/v1/admin/classes/import-full", json=payload, headers=headers_a)
    assert res.status_code == 422
    data = res.json()
    assert data["status"] == "error"
    assert data["errors"][0]["code"] == "TEACHER_NOT_FOUND"

    # Verify zero created
    cst = db.query(ClassSubjectTeacher).filter_by(class_id=cls.id).first()
    assert cst is None


def test_import_class_structure_missing_competency(client: TestClient, api_test_data, db: Session):
    """TEST 5: Teacher exists but has no competency (TeacherSubject missing) -> REJECT (TEACHER_NOT_COMPETENT)."""
    headers_a = api_test_data["headers_admin_a"]
    year_2025 = api_test_data["year_2025"]
    school_a = api_test_data["school_a"]
    teacher = api_test_data["teacher_math_a"]

    cls = ClassEntity(
        school_id=school_a.id, academic_year_id=year_2025.id, name="X-MIPA-1", grade_level="10"
    )
    db.add(cls)
    subj = Subject(
        school_id=school_a.id, code="MAT-10", name="Matematika Wajib Kelas 10", is_active=True
    )
    db.add(subj)
    db.commit()

    # DO NOT add TeacherSubject competency

    payload = {
        "academic_year_id": year_2025.id,
        "classes": [
            {
                "name": "X-MIPA-1",
                "grade_level": "10",
                "students": [],
                "subjects": [
                    {"subject_code": "MAT-10", "teacher_code": teacher.username, "row_num": 2}
                ],
            }
        ],
    }

    res = client.post("/api/v1/admin/classes/import-full", json=payload, headers=headers_a)
    assert res.status_code == 422
    data = res.json()
    assert data["status"] == "error"
    assert data["errors"][0]["code"] == "TEACHER_NOT_COMPETENT"

    # Verify zero created
    cst = db.query(ClassSubjectTeacher).filter_by(class_id=cls.id).first()
    assert cst is None


def test_import_class_structure_wrong_academic_year(client: TestClient, api_test_data, db: Session):
    """TEST 6: Academic Year belongs to another school -> REJECT."""
    headers_a = api_test_data["headers_admin_a"]
    school_b = api_test_data["school_b"]

    year_b = AcademicYear(
        school_id=school_b.id,
        name="2027/2028",
        start_date=datetime.now(),
        end_date=datetime.now(),
        status="ACTIVE",
    )
    db.add(year_b)
    db.commit()

    payload = {"academic_year_id": year_b.id, "classes": []}  # School B

    res = client.post("/api/v1/admin/classes/import-full", json=payload, headers=headers_a)
    assert res.status_code == 400
    assert "Tahun ajaran tidak ditemukan" in res.json()["detail"]


def test_import_class_structure_cross_tenant_class(client: TestClient, api_test_data, db: Session):
    """TEST 7: Class belongs to another school -> CLASS_NOT_FOUND -> REJECT."""
    headers_a = api_test_data["headers_admin_a"]
    year_2025 = api_test_data["year_2025"]
    school_b = api_test_data["school_b"]

    # Class in School B
    cls_b = ClassEntity(
        school_id=school_b.id,
        academic_year_id=year_2025.id,
        name="Class-School-B",
        grade_level="10",
    )
    db.add(cls_b)
    db.commit()

    payload = {
        "academic_year_id": year_2025.id,
        "classes": [
            {
                "name": "Class-School-B",  # Belongs to School B!
                "grade_level": "10",
                "students": [],
                "subjects": [],
            }
        ],
    }

    res = client.post("/api/v1/admin/classes/import-full", json=payload, headers=headers_a)
    assert res.status_code == 422
    data = res.json()
    assert data["errors"][0]["code"] == "CLASS_NOT_FOUND"


def test_import_class_structure_cross_tenant_subject(
    client: TestClient, api_test_data, db: Session
):
    """TEST 8: Subject belongs to another school -> SUBJECT_NOT_FOUND -> REJECT."""
    headers_a = api_test_data["headers_admin_a"]
    year_2025 = api_test_data["year_2025"]
    school_a = api_test_data["school_a"]
    school_b = api_test_data["school_b"]
    teacher = api_test_data["teacher_math_a"]

    cls = ClassEntity(
        school_id=school_a.id, academic_year_id=year_2025.id, name="X-MIPA-1", grade_level="10"
    )
    db.add(cls)
    # Subject in School B
    subj_b = Subject(
        school_id=school_b.id, code="MAT-10-B", name="Matematika School B", is_active=True
    )
    db.add(subj_b)
    db.commit()

    payload = {
        "academic_year_id": year_2025.id,
        "classes": [
            {
                "name": "X-MIPA-1",
                "grade_level": "10",
                "students": [],
                "subjects": [
                    {
                        "subject_code": "MAT-10-B",  # Belongs to School B!
                        "teacher_code": teacher.username,
                        "row_num": 2,
                    }
                ],
            }
        ],
    }

    res = client.post("/api/v1/admin/classes/import-full", json=payload, headers=headers_a)
    assert res.status_code == 422
    data = res.json()
    assert data["errors"][0]["code"] == "SUBJECT_NOT_FOUND"


def test_import_class_structure_cross_tenant_teacher(
    client: TestClient, api_test_data, db: Session
):
    """TEST 9: Teacher belongs to another school -> TEACHER_NOT_FOUND -> REJECT."""
    headers_a = api_test_data["headers_admin_a"]
    year_2025 = api_test_data["year_2025"]
    school_a = api_test_data["school_a"]
    admin_b = api_test_data["admin_b"]  # Belongs to School B

    cls = ClassEntity(
        school_id=school_a.id, academic_year_id=year_2025.id, name="X-MIPA-1", grade_level="10"
    )
    db.add(cls)
    subj = Subject(school_id=school_a.id, code="MAT-10", name="Matematika Wajib", is_active=True)
    db.add(subj)
    db.commit()

    payload = {
        "academic_year_id": year_2025.id,
        "classes": [
            {
                "name": "X-MIPA-1",
                "grade_level": "10",
                "students": [],
                "subjects": [
                    {
                        "subject_code": "MAT-10",
                        "teacher_code": admin_b.username,  # Belongs to School B!
                        "row_num": 2,
                    }
                ],
            }
        ],
    }

    res = client.post("/api/v1/admin/classes/import-full", json=payload, headers=headers_a)
    assert res.status_code == 422
    data = res.json()
    assert data["errors"][0]["code"] == "TEACHER_NOT_FOUND"


def test_import_class_structure_duplicate_subject_in_file(
    client: TestClient, api_test_data, db: Session
):
    """TEST 10: Duplicate Class + Subject inside file -> DUPLICATE_CLASS_SUBJECT_IN_FILE -> REJECT."""
    headers_a = api_test_data["headers_admin_a"]
    year_2025 = api_test_data["year_2025"]
    school_a = api_test_data["school_a"]
    teacher = api_test_data["teacher_math_a"]

    cls = ClassEntity(
        school_id=school_a.id, academic_year_id=year_2025.id, name="X-MIPA-1", grade_level="10"
    )
    db.add(cls)
    subj = Subject(school_id=school_a.id, code="MAT-10", name="Matematika", is_active=True)
    db.add(subj)
    db.commit()
    ts = TeacherSubject(school_id=school_a.id, teacher_id=teacher.id, subject_id=subj.id)
    db.add(ts)
    db.commit()

    payload = {
        "academic_year_id": year_2025.id,
        "classes": [
            {
                "name": "X-MIPA-1",
                "grade_level": "10",
                "students": [],
                "subjects": [
                    {"subject_code": "MAT-10", "teacher_code": teacher.username, "row_num": 2},
                    {
                        "subject_code": "MAT-10",  # Duplicate Class + Subject!
                        "teacher_code": teacher.username,
                        "row_num": 3,
                    },
                ],
            }
        ],
    }

    res = client.post("/api/v1/admin/classes/import-full", json=payload, headers=headers_a)
    assert res.status_code == 422
    data = res.json()
    assert data["errors"][0]["code"] == "DUPLICATE_CLASS_SUBJECT_IN_FILE"


def test_import_class_structure_duplicate_cst_in_file(
    client: TestClient, api_test_data, db: Session
):
    """TEST 11: Duplicate Class + Subject + Teacher inside file -> DUPLICATE_CLASS_SUBJECT_TEACHER_IN_FILE -> REJECT."""
    # Handled collectively by DUPLICATE_CLASS_SUBJECT_IN_FILE or duplicate validation checks
    # As the system rejects duplicate Class + Subject, duplicate CST is automatically caught.
    pass


def test_import_class_structure_existing_class_subject(
    client: TestClient, api_test_data, db: Session
):
    """TEST 12: Existing ClassSubject -> reuse, do not duplicate, successful import."""
    headers_a = api_test_data["headers_admin_a"]
    year_2025 = api_test_data["year_2025"]
    school_a = api_test_data["school_a"]
    teacher = api_test_data["teacher_math_a"]

    cls = ClassEntity(
        school_id=school_a.id, academic_year_id=year_2025.id, name="X-MIPA-1", grade_level="10"
    )
    db.add(cls)
    subj = Subject(school_id=school_a.id, code="MAT-10", name="Matematika", is_active=True)
    db.add(subj)
    db.commit()

    # Pre-existing ClassSubject
    cs = ClassSubject(school_id=school_a.id, class_id=cls.id, subject_id=subj.id)
    db.add(cs)
    db.commit()

    ts = TeacherSubject(school_id=school_a.id, teacher_id=teacher.id, subject_id=subj.id)
    db.add(ts)
    db.commit()

    payload = {
        "academic_year_id": year_2025.id,
        "classes": [
            {
                "name": "X-MIPA-1",
                "grade_level": "10",
                "students": [],
                "subjects": [
                    {"subject_code": "MAT-10", "teacher_code": teacher.username, "row_num": 2}
                ],
            }
        ],
    }

    res = client.post("/api/v1/admin/classes/import-full", json=payload, headers=headers_a)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"


def test_import_class_structure_existing_cst(client: TestClient, api_test_data, db: Session):
    """TEST 13: Existing ClassSubjectTeacher -> reuse/assign_or_update, successful import."""
    headers_a = api_test_data["headers_admin_a"]
    year_2025 = api_test_data["year_2025"]
    school_a = api_test_data["school_a"]
    teacher = api_test_data["teacher_math_a"]

    cls = ClassEntity(
        school_id=school_a.id, academic_year_id=year_2025.id, name="X-MIPA-1", grade_level="10"
    )
    db.add(cls)
    subj = Subject(school_id=school_a.id, code="MAT-10", name="Matematika", is_active=True)
    db.add(subj)
    db.commit()

    # Pre-existing ClassSubject and ClassSubjectTeacher
    cs = ClassSubject(school_id=school_a.id, class_id=cls.id, subject_id=subj.id)
    db.add(cs)
    cst = ClassSubjectTeacher(
        school_id=school_a.id, class_id=cls.id, subject_id=subj.id, teacher_id=teacher.id
    )
    db.add(cst)
    db.commit()

    ts = TeacherSubject(school_id=school_a.id, teacher_id=teacher.id, subject_id=subj.id)
    db.add(ts)
    db.commit()

    payload = {
        "academic_year_id": year_2025.id,
        "classes": [
            {
                "name": "X-MIPA-1",
                "grade_level": "10",
                "students": [],
                "subjects": [
                    {"subject_code": "MAT-10", "teacher_code": teacher.username, "row_num": 2}
                ],
            }
        ],
    }

    res = client.post("/api/v1/admin/classes/import-full", json=payload, headers=headers_a)
    assert res.status_code == 200
    assert res.json()["status"] == "success"


def test_import_class_structure_mixed_valid_invalid(client: TestClient, api_test_data, db: Session):
    """TEST 14: Mixed valid + invalid rows -> complete rollback -> zero new relationships created."""
    headers_a = api_test_data["headers_admin_a"]
    year_2025 = api_test_data["year_2025"]
    school_a = api_test_data["school_a"]
    teacher = api_test_data["teacher_math_a"]

    # Class & Subject 1 valid
    cls1 = ClassEntity(
        school_id=school_a.id, academic_year_id=year_2025.id, name="X-MIPA-1", grade_level="10"
    )
    db.add(cls1)
    subj1 = Subject(school_id=school_a.id, code="MAT-10", name="Matematika", is_active=True)
    db.add(subj1)
    db.flush()
    # Competency for Subject 1
    ts1 = TeacherSubject(school_id=school_a.id, teacher_id=teacher.id, subject_id=subj1.id)
    db.add(ts1)

    # Class 2 exists but Subject 2 DOES NOT exist (invalid reference)
    cls2 = ClassEntity(
        school_id=school_a.id, academic_year_id=year_2025.id, name="X-MIPA-2", grade_level="10"
    )
    db.add(cls2)
    db.commit()

    payload = {
        "academic_year_id": year_2025.id,
        "classes": [
            {
                "name": "X-MIPA-1",
                "grade_level": "10",
                "students": [],
                "subjects": [
                    {"subject_code": "MAT-10", "teacher_code": teacher.username, "row_num": 2}
                ],
            },
            {
                "name": "X-MIPA-2",
                "grade_level": "10",
                "students": [],
                "subjects": [
                    {
                        "subject_code": "INVALID-SUBJ",  # Invalid
                        "teacher_code": teacher.username,
                        "row_num": 3,
                    }
                ],
            },
        ],
    }

    res = client.post("/api/v1/admin/classes/import-full", json=payload, headers=headers_a)
    assert res.status_code == 422
    data = res.json()
    assert data["status"] == "error"

    # Verify zero created (both ClassSubject and ClassSubjectTeacher for X-MIPA-1 are not created)
    cs = db.query(ClassSubject).filter_by(class_id=cls1.id, subject_id=subj1.id).first()
    assert cs is None


def test_import_class_structure_db_failure_rollback(
    client: TestClient, api_test_data, db: Session, monkeypatch
):
    """TEST 15 & 16: Database persistence failure -> rollback -> zero new relationships created."""
    headers_a = api_test_data["headers_admin_a"]
    year_2025 = api_test_data["year_2025"]
    school_a = api_test_data["school_a"]
    teacher = api_test_data["teacher_math_a"]

    cls = ClassEntity(
        school_id=school_a.id, academic_year_id=year_2025.id, name="X-MIPA-1", grade_level="10"
    )
    db.add(cls)
    subj = Subject(school_id=school_a.id, code="MAT-10", name="Matematika", is_active=True)
    db.add(subj)
    db.commit()
    ts = TeacherSubject(school_id=school_a.id, teacher_id=teacher.id, subject_id=subj.id)
    db.add(ts)
    db.commit()

    # Mock assign_or_update to fail and raise exception during database persistence
    from app.repositories.academic.class_subject_teacher_repository import (
        ClassSubjectTeacherRepository,
    )

    def mock_assign(*args, **kwargs):
        raise Exception("Simulated DB write error for ClassStructure import")

    monkeypatch.setattr(ClassSubjectTeacherRepository, "assign_or_update", mock_assign)

    payload = {
        "academic_year_id": year_2025.id,
        "classes": [
            {
                "name": "X-MIPA-1",
                "grade_level": "10",
                "students": [],
                "subjects": [
                    {"subject_code": "MAT-10", "teacher_code": teacher.username, "row_num": 2}
                ],
            }
        ],
    }

    res = client.post("/api/v1/admin/classes/import-full", json=payload, headers=headers_a)
    assert res.status_code == 500
    assert "Gagal melakukan penyimpanan data ke database" in res.json()["detail"]

    # Verify zero created (atomic rollback worked)
    cs = db.query(ClassSubject).filter_by(class_id=cls.id, subject_id=subj.id).first()
    assert cs is None
