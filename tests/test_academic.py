import uuid
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.core.security.password import hash_password
from app.exceptions.base import AcademicValidationException, BusinessException
from app.models.school.school import School
from app.models.security.auth_account import AuthAccount
from app.models.security.enums import UserRole
from app.repositories.academic.academic_year_repository import academic_year_repository
from app.services.academic.academic_service import AcademicService


def create_test_school_and_admin(db, npsn: str) -> tuple[School, AuthAccount]:
    school = School(
        public_id=uuid4(),
        npsn=npsn,
        code=npsn,
        name=f"School {npsn}",
        school_level_id=1,
        status="ACTIVE",
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


def test_create_academic_year_success(db):
    school, admin = create_test_school_and_admin(db, "66660001")
    start = datetime.now(timezone.utc)
    end = start + timedelta(days=365)

    year = AcademicService.create_academic_year(
        db=db, school_id=school.id, name="2025/2026", start_date=start, end_date=end
    )
    db.commit()

    assert year.name == "2025/2026"
    assert year.status == "PLANNED"
    assert year.school_id == school.id


def test_create_academic_year_overlap_error(db):
    school, admin = create_test_school_and_admin(db, "66660002")
    start = datetime.now(timezone.utc)
    end = start + timedelta(days=365)

    # First year
    AcademicService.create_academic_year(
        db=db, school_id=school.id, name="2025/2026", start_date=start, end_date=end
    )
    db.commit()

    # Second year (overlapping dates)
    with pytest.raises(BusinessException) as excinfo:
        AcademicService.create_academic_year(
            db=db,
            school_id=school.id,
            name="2025/2026 Overlap",
            start_date=start + timedelta(days=10),
            end_date=end + timedelta(days=10),
        )
    assert "date range overlaps" in str(excinfo.value)


def test_delete_academic_year(db):
    school, admin = create_test_school_and_admin(db, "66660003")
    start = datetime.now(timezone.utc)
    end = start + timedelta(days=365)

    year = AcademicService.create_academic_year(
        db=db, school_id=school.id, name="2025/2026", start_date=start, end_date=end
    )
    db.commit()

    # Delete planned year
    AcademicService.delete_academic_year(db, year.public_id)
    db.commit()

    assert academic_year_repository.get_by_public_id(db, year.public_id) is None


def test_delete_active_academic_year_error(db):
    school, admin = create_test_school_and_admin(db, "66660004")
    start = datetime.now(timezone.utc)
    end = start + timedelta(days=365)

    year = AcademicService.create_academic_year(
        db=db, school_id=school.id, name="2025/2026", start_date=start, end_date=end
    )
    # Force active
    year.status = "ACTIVE"
    db.commit()

    # Delete active year should fail (BR-ACA-015)
    with pytest.raises(BusinessException) as excinfo:
        AcademicService.delete_academic_year(db, year.public_id)
    assert "Cannot delete Academic Year in status ACTIVE" in str(excinfo.value)


def test_create_and_activate_semester(db):
    school, admin = create_test_school_and_admin(db, "66660005")
    start = datetime.now(timezone.utc)
    end = start + timedelta(days=365)

    year = AcademicService.create_academic_year(
        db=db, school_id=school.id, name="2025/2026", start_date=start, end_date=end
    )
    year.status = "ACTIVE"
    db.commit()

    # Create semester
    sem = AcademicService.create_academic_semester(
        db=db, academic_year_id=year.id, code="ODD", display_name="Ganjil"
    )
    db.commit()

    assert sem.code == "ODD"
    assert sem.status == "PLANNED"

    # Activate semester
    activated = AcademicService.activate_semester(db, sem.public_id)
    db.commit()

    assert activated.status == "ACTIVE"


def test_rollover_academic_year_success_and_infractions(db, test_superadmin):
    school, admin = create_test_school_and_admin(db, f"666{uuid.uuid4().hex[:5]}")

    # 1. Create Year 1 (Active) & Year 2 (Planned)
    start1 = datetime.now(timezone.utc)
    end1 = start1 + timedelta(days=365)
    year1 = AcademicService.create_academic_year(db, school.id, "Year 1", start1, end1)
    year1.status = "ACTIVE"
    db.flush()

    sem1 = AcademicService.create_academic_semester(db, year1.id, "ODD", "Ganjil")
    sem1.status = "ACTIVE"
    db.flush()
    db.commit()

    start2 = end1 + timedelta(days=1)
    end2 = start2 + timedelta(days=365)
    year2 = AcademicService.create_academic_year(db, school.id, "Year 2", start2, end2)
    db.flush()
    AcademicService.create_academic_semester(db, year2.id, "ODD", "Ganjil")
    db.commit()

    from app.models.academic.class_entity import ClassEntity
    from app.models.academic.subject import Subject
    from app.models.security.auth_account import AuthAccount

    cls1 = ClassEntity(school_id=school.id, academic_year_id=year1.id, name="Class 1")
    db.add(cls1)
    db.flush()

    subj1 = Subject(school_id=school.id, code="SUB1", name="Subject 1")
    db.add(subj1)
    db.flush()

    tcher = AuthAccount(school_id=school.id, public_id=uuid4(), username=f"teacher_{uuid4().hex[:6]}", password_hash="hash", role="TEACHER", is_active=True)
    db.add(tcher)
    db.flush()

    # Insert an active exam schedule and session for Year 1
    from app.models.academic.exam_schedule import ExamSchedule
    from app.models.exam.exam_session import ExamSession, ExamSessionStatus

    sch = ExamSchedule(
        school_id=school.id,
        academic_year_id=year1.id,
        academic_semester_id=sem1.id,
        class_id=cls1.id,
        subject_id=subj1.id,
        teacher_id=tcher.id,
        title="Test Exam",
        start_time=start1,
        end_time=end1,
        duration_minutes=60,
        status="ACTIVE",
    )
    db.add(sch)
    db.flush()

    from app.models.teacher.question_package import QuestionPackage

    pkg1 = QuestionPackage(
        owner_teacher_account_id=tcher.id,
        school_id=school.id,
        name="Rollover Package",
        class_level="10",
        target_counts={},
        subject="SUB1",
        status="READY",
    )
    db.add(pkg1)
    db.flush()

    sess = ExamSession(
        schedule_id=sch.id,
        package_id=pkg1.id,
        scheduled_start_at=start1,
        scheduled_end_at=end1,
        duration_minutes=60,
        status=ExamSessionStatus.ACTIVE,
    )
    db.add(sess)
    db.commit()

    # Rollover should fail with AcademicValidationException due to active exams (BR-ACA-011)
    with pytest.raises(AcademicValidationException) as excinfo:
        AcademicService.rollover_academic_year(db, school.id, year2.public_id)
    assert "Masih ada sesi ujian yang sedang aktif" in excinfo.value.errors[0]

    # Clear active exams
    db.execute(text("DELETE FROM exam_snapshots"))
    db.execute(text("DELETE FROM student_answers"))
    db.execute(text("DELETE FROM exam_attempts"))
    db.execute(text("DELETE FROM exam_sessions"))
    db.execute(text("DELETE FROM exam_schedules"))
    db.commit()

    # Rollover should succeed
    active_year = AcademicService.rollover_academic_year(db, school.id, year2.public_id)
    assert active_year.status == "ACTIVE"
    assert year1.status == "ARCHIVED"
    db.commit()


def test_api_academic_endpoints(client, test_superadmin, db):
    # Authenticate SuperAdmin
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": test_superadmin["username"], "password": test_superadmin["password"]},
    )
    assert login_res.status_code == 200
    sa_token = login_res.json()["access_token"]
    sa_headers = {"Authorization": f"Bearer {sa_token}"}

    # Create a school via API
    npsn = "66669999"
    school_res = client.post(
        "/api/v1/schools",
        headers=sa_headers,
        json={
            "npsn": npsn,
            "name": "API Academic Test School",
            "domain": "api-academic.sch.id",
            "school_level_id": 1,
            "email": "test@academic-school.com",
        },
    )
    assert school_res.status_code == 201

    # Update school status to ACTIVE so mutating operations are permitted
    db_school = db.query(School).filter(School.npsn == npsn).first()
    db_school.status = "ACTIVE"
    
    # Reset admin credentials to legacy test expectations
    admin_acc = db.query(AuthAccount).filter(AuthAccount.school_id == db_school.id).first()
    admin_acc.username = f"admin_{npsn}"
    admin_acc.password_hash = hash_password(f"3qu!6rade{npsn}")
    db.commit()

    # Authenticate School Admin A
    login_admin = client.post(
        "/api/v1/auth/login",
        json={"username": f"admin_{npsn}", "password": f"3qu!6rade{npsn}"},
    )
    assert login_admin.status_code == 200
    admin_token = login_admin.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Create Academic Year via API
    start_date = datetime.now(timezone.utc).isoformat()
    end_date = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()

    year_res = client.post(
        "/api/v1/academic/years",
        headers=admin_headers,
        json={"name": "2025/2026", "start_date": start_date, "end_date": end_date},
    )
    assert year_res.status_code == 201
    year_data = year_res.json()
    assert year_data["status"] == "PLANNED"

    # Create Semester via API
    sem_res = client.post(
        "/api/v1/academic/semesters",
        headers=admin_headers,
        json={"academic_year_id": year_data["id"], "code": "ODD", "display_name": "Ganjil"},
    )
    assert sem_res.status_code == 201
    assert sem_res.json()["status"] == "PLANNED"

    # List Academic Periods via API
    periods_res = client.get("/api/v1/academic/periods", headers=admin_headers)
    assert periods_res.status_code == 200
    assert len(periods_res.json()) == 1
