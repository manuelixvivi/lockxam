import uuid
from datetime import datetime, timedelta, timezone
import pytest

from app.core.security.password import hash_password
from app.models.security.auth_account import AuthAccount
from app.models.academic.academic_year import AcademicYear
from app.models.academic.academic_semester import AcademicSemester
from app.models.academic.class_entity import ClassEntity
from app.models.academic.subject import Subject
from app.models.academic.exam_schedule import ExamSchedule
from app.models.academic.student_class_enrollment import StudentClassEnrollment
from app.models.exam.exam_session import ExamSession, ExamSessionStatus
from app.models.exam.exam_attempt import ExamAttempt
from app.models.exam.device_session import DeviceSession, DeviceSessionStatus
from app.models.exam.enums import ExamAttemptStatus
from app.services.exam.exam_service import ExamService
from app.exceptions import BusinessException


def create_teacher_account(db, school_id, username_prefix="teacher"):
    hashed = hash_password("Password123!")
    username = f"{username_prefix}_{uuid.uuid4().hex[:6]}"
    acc = AuthAccount(
        public_id=uuid.uuid4(),
        school_id=school_id,
        username=username,
        password_hash=hashed,
        role="TEACHER",
        is_active=True,
    )
    db.add(acc)
    db.flush()
    return {"account": acc, "username": username, "password": "Password123!"}


def setup_exam_environment(db, school_id, proctor_id):
    ay = AcademicYear(
        school_id=school_id,
        name="2026/2027",
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=365),
        status="ACTIVE",
    )
    db.add(ay)
    db.flush()

    sem = AcademicSemester(
        academic_year_id=ay.id, code="GANJIL", display_name="Ganjil", status="ACTIVE"
    )
    db.add(sem)
    db.flush()

    cls = ClassEntity(school_id=school_id, academic_year_id=ay.id, name="Class 10A")
    db.add(cls)
    db.flush()

    subj = Subject(school_id=school_id, code="MATH10", name="Mathematics")
    db.add(subj)
    db.flush()

    schedule = ExamSchedule(
        school_id=school_id,
        academic_year_id=ay.id,
        academic_semester_id=sem.id,
        class_id=cls.id,
        subject_id=subj.id,
        teacher_id=proctor_id,
        proctor_id=proctor_id,
        title="PTS Math 10A",
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc) + timedelta(hours=2),
        duration_minutes=60,
    )
    db.add(schedule)
    db.flush()

    # Enrolled student
    student_acc = AuthAccount(
        public_id=uuid.uuid4(),
        school_id=school_id,
        username=f"student_{uuid.uuid4().hex[:6]}",
        password_hash="hash",
        role="STUDENT",
        is_active=True,
    )
    db.add(student_acc)
    db.flush()

    enrollment = StudentClassEnrollment(
        school_id=school_id,
        student_id=student_acc.id,
        class_id=cls.id,
        academic_year_id=ay.id,
        status="ACTIVE",
    )
    db.add(enrollment)

    # Unenrolled student
    unenrolled_acc = AuthAccount(
        public_id=uuid.uuid4(),
        school_id=school_id,
        username=f"unenrolled_{uuid.uuid4().hex[:6]}",
        password_hash="hash",
        role="STUDENT",
        is_active=True,
    )
    db.add(unenrolled_acc)
    db.commit()

    return {
        "schedule": schedule,
        "class": cls,
        "enrolled_student": student_acc,
        "unenrolled_student": unenrolled_acc,
    }


def test_proctor_bau_bola_rejection(client, db, test_school):
    test_school.status = "ACTIVE"
    db.add(test_school)
    db.commit()

    proctor_teacher = create_teacher_account(db, test_school.id, "proctor_legit")
    attacker_teacher = create_teacher_account(db, test_school.id, "proctor_rogue")

    env = setup_exam_environment(db, test_school.id, proctor_teacher["account"].id)
    schedule = env["schedule"]
    enrolled_student = env["enrolled_student"]

    # Login attacker teacher
    att_login = client.post(
        "/api/v1/auth/login",
        json={"username": attacker_teacher["username"], "password": attacker_teacher["password"]},
    )
    attacker_token = att_login.json()["access_token"]

    headers = {"Authorization": f"Bearer {attacker_token}"}

    # 1. Attacker tries to log event for schedule where they are NOT proctor -> 403
    evt_res = client.post(
        f"/api/v1/proctor/assignments/{schedule.id}/events",
        json={
            "student_id": enrolled_student.id,
            "event_type": "VIOLATION_DETECTED",
            "reason": "Unauthorized event log attempt",
            "action_taken": "NONE",
        },
        headers=headers,
    )
    assert evt_res.status_code == 403
    assert "Akses ditolak" in evt_res.json()["detail"]

    # 2. Attacker tries to get/create BAU for schedule -> 403
    bau_res = client.get(
        f"/api/v1/proctor/assignments/{schedule.id}/bau",
        headers=headers,
    )
    assert bau_res.status_code == 403

    # Create legitimate BAU using legitimate proctor token first
    proctor_login = client.post(
        "/api/v1/auth/login",
        json={"username": proctor_teacher["username"], "password": proctor_teacher["password"]},
    )
    proctor_token = proctor_login.json()["access_token"]
    legit_headers = {"Authorization": f"Bearer {proctor_token}"}

    bau_legit = client.get(
        f"/api/v1/proctor/assignments/{schedule.id}/bau",
        headers=legit_headers,
    )
    assert bau_legit.status_code == 200
    bau_id = bau_legit.json()["id"]

    # 3. Attacker tries to update attendance for this BAU -> 403
    att_update_res = client.put(
        f"/api/v1/proctor/bau/{bau_id}/attendance",
        json={"student_id": enrolled_student.id, "attendance_status": "HADIR"},
        headers=headers,
    )
    assert att_update_res.status_code == 403

    # 4. Attacker tries to submit this BAU -> 403
    sub_res = client.post(
        f"/api/v1/proctor/bau/{bau_id}/submit",
        json={"proctor_notes": "Rogue submission"},
        headers=headers,
    )
    assert sub_res.status_code == 403


