import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.academic.academic_semester import AcademicSemester
from app.models.academic.academic_year import AcademicYear
from app.models.academic.enums import AcademicStatus
from app.models.master.school_level import SchoolLevel
from app.models.school.school import School
from app.models.security.auth_account import AuthAccount


@pytest.fixture
def api_test_data(db):
    """Sets up two distinct schools with admin, teachers, and students for rigorous tenant testing."""
    lvl = db.query(SchoolLevel).first()
    if not lvl:
        lvl = SchoolLevel(id=1, code="SMA", name="Sekolah Menengah Atas", is_active=True)
        db.add(lvl)
        db.flush()

    # School A
    school_a = School(
        public_id=uuid.uuid4(),
        npsn="11112222",
        code="SCH_A",
        name="SMA Nusantara A",
        domain="sch-a.sch.id",
        school_level_id=lvl.id,
        status="ACTIVE",
        is_active=True,
    )
    # School B (Tenant Isolation Test)
    school_b = School(
        public_id=uuid.uuid4(),
        npsn="33334444",
        code="SCH_B",
        name="SMA Garuda B",
        domain="sch-b.sch.id",
        school_level_id=lvl.id,
        status="ACTIVE",
        is_active=True,
    )
    db.add_all([school_a, school_b])
    db.flush()

    default_pwd = hash_password("Password123!")

    # Admin A
    admin_a = AuthAccount(
        public_id=uuid.uuid4(),
        school_id=school_a.id,
        username="admin_sch_a",
        password_hash=default_pwd,
        role="SCHOOL_ADMIN",
        is_active=True,
    )
    # Admin B
    admin_b = AuthAccount(
        public_id=uuid.uuid4(),
        school_id=school_b.id,
        username="admin_sch_b",
        password_hash=default_pwd,
        role="SCHOOL_ADMIN",
        is_active=True,
    )
    # Teachers for School A
    teacher_math_a = AuthAccount(
        public_id=uuid.uuid4(),
        school_id=school_a.id,
        username="guru_mat_a",
        name="Pak Budi Matematika",
        password_hash=default_pwd,
        role="TEACHER",
        is_active=True,
    )
    teacher_bio_a = AuthAccount(
        public_id=uuid.uuid4(),
        school_id=school_a.id,
        username="guru_bio_a",
        name="Ibu Siti Biologi",
        password_hash=default_pwd,
        role="TEACHER",
        is_active=True,
    )
    # Students for School A
    student_1 = AuthAccount(
        public_id=uuid.uuid4(),
        school_id=school_a.id,
        username="siswa_ahmad",
        name="Ahmad Pratama",
        nisn="0011223344",
        password_hash=default_pwd,
        role="STUDENT",
        is_active=True,
    )
    student_2 = AuthAccount(
        public_id=uuid.uuid4(),
        school_id=school_a.id,
        username="siswa_budi",
        name="Budi Santoso",
        nisn="0011223355",
        password_hash=default_pwd,
        role="STUDENT",
        is_active=True,
    )

    db.add_all([admin_a, admin_b, teacher_math_a, teacher_bio_a, student_1, student_2])
    db.flush()

    # Academic Year 2025/2026 for School A
    now = datetime.now(timezone.utc)
    year_2025 = AcademicYear(
        public_id=uuid.uuid4(),
        school_id=school_a.id,
        name="2025/2026",
        start_date=now,
        end_date=now + timedelta(days=365),
        status=AcademicStatus.ACTIVE.value,
    )
    db.add(year_2025)
    db.flush()

    sem_ganjil = AcademicSemester(
        public_id=uuid.uuid4(),
        academic_year_id=year_2025.id,
        code="ODD",
        display_name="Semester Ganjil",
        status="ACTIVE",
    )
    db.add(sem_ganjil)
    db.flush()

    # Create JWT Tokens and persist valid user sessions
    from app.core.security.jwt import create_user_token
    from app.services.security.session_service import SessionService

    def make_auth_header(acc):
        sess = SessionService.create_session()
        SessionService.save_session(db, acc.id, sess)
        token = create_user_token(
            user_id=acc.id,
            role=acc.role,
            school_id=acc.school_id,
            session_id=sess["session_id"],
            access_jti=sess["access_jti"],
        )
        return {"Authorization": f"Bearer {token}"}

    headers_admin_a = make_auth_header(admin_a)
    headers_admin_b = make_auth_header(admin_b)
    headers_teacher_a = make_auth_header(teacher_math_a)
    headers_student_1 = make_auth_header(student_1)
    db.flush()

    return {
        "school_a": school_a,
        "school_b": school_b,
        "admin_a": admin_a,
        "admin_b": admin_b,
        "teacher_math_a": teacher_math_a,
        "teacher_bio_a": teacher_bio_a,
        "student_1": student_1,
        "student_2": student_2,
        "year_2025": year_2025,
        "sem_ganjil": sem_ganjil,
        "headers_admin_a": headers_admin_a,
        "headers_admin_b": headers_admin_b,
        "headers_teacher_a": headers_teacher_a,
        "headers_student_1": headers_student_1,
    }


