import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.security.password import hash_password
from app.exceptions import BusinessException
from app.models.security.auth_account import AuthAccount
from app.models.teacher.enums import AttendanceStatus, BAUStatus, ProctorEventType
from app.services.teacher.proctor_service import ProctorService


def create_test_admin(db, school_id):
    hashed = hash_password("Password123!")
    username = f"admin_{uuid.uuid4().hex[:4]}"
    acc = AuthAccount(
        public_id=uuid.uuid4(),
        school_id=school_id,
        username=username,
        password_hash=hashed,
        role="ADMIN",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(acc)
    db.flush()
    return {"account": acc, "username": username, "password": "Password123!"}


def test_log_proctor_event_service(db, test_teacher):
    teacher = test_teacher["account"]
    event = ProctorService.log_proctor_event(
        db=db,
        proctor_assignment_id=101,
        student_id=50,
        event_type=ProctorEventType.VIOLATION_DETECTED,
        reason="Membuka aplikasi lain",
        proctor_id=teacher.id,
        action_taken="DEVICE_LOCKED",
    )

    assert event.id is not None
    assert event.proctor_assignment_id == 101
    assert event.student_id == 50
    assert event.event_type == ProctorEventType.VIOLATION_DETECTED
    assert event.reason == "Membuka aplikasi lain"


def test_bau_lifecycle_service(db):
    proctor_assignment_id = 202
    student_id = 99

    # 1. Get or Create -> DRAFT
    doc = ProctorService.get_or_create_bau(db, proctor_assignment_id)
    assert doc.status == BAUStatus.DRAFT
    assert doc.proctor_assignment_id == proctor_assignment_id

    # 2. Update attendance in DRAFT -> Success
    att = ProctorService.update_attendance(
        db=db,
        bau_document_id=doc.id,
        student_id=student_id,
        status=AttendanceStatus.HADIR,
        reason="Tepat waktu",
    )
    assert att.attendance_status == AttendanceStatus.HADIR
    assert att.reason == "Tepat waktu"

    # 3. Submit -> SUBMITTED
    submitted_doc = ProctorService.submit_bau(db, doc.id, proctor_notes="Ujian lancar")
    assert submitted_doc.status == BAUStatus.SUBMITTED
    assert submitted_doc.proctor_notes == "Ujian lancar"
    assert submitted_doc.submitted_at is not None

    # 4. Try updating after SUBMITTED (> 24 hours) -> FAIL (Locked)
    doc.submitted_at = datetime.now(timezone.utc) - timedelta(hours=25)
    db.commit()

    with pytest.raises(BusinessException) as exc_info:
        ProctorService.update_attendance(
            db=db,
            bau_document_id=doc.id,
            student_id=student_id,
            status=AttendanceStatus.SAKIT,
        )
    assert "Berita Acara telah dikunci" in str(exc_info.value)

    # 5. Request Correction -> CORRECTION_REQUESTED
    correction_doc = ProctorService.request_correction(db, doc.id)
    assert correction_doc.status == BAUStatus.CORRECTION_REQUESTED

    # 6. Resolve Correction: Approve -> DRAFT (Can edit again)
    resolved_approved_doc = ProctorService.resolve_correction(db, doc.id, approve=True)
    assert resolved_approved_doc.status == BAUStatus.DRAFT

    # 7. Update attendance in DRAFT -> Success
    att_updated = ProctorService.update_attendance(
        db=db,
        bau_document_id=doc.id,
        student_id=student_id,
        status=AttendanceStatus.SAKIT,
    )
    assert att_updated.attendance_status == AttendanceStatus.SAKIT

    # 8. Submit again -> SUBMITTED
    submitted_again_doc = ProctorService.submit_bau(db, doc.id)
    assert submitted_again_doc.status == BAUStatus.SUBMITTED

    # 9. Request Correction again -> CORRECTION_REQUESTED
    ProctorService.request_correction(db, doc.id)

    # 10. Resolve Correction: Reject -> SUBMITTED (Locked again)
    resolved_rejected_doc = ProctorService.resolve_correction(db, doc.id, approve=False)
    assert resolved_rejected_doc.status == BAUStatus.SUBMITTED


def test_api_proctor_endpoints(client, test_teacher, db, test_school):
    # Set school Active
    test_school.status = "ACTIVE"
    db.add(test_school)
    db.commit()

    # Login Teacher
    teacher_login = client.post(
        "/api/v1/auth/login",
        json={"username": test_teacher["username"], "password": test_teacher["password"]},
    )
    teacher_token = teacher_login.json()["access_token"]

    # 1. Log Event API -> Success
    event_res = client.post(
        "/api/v1/proctor/assignments/303/events",
        json={
            "student_id": 12,
            "event_type": "DEVICE_RESET",
            "reason": "Reset perangkat utama",
            "action_taken": "DEVICE_RESET_SUCCESS",
        },
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert event_res.status_code == 201
    assert event_res.json()["proctor_assignment_id"] == 303
    assert event_res.json()["event_type"] == "DEVICE_RESET"

    # 2. Get or Create BAU API -> Success
    bau_res = client.get(
        "/api/v1/proctor/assignments/303/bau",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert bau_res.status_code == 200
    bau_data = bau_res.json()
    assert bau_data["status"] == "DRAFT"
    bau_id = bau_data["id"]

    # 3. Update Attendance API -> Success
    att_res = client.put(
        f"/api/v1/proctor/bau/{bau_id}/attendance",
        json={"student_id": 12, "attendance_status": "HADIR", "reason": "Hadir fisik"},
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert att_res.status_code == 200
    assert att_res.json()["attendance_status"] == "HADIR"

    # 4. Submit BAU API -> Success
    submit_res = client.post(
        f"/api/v1/proctor/bau/{bau_id}/submit",
        json={"proctor_notes": "Berjalan tertib"},
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert submit_res.status_code == 200
    assert submit_res.json()["status"] == "SUBMITTED"

    # 5. Request Correction API -> Success
    req_res = client.post(
        f"/api/v1/proctor/bau/{bau_id}/request-correction",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert req_res.status_code == 200
    assert req_res.json()["status"] == "CORRECTION_REQUESTED"

    # 6. Resolve Correction API as Teacher -> Fail with 403 (Teacher cannot resolve)
    resolve_fail_res = client.post(
        f"/api/v1/proctor/bau/{bau_id}/resolve-correction?approve=true",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert resolve_fail_res.status_code == 403

    # Create Admin for the same school
    test_admin = create_test_admin(db, test_school.id)

    # Login Admin
    admin_login = client.post(
        "/api/v1/auth/login",
        json={"username": test_admin["username"], "password": test_admin["password"]},
    )
    admin_token = admin_login.json()["access_token"]

    # 7. Resolve Correction API as Admin -> Success
    resolve_res = client.post(
        f"/api/v1/proctor/bau/{bau_id}/resolve-correction?approve=true",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resolve_res.status_code == 200
    assert resolve_res.json()["status"] == "DRAFT"


def test_proctor_command_endpoints(client, test_teacher, db, test_school, monkeypatch):
    test_school.status = "ACTIVE"
    db.add(test_school)
    db.commit()

    monkeypatch.setenv("TESTING", "True")

    # Login Teacher
    teacher_login = client.post(
        "/api/v1/auth/login",
        json={"username": test_teacher["username"], "password": test_teacher["password"]},
    )
    teacher_token = teacher_login.json()["access_token"]

    from app.models.security.auth_account import AuthAccount
    from app.models.academic.exam_schedule import ExamSchedule
    from app.models.exam.exam_session import ExamSession, ExamSessionStatus
    from app.models.exam.exam_attempt import ExamAttempt
    from app.models.exam.enums import ExamAttemptStatus

    std = AuthAccount(
        id=123,
        public_id=uuid.uuid4(),
        school_id=test_school.id,
        username="siswa_test_proctor",
        password_hash="hash",
        role="STUDENT",
        is_active=True,
    )
    db.add(std)
    db.flush()

    from app.models.academic.academic_year import AcademicYear
    from app.models.academic.academic_semester import AcademicSemester
    from app.models.academic.class_entity import ClassEntity as Class
    from app.models.academic.subject import Subject

    ay = AcademicYear(school_id=test_school.id, name="2026/2027", start_date=datetime.now(timezone.utc), end_date=datetime.now(timezone.utc)+timedelta(days=365), status="ACTIVE")
    db.add(ay)
    db.flush()

    sem = AcademicSemester(academic_year_id=ay.id, code="GANJIL", display_name="Ganjil", status="ACTIVE")
    db.add(sem)
    db.flush()

    cls = Class(school_id=test_school.id, academic_year_id=ay.id, name="Proctor Class")
    db.add(cls)
    db.flush()

    subj = Subject(school_id=test_school.id, code="PROCTOR_SUBJ", name="Proctor Subject")
    db.add(subj)
    db.flush()

    sch = ExamSchedule(
        school_id=test_school.id,
        academic_year_id=ay.id,
        academic_semester_id=sem.id,
        class_id=cls.id,
        subject_id=subj.id,
        teacher_id=test_teacher["account"].id,
        title="Proctor Test Schedule",
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc) + timedelta(hours=2),
        duration_minutes=60,
    )
    db.add(sch)
    db.flush()

    from app.models.teacher.question_package import QuestionPackage

    pkg = QuestionPackage(
        owner_teacher_account_id=test_teacher["account"].id,
        school_id=test_school.id,
        name="Proctor Test Package",
        class_level="10",
        target_counts={},
        subject="Proctor Subject",
        status="READY",
    )
    db.add(pkg)
    db.flush()

    sess = ExamSession(
        schedule_id=sch.id,
        package_id=pkg.id,
        scheduled_start_at=datetime.now(timezone.utc),
        scheduled_end_at=datetime.now(timezone.utc) + timedelta(hours=2),
        duration_minutes=60,
        status=ExamSessionStatus.ACTIVE,
    )
    db.add(sess)
    db.flush()

    attempt = ExamAttempt(
        exam_session_id=sess.id,
        student_id=std.id,
        status=ExamAttemptStatus.IN_PROGRESS,
        randomized_order=[],
        started_at=datetime.now(timezone.utc),
        deadline_at=datetime.now(timezone.utc) + timedelta(minutes=60),
        remaining_seconds=3600,
    )
    db.add(attempt)
    db.commit()

    payload = {
        "attempt_id": attempt.id,
        "proctor_assignment_id": sch.id,
        "exam_session_id": sess.id,
        "reason": "Membuka aplikasi terlarang",
    }

    # 1. Lock Student Endpoint -> Success
    res = client.post(
        "/api/v1/proctor/commands/lock",
        json=payload,
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert res.status_code == 200
    assert "berhasil dieksekusi" in res.json()["message"]

    # 2. Unlock Student Endpoint -> Success
    res = client.post(
        "/api/v1/proctor/commands/unlock",
        json=payload,
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert res.status_code == 200
    assert "berhasil dieksekusi" in res.json()["message"]

    # 3. Device Reset Endpoint -> Success
    res = client.post(
        "/api/v1/proctor/commands/device-reset",
        json=payload,
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert res.status_code == 200
    assert "berhasil dieksekusi" in res.json()["message"]