def test_proctor_attendance_student_enrollment_validation(client, db, test_school):
    test_school.status = "ACTIVE"
    db.add(test_school)
    db.commit()

    proctor_teacher = create_teacher_account(db, test_school.id, "proctor_enrollment")
    env = setup_exam_environment(db, test_school.id, proctor_teacher["account"].id)
    schedule = env["schedule"]
    enrolled_student = env["enrolled_student"]
    unenrolled_student = env["unenrolled_student"]

    proctor_login = client.post(
        "/api/v1/auth/login",
        json={"username": proctor_teacher["username"], "password": proctor_teacher["password"]},
    )
    headers = {"Authorization": f"Bearer {proctor_login.json()['access_token']}"}

    # Get BAU
    bau_res = client.get(f"/api/v1/proctor/assignments/{schedule.id}/bau", headers=headers)
    assert bau_res.status_code == 200
    bau_id = bau_res.json()["id"]

    # Update attendance for enrolled student -> Success 200
    res_enrolled = client.put(
        f"/api/v1/proctor/bau/{bau_id}/attendance",
        json={"student_id": enrolled_student.id, "attendance_status": "HADIR", "reason": "Present in class"},
        headers=headers,
    )
    assert res_enrolled.status_code == 200
    assert res_enrolled.json()["attendance_status"] == "HADIR"

    # Update attendance for UNENROLLED student -> 400 Bad Request
    res_unenrolled = client.put(
        f"/api/v1/proctor/bau/{bau_id}/attendance",
        json={"student_id": unenrolled_student.id, "attendance_status": "HADIR", "reason": "Invalid student"},
        headers=headers,
    )
    assert res_unenrolled.status_code == 400
    assert "Siswa tidak terdaftar" in res_unenrolled.json()["detail"]


def test_strict_device_id_matching_in_start_attempt(db, test_school):
    test_school.status = "ACTIVE"
    db.add(test_school)
    db.commit()

    teacher = create_teacher_account(db, test_school.id, "dev_test_teacher")
    env = setup_exam_environment(db, test_school.id, teacher["account"].id)
    schedule = env["schedule"]
    student = env["enrolled_student"]

    from app.models.teacher.question_package import QuestionPackage
    pkg = QuestionPackage(
        owner_teacher_account_id=teacher["account"].id,
        school_id=test_school.id,
        name="Device Test Package",
        class_level="10",
        target_counts={},
        subject="Mathematics",
        status="READY",
    )
    db.add(pkg)
    db.flush()

    session = ExamSession(
        schedule_id=schedule.id,
        package_id=pkg.id,
        scheduled_start_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        scheduled_end_at=datetime.now(timezone.utc) + timedelta(hours=1),
        duration_minutes=60,
        status=ExamSessionStatus.ACTIVE,
    )
    db.add(session)
    db.flush()

    from app.repositories.exam.checkin_repository import checkin_repository
    from app.models.academic.exam_snapshot import ExamSnapshot
    snap = ExamSnapshot(
        school_id=test_school.id,
        exam_schedule_id=schedule.id,
        question_package_id=pkg.id,
        teacher_id=teacher["account"].id,
        class_id=env["class"].id,
        subject_id=schedule.subject_id,
        academic_year_id=schedule.academic_year_id,
        academic_semester_id=schedule.academic_semester_id,
        snapshot_data={"questions": [], "rules_config": {"randomize_per_type": True}},
        total_questions=0,
        total_points=100,
        duration_minutes=60,
        is_locked=True,
    )
    db.add(snap)

    from app.models.exam.exam_checkin import ExamCheckin
    checkin = ExamCheckin(
        schedule_id=schedule.id,
        student_id=student.id,
        device_id="DEVICE_ID_AAA",
        checked_in_at=datetime.now(timezone.utc),
    )
    db.add(checkin)
    db.commit()

    # Device 1 starts attempt -> Success
    attempt1 = ExamService.start_attempt(
        db=db,
        session_id=session.id,
        student_id=student.id,
        device_id="DEVICE_ID_AAA",
        ip_address="192.168.1.10",
    )
    assert attempt1.id is not None

    # Resuming attempt from Device 1 -> Success
    attempt1_resume = ExamService.start_attempt(
        db=db,
        session_id=session.id,
        student_id=student.id,
        device_id="DEVICE_ID_AAA",
        ip_address="192.168.1.10",
    )
    assert attempt1_resume.id == attempt1.id

    # Resuming attempt from Device 2 (different device ID without reset) -> HTTP 403
    with pytest.raises(BusinessException) as exc_info:
        ExamService.start_attempt(
            db=db,
            session_id=session.id,
            student_id=student.id,
            device_id="DEVICE_ID_BBB_DIFFERENT",
            ip_address="192.168.1.20",
        )
    assert exc_info.value.status_code == 403
    assert "Ujian sedang berlangsung di perangkat lain" in str(exc_info.value)