def test_subject_api_and_teacher_competency(client: TestClient, api_test_data):
    """Tests Subject CRUD, competency assignment, and listing qualified teachers."""
    headers_a = api_test_data["headers_admin_a"]
    teacher_math = api_test_data["teacher_math_a"]

    # 1. Create Subject (Matematika)
    res = client.post(
        "/api/v1/admin/subjects",
        json={
            "code": "mat-10",
            "name": "Matematika Wajib Kelas 10",
            "description": "Kurikulum Nasional",
        },
        headers=headers_a,
    )
    assert res.status_code == 201
    subj_data = res.json()
    assert subj_data["code"] == "MAT-10"
    assert subj_data["name"] == "Matematika Wajib Kelas 10"
    subject_id = subj_data["id"]

    # 2. Duplicate Subject Code in same school -> 400
    res_dup = client.post(
        "/api/v1/admin/subjects",
        json={"code": "MAT-10", "name": "Matematika Lain"},
        headers=headers_a,
    )
    assert res_dup.status_code == 400

    # 3. Assign Teacher Competency
    res_comp = client.post(
        f"/api/v1/admin/subjects/{subject_id}/teachers/{teacher_math.id}",
        headers=headers_a,
    )
    assert res_comp.status_code == 200
    assert res_comp.json()["teacher_name"] == "Pak Budi Matematika"

    # 4. List Qualified Teachers for Subject
    res_qual = client.get(f"/api/v1/admin/subjects/{subject_id}/teachers", headers=headers_a)
    assert res_qual.status_code == 200
    teachers = res_qual.json()
    assert len(teachers) == 1
    assert teachers[0]["teacher_id"] == teacher_math.id
    assert teachers[0]["name"] == "Pak Budi Matematika"


def test_class_management_and_uniqueness_invariant(client: TestClient, api_test_data):
    """Tests Class creation and Invariant ACADEMIC-CLASS-001."""
    headers_a = api_test_data["headers_admin_a"]
    year_2025 = api_test_data["year_2025"]

    # 1. Create Class X-MIPA-1
    res = client.post(
        "/api/v1/admin/classes",
        json={"academic_year_id": year_2025.id, "name": "X-MIPA-1", "grade_level": "10"},
        headers=headers_a,
    )
    assert res.status_code == 201
    class_data = res.json()
    assert class_data["name"] == "X-MIPA-1"
    class_id = class_data["id"]

    # 2. Invariant ACADEMIC-CLASS-001: Duplicate class in same year -> 400
    res_dup = client.post(
        "/api/v1/admin/classes",
        json={"academic_year_id": year_2025.id, "name": "X-MIPA-1", "grade_level": "10"},
        headers=headers_a,
    )
    assert res_dup.status_code == 400
    assert "sudah ada pada tahun ajaran" in res_dup.json()["detail"]


def test_student_enrollment_and_mutation_history(client: TestClient, api_test_data):
    """Tests Student Enrollment and Invariant STUDENT-ACADEMIC-001."""
    headers_a = api_test_data["headers_admin_a"]
    year_2025 = api_test_data["year_2025"]
    student = api_test_data["student_1"]

    # Create Class A and Class B
    res_a = client.post(
        "/api/v1/admin/classes",
        json={"academic_year_id": year_2025.id, "name": "X-IPA-1"},
        headers=headers_a,
    )
    class_a_id = res_a.json()["id"]

    res_b = client.post(
        "/api/v1/admin/classes",
        json={"academic_year_id": year_2025.id, "name": "X-IPA-2"},
        headers=headers_a,
    )
    class_b_id = res_b.json()["id"]

    # 1. Enroll to Class A
    res_enr = client.post(
        f"/api/v1/admin/classes/{class_a_id}/students",
        json={"student_id": student.id},
        headers=headers_a,
    )
    assert res_enr.status_code == 201
    assert res_enr.json()["status"] == "ACTIVE"
    assert res_enr.json()["class_name"] == "X-IPA-1"

    # Verify student is in Class A
    res_list_a = client.get(f"/api/v1/admin/classes/{class_a_id}/students", headers=headers_a)
    assert len(res_list_a.json()) == 1

    # 2. Mutasi: Transfer student to Class B
    res_trans = client.post(
        f"/api/v1/admin/classes/{class_b_id}/students",
        json={"student_id": student.id},
        headers=headers_a,
    )
    assert res_trans.status_code == 201
    assert res_trans.json()["status"] == "ACTIVE"
    assert res_trans.json()["class_name"] == "X-IPA-2"

    # Class A now has 0 ACTIVE students (1 TRANSFERRED history record)
    res_list_a_after = client.get(f"/api/v1/admin/classes/{class_a_id}/students", headers=headers_a)
    active_in_a = [s for s in res_list_a_after.json() if s["status"] == "ACTIVE"]
    transferred_in_a = [s for s in res_list_a_after.json() if s["status"] == "TRANSFERRED"]
    assert len(active_in_a) == 0
    assert len(transferred_in_a) == 1

    # Class B now has 1 ACTIVE student
    res_list_b_after = client.get(f"/api/v1/admin/classes/{class_b_id}/students", headers=headers_a)
    active_in_b = [s for s in res_list_b_after.json() if s["status"] == "ACTIVE"]
    assert len(active_in_b) == 1


def test_candidate_teacher_api_and_class_assignment(client: TestClient, api_test_data):
    """
    Tests the Teacher Candidate Endpoint:
    GET /api/v1/admin/classes/{class_id}/subjects/{subject_id}/teacher-candidates
    Ensures:
      1. Only teachers with competency in subject_id are returned
      2. Non-competent teachers are rejected if assigned
      3. Competent teachers are successfully assigned
    """
    headers_a = api_test_data["headers_admin_a"]
    year_2025 = api_test_data["year_2025"]
    teacher_math = api_test_data["teacher_math_a"]
    teacher_bio = api_test_data["teacher_bio_a"]

    # 1. Create Class
    res_cls = client.post(
        "/api/v1/admin/classes",
        json={"academic_year_id": year_2025.id, "name": "XI-IPA-1"},
        headers=headers_a,
    )
    class_id = res_cls.json()["id"]

    # 2. Create Subject (Matematika)
    res_sub = client.post(
        "/api/v1/admin/subjects",
        json={"code": "MAT-XI", "name": "Matematika Peminatan XI"},
        headers=headers_a,
    )
    subject_id = res_sub.json()["id"]

    # 3. Assign Subject to Class
    client.post(
        f"/api/v1/admin/classes/{class_id}/subjects",
        json={"subject_id": subject_id},
        headers=headers_a,
    )

    # 4. Assign Math competency ONLY to teacher_math
    client.post(
        f"/api/v1/admin/subjects/{subject_id}/teachers/{teacher_math.id}", headers=headers_a
    )

    # 5. TEST CANDIDATE TEACHER API
    res_candidates = client.get(
        f"/api/v1/admin/classes/{class_id}/subjects/{subject_id}/teacher-candidates",
        headers=headers_a,
    )
    assert res_candidates.status_code == 200
    candidates = res_candidates.json()
    assert len(candidates) == 1
    assert candidates[0]["teacher_id"] == teacher_math.id
    assert candidates[0]["name"] == "Pak Budi Matematika"
    assert candidates[0]["status"] == "ACTIVE"

    # 6. Assign non-competent teacher (teacher_bio) -> FAILS HTTP 400 (CLASS-TEACHER-001)
    res_fail = client.post(
        f"/api/v1/admin/classes/{class_id}/subjects/{subject_id}/teachers",
        json={"teacher_id": teacher_bio.id},
        headers=headers_a,
    )
    assert res_fail.status_code == 400
    assert "belum memiliki kompetensi" in res_fail.json()["detail"]

    # 7. Assign competent teacher (teacher_math) -> SUCCESS HTTP 200
    res_ok = client.post(
        f"/api/v1/admin/classes/{class_id}/subjects/{subject_id}/teachers",
        json={"teacher_id": teacher_math.id},
        headers=headers_a,
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["teacher_name"] == "Pak Budi Matematika"


def test_exam_schedule_api(client: TestClient, api_test_data):
    """Tests Exam Schedule creation and automatic teacher derivation (EXAM-SCHEDULE-001)."""
    headers_a = api_test_data["headers_admin_a"]
    year_2025 = api_test_data["year_2025"]
    sem_ganjil = api_test_data["sem_ganjil"]
    teacher_math = api_test_data["teacher_math_a"]

    # Setup Class, Subject, and Class-Subject-Teacher
    res_cls = client.post(
        "/api/v1/admin/classes",
        json={"academic_year_id": year_2025.id, "name": "XII-MIPA-1"},
        headers=headers_a,
    )
    class_id = res_cls.json()["id"]

    res_sub = client.post(
        "/api/v1/admin/subjects",
        json={"code": "MAT-XII", "name": "Matematika XII"},
        headers=headers_a,
    )
    subject_id = res_sub.json()["id"]

    client.post(
        f"/api/v1/admin/subjects/{subject_id}/teachers/{teacher_math.id}", headers=headers_a
    )
    client.post(
        f"/api/v1/admin/classes/{class_id}/subjects",
        json={"subject_id": subject_id},
        headers=headers_a,
    )
    client.post(
        f"/api/v1/admin/classes/{class_id}/subjects/{subject_id}/teachers",
        json={"teacher_id": teacher_math.id},
        headers=headers_a,
    )

    # 1. Create Exam Schedule
    now = datetime.now(timezone.utc)
    res_sched = client.post(
        "/api/v1/admin/exam-schedules",
        json={
            "academic_year_id": year_2025.id,
            "academic_semester_id": sem_ganjil.id,
            "class_id": class_id,
            "subject_id": subject_id,
            "title": "Penilaian Akhir Semester Matematika",
            "start_time": (now + timedelta(days=1)).isoformat(),
            "end_time": (now + timedelta(days=1, hours=2)).isoformat(),
            "duration_minutes": 90,
        },
        headers=headers_a,
    )
    assert res_sched.status_code == 201
    sched_data = res_sched.json()
    assert sched_data["title"] == "Penilaian Akhir Semester Matematika"
    assert sched_data["teacher_name"] == "Pak Budi Matematika"
    assert sched_data["status"] == "DRAFT"
    schedule_public_id = sched_data["public_id"]

    # 2. Assign Proctor
    res_proc = client.put(
        f"/api/v1/admin/exam-schedules/{schedule_public_id}/proctor",
        json={"proctor_id": teacher_math.id},
        headers=headers_a,
    )
    assert res_proc.status_code == 200
    assert res_proc.json()["proctor_name"] == "Pak Budi Matematika"

    # 3. List Schedules
    res_list = client.get(f"/api/v1/admin/exam-schedules?class_id={class_id}", headers=headers_a)
    assert res_list.status_code == 200
    assert len(res_list.json()) == 1


def test_tenant_isolation_and_rbac(client: TestClient, api_test_data):
    """Ensures strict multi-tenant isolation and role-based access control."""
    headers_a = api_test_data["headers_admin_a"]
    headers_b = api_test_data["headers_admin_b"]
    headers_teacher = api_test_data["headers_teacher_a"]
    headers_student = api_test_data["headers_student_1"]
    year_2025 = api_test_data["year_2025"]

    # School A creates a Subject
    res = client.post(
        "/api/v1/admin/subjects", json={"code": "FIS-10", "name": "Fisika"}, headers=headers_a
    )
    assert res.status_code == 201
    subject_public_id = res.json()["public_id"]

    # 1. School B cannot access School A's subject
    res_b = client.get(f"/api/v1/admin/subjects/{subject_public_id}", headers=headers_b)
    assert res_b.status_code == 404

    # 2. Non-admin (Teacher) cannot create subjects or classes
    res_t = client.post(
        "/api/v1/admin/subjects", json={"code": "KIM-10", "name": "Kimia"}, headers=headers_teacher
    )
    assert res_t.status_code == 403

    # 3. Non-admin (Student) cannot create subjects or classes
    res_s = client.post(
        "/api/v1/admin/classes",
        json={"academic_year_id": year_2025.id, "name": "X-1"},
        headers=headers_student,
    )
    assert res_s.status_code == 403


def test_exam_schedule_packages_and_import(client: TestClient, api_test_data, db):
    import traceback

    try:
        headers_a = api_test_data["headers_admin_a"]
        year_2025 = api_test_data["year_2025"]
        sem_ganjil = api_test_data["sem_ganjil"]
        school_a = api_test_data["school_a"]

        # 1. Create a proctor teacher with a teacher_code
        from app.services.school.staff_service import SchoolStaffService

        teacher, _ = SchoolStaffService.create_teacher(
            db=db,
            school_id=school_a.id,
            name="Pengawas Hebat",
            nip="11223344",
            gender="L",
            registered_year=2025,
            classes_taught=[],
            # subjects_taught removed: competency assigned via TeacherSubject endpoint
            teacher_code="P-HEBAT",
        )
        db.commit()

        # Create Subject & Class
        res_subj = client.post(
            "/api/v1/admin/subjects",
            json={"code": "KIMIA", "name": "Kimia Dasar"},
            headers=headers_a,
        )
        assert res_subj.status_code == 201
        subj_id = res_subj.json()["id"]

        res_cls = client.post(
            "/api/v1/admin/classes",
            json={"academic_year_id": year_2025.id, "name": "XII IPA 2"},
            headers=headers_a,
        )
        assert res_cls.status_code == 201
        class_id = res_cls.json()["id"]

        # Assign Teacher to handle subject in class (required by invariant EXAM-SCHEDULE-001)
        # Let's assign our teacher_math to teach Kimia in XII IPA 2
        teacher_math = api_test_data["teacher_math_a"]

        # Assign competency to teacher first
        from app.services.academic.subject_service import SubjectService

        SubjectService.assign_teacher_competency(db, school_a.id, teacher_math.id, subj_id)

        # Assign teacher to class subject
        from app.services.academic.class_structure_service import ClassStructureService

        ClassStructureService.assign_teacher_to_class_subject(
            db, school_a.id, class_id, subj_id, teacher_math.id
        )
        db.commit()

        # 2. Create Exam Schedule Package
        res_pkg = client.post(
            "/api/v1/admin/exam-schedules/packages",
            json={"title": "PAS Ganjil 2025", "academic_year_id": year_2025.id},
            headers=headers_a,
        )
        assert res_pkg.status_code == 201
        pkg_data = res_pkg.json()
        assert pkg_data["title"] == "PAS Ganjil 2025"
        assert pkg_data["academic_year_name"] == "2025/2026"
        pkg_public_id = pkg_data["public_id"]

        # 3. Import Schedules using proctor teacher_code "P-HEBAT"
        rows = [
            {
                "Kelas": "XII IPA 2",
                "Mata Pelajaran": "KIMIA",
                "Tanggal Ujian": "2026-10-12",
                "Jam Mulai": "07:30",
                "Jam Selesai": "09:00",
                "Kode Pengawas": "P-HEBAT",
            }
        ]

        res_import = client.post(
            f"/api/v1/admin/exam-schedules/packages/{pkg_public_id}/import",
            json=rows,
            headers=headers_a,
        )
        assert res_import.status_code == 200
        imported_data = res_import.json()
        assert len(imported_data) == 1
        assert imported_data[0]["class_name"] == "XII IPA 2"
        assert imported_data[0]["subject_name"] == "Kimia Dasar"
        assert imported_data[0]["proctor_code"] == "P-HEBAT"
        assert imported_data[0]["proctor_name"] == "Pengawas Hebat"
        assert imported_data[0]["duration_minutes"] == 90

        # 4. List Packages
        res_list = client.get("/api/v1/admin/exam-schedules/packages", headers=headers_a)
        if res_list.status_code == 422:
            raise Exception(f"Pydantic 422 Error Detail: {res_list.json()}")
        assert res_list.status_code == 200
        assert len(res_list.json()) >= 1
        assert any(str(p["public_id"]) == str(pkg_public_id) for p in res_list.json())

        # 5. Delete Package
        res_del = client.delete(
            f"/api/v1/admin/exam-schedules/packages/{pkg_public_id}", headers=headers_a
        )
        assert res_del.status_code == 204
    except Exception as e:
        print("TEST EXCEPTION OCCURRED:", e)
        traceback.print_exc()
        raise e


def test_exam_schedule_class_overlap_validation(client: TestClient, api_test_data, db: Session):
    headers_a = api_test_data["headers_admin_a"]
    year_2025 = api_test_data["year_2025"]
    sem_ganjil = api_test_data["sem_ganjil"]
    school_a = api_test_data["school_a"]
    teacher_math = api_test_data["teacher_math_a"]
    teacher_bio = api_test_data["teacher_bio_a"]

    # 1. Create a class XII IPA 3 via API
    res_cls = client.post(
        "/api/v1/admin/classes",
        json={"academic_year_id": year_2025.id, "name": "XII IPA 3", "grade_level": "12"},
        headers=headers_a,
    )
    assert res_cls.status_code == 201
    class_id = res_cls.json()["id"]

    # 2. Create two subjects via API
    res_sub1 = client.post(
        "/api/v1/admin/subjects",
        json={"code": "MAT-A", "name": "Matematika Overlap"},
        headers=headers_a,
    )
    assert res_sub1.status_code == 201
    sub1_id = res_sub1.json()["id"]

    res_sub2 = client.post(
        "/api/v1/admin/subjects",
        json={"code": "IND-A", "name": "Bahasa Overlap"},
        headers=headers_a,
    )
    assert res_sub2.status_code == 201
    sub2_id = res_sub2.json()["id"]

    # 3. Assign Subjects to Class and assign Teacher competencies
    client.post(
        f"/api/v1/admin/classes/{class_id}/subjects",
        json={"subject_id": sub1_id},
        headers=headers_a,
    )
    client.post(
        f"/api/v1/admin/classes/{class_id}/subjects",
        json={"subject_id": sub2_id},
        headers=headers_a,
    )

    from app.services.academic.class_structure_service import ClassStructureService
    from app.services.academic.subject_service import SubjectService

    SubjectService.assign_teacher_competency(db, school_a.id, teacher_math.id, sub1_id)
    ClassStructureService.assign_teacher_to_class_subject(
        db, school_a.id, class_id, sub1_id, teacher_math.id
    )

    SubjectService.assign_teacher_competency(db, school_a.id, teacher_bio.id, sub2_id)
    ClassStructureService.assign_teacher_to_class_subject(
        db, school_a.id, class_id, sub2_id, teacher_bio.id
    )
    db.commit()

    # 4. Create first Exam Schedule manually (08:00 - 09:30)
    res_sch1 = client.post(
        "/api/v1/admin/exam-schedules",
        json={
            "academic_year_id": year_2025.id,
            "academic_semester_id": sem_ganjil.id,
            "class_id": class_id,
            "subject_id": sub1_id,
            "title": "PAS Matematika",
            "start_time": "2026-11-20T08:00:00Z",
            "end_time": "2026-11-20T09:30:00Z",
            "duration_minutes": 90,
        },
        headers=headers_a,
    )
    print("SCH1 RESPONSE:", res_sch1.status_code, res_sch1.json())
    assert res_sch1.status_code == 201

    # 5. Attempt to create overlapping Exam Schedule manually (09:00 - 10:30) -> should fail with 400
    res_sch2 = client.post(
        "/api/v1/admin/exam-schedules",
        json={
            "academic_year_id": year_2025.id,
            "academic_semester_id": sem_ganjil.id,
            "class_id": class_id,
            "subject_id": sub2_id,
            "title": "PAS Bahasa",
            "start_time": "2026-11-20T09:00:00Z",
            "end_time": "2026-11-20T10:30:00Z",
            "duration_minutes": 90,
        },
        headers=headers_a,
    )
    print("SCH2 RESPONSE:", res_sch2.status_code, res_sch2.json())
    assert res_sch2.status_code == 400
    assert "Jadwal ujian bentrok dengan" in res_sch2.json()["detail"]

    # 6. Non-overlapping back-to-back Exam Schedule (09:30 - 11:00) -> should succeed
    res_sch3 = client.post(
        "/api/v1/admin/exam-schedules",
        json={
            "academic_year_id": year_2025.id,
            "academic_semester_id": sem_ganjil.id,
            "class_id": class_id,
            "subject_id": sub2_id,
            "title": "PAS Bahasa",
            "start_time": "2026-11-20T09:30:00Z",
            "end_time": "2026-11-20T11:00:00Z",
            "duration_minutes": 90,
        },
        headers=headers_a,
    )
    assert res_sch3.status_code == 201

    # 7. Create Exam Schedule Package for XLSX test
    res_pkg = client.post(
        "/api/v1/admin/exam-schedules/packages",
        json={"title": "PAS XLSX Overlap", "academic_year_id": year_2025.id},
        headers=headers_a,
    )
    assert res_pkg.status_code == 201
    pkg_public_id = res_pkg.json()["public_id"]

    # 8. Import rows with overlap within the batch -> should fail with 400
    rows_overlap_batch = [
        {
            "Kelas": "XII IPA 3",
            "Mata Pelajaran": "MAT-A",
            "Tanggal Ujian": "2026-12-10",
            "Jam Mulai": "08:00",
            "Jam Selesai": "09:30",
        },
        {
            "Kelas": "XII IPA 3",
            "Mata Pelajaran": "IND-A",
            "Tanggal Ujian": "2026-12-10",
            "Jam Mulai": "09:00",
            "Jam Selesai": "10:30",
        },
    ]
    res_import1 = client.post(
        f"/api/v1/admin/exam-schedules/packages/{pkg_public_id}/import",
        json=rows_overlap_batch,
        headers=headers_a,
    )
    assert res_import1.status_code == 400
    assert "Bentrok waktu ujian kelas" in res_import1.json()["detail"]

    # 9. Import rows with overlap against database (overlaps with PAS Matematika on Nov 20) -> should fail with 400
    rows_overlap_db = [
        {
            "Kelas": "XII IPA 3",
            "Mata Pelajaran": "MAT-A",
            "Tanggal Ujian": "2026-11-20",
            "Jam Mulai": "08:30",
            "Jam Selesai": "10:00",
        }
    ]
    res_import2 = client.post(
        f"/api/v1/admin/exam-schedules/packages/{pkg_public_id}/import",
        json=rows_overlap_db,
        headers=headers_a,
    )
    assert res_import2.status_code == 400
    assert "sudah memiliki jadwal ujian lain" in res_import2.json()["detail"]


def test_bulk_subject_assignment_and_removal(client: TestClient, api_test_data):
    """Tests bulk subject assignment, teacher isolation/competency, and bulk removal of subjects."""
    headers_a = api_test_data["headers_admin_a"]
    year_2025 = api_test_data["year_2025"]
    teacher_math = api_test_data["teacher_math_a"]

    # 1. Create Class
    res_cls = client.post(
        "/api/v1/admin/classes",
        json={"academic_year_id": year_2025.id, "name": "X-IPA-5", "grade_level": "X"},
        headers=headers_a,
    )
    assert res_cls.status_code == 201
    class_id = res_cls.json()["id"]

    # 2. Create Subjects in Master List
    res_sub1 = client.post(
        "/api/v1/admin/subjects",
        json={"code": "MAT-BULK", "name": "Matematika Bulk"},
        headers=headers_a,
    )
    assert res_sub1.status_code == 201
    sub1_id = res_sub1.json()["id"]

    res_sub2 = client.post(
        "/api/v1/admin/subjects",
        json={"code": "FIS-BULK", "name": "Fisika Bulk"},
        headers=headers_a,
    )
    assert res_sub2.status_code == 201
    sub2_id = res_sub2.json()["id"]

    # Assign Math competency to teacher_math
    client.post(f"/api/v1/admin/subjects/{sub1_id}/teachers/{teacher_math.id}", headers=headers_a)

    # 3. Bulk Assign Subjects
    res_assign = client.post(
        f"/api/v1/admin/classes/{class_id}/subjects/bulk-assign",
        json={"subject_ids": [sub1_id, sub2_id]},
        headers=headers_a,
    )
    assert res_assign.status_code == 200
    assert res_assign.json()["assigned_count"] == 2

    # Verify Class Subjects List
    res_list = client.get(f"/api/v1/admin/classes/{class_id}/subjects", headers=headers_a)
    assert res_list.status_code == 200
    subjects_in_class = res_list.json()
    assert len(subjects_in_class) == 2
    subject_ids = [s["subject_id"] for s in subjects_in_class]
    assert sub1_id in subject_ids
    assert sub2_id in subject_ids

    # 4. Assign Teacher to Mat-Bulk
    res_teach = client.post(
        f"/api/v1/admin/classes/{class_id}/subjects/{sub1_id}/teachers",
        json={"teacher_id": teacher_math.id},
        headers=headers_a,
    )
    assert res_teach.status_code == 200

    # 5. Bulk Remove Subjects
    res_remove = client.post(
        f"/api/v1/admin/classes/{class_id}/subjects/bulk-remove",
        json={"subject_ids": [sub1_id]},
        headers=headers_a,
    )
    assert res_remove.status_code == 200
    assert res_remove.json()["removed_count"] == 1

    # Verify Class Subjects List has only 1 subject left (FIS-BULK)
    res_list2 = client.get(f"/api/v1/admin/classes/{class_id}/subjects", headers=headers_a)
    assert res_list2.status_code == 200
    subjects_in_class_after = res_list2.json()
    assert len(subjects_in_class_after) == 1
    assert subjects_in_class_after[0]["subject_id"] == sub2_id

    # Verify that the master subject 'Matematika Bulk' still exists in the school's master subject list!
    res_master_subj = client.get("/api/v1/admin/subjects", headers=headers_a)
    assert res_master_subj.status_code == 200
    master_subjects = res_master_subj.json()
    master_subject_ids = [s["id"] for s in master_subjects]
    assert sub1_id in master_subject_ids
