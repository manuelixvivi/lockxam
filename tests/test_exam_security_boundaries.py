import hashlib
import hmac
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.dependencies import get_current_user
from app.core.security.keys import SECRET_KEY
from app.exceptions.base import BusinessException
from app.models.academic.academic_semester import AcademicSemester
from app.models.academic.academic_year import AcademicYear
from app.models.academic.class_entity import ClassEntity
from app.models.academic.enums import AcademicStatus, EnrollmentStatus, ExamScheduleStatus
from app.models.academic.student_class_enrollment import StudentClassEnrollment
from app.models.exam.device_session import DeviceSession, DeviceSessionStatus
from app.models.exam.enums import ExamAttemptStatus, ExamSessionStatus
from app.models.exam.exam_attempt import ExamAttempt
from app.models.exam.exam_session import ExamSession
from app.models.exam.package_snapshot import ExamPackageSnapshot
from app.models.master.school_level import SchoolLevel
from app.models.school.school import School
from app.models.security.auth_account import AuthAccount
from app.models.security.enums import UserRole
from app.models.teacher.enums import PackageStatus, QuestionType
from app.models.teacher.package_item import QuestionPackageItem
from app.models.teacher.question import Question
from app.models.teacher.question_package import QuestionPackage
from app.services.academic.class_structure_service import ClassStructureService
from app.services.academic.exam_schedule_service import ExamScheduleService
from app.services.academic.exam_snapshot_service import ExamSnapshotService
from app.services.academic.subject_service import SubjectService
from app.services.exam.exam_service import ExamService
from app.services.teacher.proctor_service import ProctorService
from main import app


def _create_school_hierarchy(db, school_name="SMAN 1 Boundary"):
    level = db.scalar(select(SchoolLevel).limit(1))
    if not level:
        level = SchoolLevel(code="SMA", name="Sekolah Menengah Atas")
        db.add(level)
        db.flush()

    unique_code = f"SCH_{uuid4().hex[:8]}"
    school = School(
        name=school_name,
        code=unique_code,
        domain=f"{unique_code.lower()}.sch.id",
        npsn=f"NPSN_{uuid4().hex[:6]}",
        school_level_id=level.id,
        address="Jl. Pendidikan Boundary No. 1",
        is_active=True,
    )
    db.add(school)
    db.flush()

    now = datetime.now(timezone.utc)
    year = AcademicYear(
        school_id=school.id,
        name=f"2026/2027-{uuid4().hex[:4]}",
        start_date=now,
        end_date=now + timedelta(days=365),
        status=AcademicStatus.ACTIVE.value,
    )
    db.add(year)
    db.flush()

    sem = AcademicSemester(
        academic_year_id=year.id,
        code=f"GANJIL_{uuid4().hex[:4]}",
        display_name="Semester Ganjil",
        status=AcademicStatus.ACTIVE.value,
    )
    db.add(sem)
    db.flush()

    cls = ClassEntity(
        school_id=school.id,
        academic_year_id=year.id,
        name=f"XII-IPA-{uuid4().hex[:4]}",
        grade_level="12",
        is_active=True,
    )
    db.add(cls)
    db.flush()

    teacher = AuthAccount(
        school_id=school.id,
        username=f"teacher_{uuid4().hex[:8]}",
        name="Guru Boundary",
        password_hash="fake_hash",
        role=UserRole.TEACHER.value,
        is_active=True,
    )
    db.add(teacher)
    db.flush()

    student1 = AuthAccount(
        school_id=school.id,
        username=f"student1_{uuid4().hex[:8]}",
        name="Siswa Boundary 1",
        password_hash="fake_hash",
        role=UserRole.STUDENT.value,
        is_active=True,
    )
    student2 = AuthAccount(
        school_id=school.id,
        username=f"student2_{uuid4().hex[:8]}",
        name="Siswa Boundary 2",
        password_hash="fake_hash",
        role=UserRole.STUDENT.value,
        is_active=True,
    )
    db.add_all([student1, student2])
    db.flush()

    subj = SubjectService.create_subject(
        db, school.id, code=f"SBJ_{uuid4().hex[:4]}", name="Fisika Boundary"
    )
    SubjectService.assign_teacher_competency(db, school.id, teacher.id, subj.id)
    ClassStructureService.assign_teacher_to_class_subject(
        db, school_id=school.id, class_id=cls.id, subject_id=subj.id, teacher_id=teacher.id
    )

    enrollment1 = StudentClassEnrollment(
        school_id=school.id,
        academic_year_id=year.id,
        class_id=cls.id,
        student_id=student1.id,
        status=EnrollmentStatus.ACTIVE.value,
        start_date=now,
    )
    db.add(enrollment1)
    db.flush()

    # Question & Package
    q = Question(
        owner_teacher_account_id=teacher.id,
        type=QuestionType.PG.value,
        content="Berapa hasil 5 + 5?",
        options=["8", "10", "12", "14"],
        answer_key="B",
        rubrics=[],
        subject=subj.name,
    )
    db.add(q)
    db.flush()

    pkg = QuestionPackage(
        owner_teacher_account_id=teacher.id,
        school_id=school.id,
        name=f"Paket Test {uuid4().hex[:4]}",
        class_level="XII",
        target_counts={"PG": 1},
        subject=subj.name,
        status=PackageStatus.READY.value,
    )
    db.add(pkg)
    db.flush()

    item = QuestionPackageItem(
        package_id=pkg.id,
        question_id=q.id,
        canonical_order=1,
        score=100.0,
    )
    db.add(item)
    db.flush()

    schedule = ExamScheduleService.create_exam_schedule(
        db,
        school_id=school.id,
        academic_year_id=year.id,
        academic_semester_id=sem.id,
        class_id=cls.id,
        subject_id=subj.id,
        title="Ujian Boundary Security",
        start_time=now - timedelta(minutes=10),
        end_time=now + timedelta(hours=2),
        duration_minutes=60,
        proctor_id=teacher.id,
    )
    schedule.teacher_id = teacher.id
    schedule.proctor_id = teacher.id
    db.flush()

    ExamSnapshotService.create_immutable_snapshot(
        db,
        school_id=school.id,
        teacher_id=teacher.id,
        schedule_public_id=schedule.public_id,
        package_public_id=pkg.public_id,
    )
    schedule.status = ExamScheduleStatus.READY.value
    db.flush()

    session = ExamSession(
        schedule_id=schedule.id,
        package_id=pkg.id,
        scheduled_start_at=schedule.start_time,
        scheduled_end_at=schedule.end_time,
        duration_minutes=60,
        status=ExamSessionStatus.ACTIVE,
    )
    db.add(session)
    db.flush()

    snapshot = ExamPackageSnapshot(
        exam_session_id=session.id,
        source_package_id=pkg.id,
        school_id=school.id,
        owner_teacher_account_id=teacher.id,
        snapshot_version=1,
        questions_json=[
            {
                "id": q.id,
                "question_id": q.id,
                "type": "PG",
                "content": q.content,
                "options": q.options,
                "answer_key": q.answer_key,
                "max_score": 100.0,
            }
        ],
    )
    db.add(snapshot)
    db.commit()

    return {
        "school": school,
        "year": year,
        "semester": sem,
        "class": cls,
        "teacher": teacher,
        "student1": student1,
        "student2": student2,
        "subject": subj,
        "question": q,
        "package": pkg,
        "schedule": schedule,
        "session": session,
        "snapshot": snapshot,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Boundary 1: Submit Attempt Ownership Binding
# ─────────────────────────────────────────────────────────────────────────────
def test_submit_attempt_ownership_enforcement(db, client):
    ctx = _create_school_hierarchy(db)
    session = ctx["session"]
    student1 = ctx["student1"]
    student2 = ctx["student2"]

    attempt = ExamAttempt(
        exam_session_id=session.id,
        student_id=student1.id,
        status=ExamAttemptStatus.IN_PROGRESS,
        randomized_order=[ctx["question"].id],
        deadline_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )
    db.add(attempt)
    db.commit()

    # 1. Service Layer rejection: student2 tries to submit student1's attempt
    with pytest.raises(BusinessException) as exc_info:
        ExamService.submit_attempt(db, attempt.id, student_id=student2.id)
    assert exc_info.value.status_code == 403
    assert "Akses ditolak: Anda bukan pemilik attempt ini" in str(exc_info.value)

    # 2. API Layer rejection: student2 attempts to submit via endpoint
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": str(student2.id),
        "role": "STUDENT",
        "school_id": ctx["school"].id,
    }
    try:
        res = client.post(f"/api/v1/exam/attempts/{attempt.id}/submit")
        assert res.status_code == 403
        assert "Akses ditolak" in res.json().get("detail", "")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    # 3. Valid submission by legitimate owner (student1)
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": str(student1.id),
        "role": "STUDENT",
        "school_id": ctx["school"].id,
    }
    try:
        res = client.post(f"/api/v1/exam/attempts/{attempt.id}/submit")
        assert res.status_code == 200
        assert res.json()["status"] in (
            ExamAttemptStatus.SUBMITTED.value,
            ExamAttemptStatus.GRADED.value,
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ─────────────────────────────────────────────────────────────────────────────
# Boundary 2: Authoritative Student Exam Eligibility Helper
# ─────────────────────────────────────────────────────────────────────────────
def test_eligibility_helper_cross_tenant_and_class_guards(db):
    ctx = _create_school_hierarchy(db)
    schedule = ctx["schedule"]
    student1 = ctx["student1"]
    student2 = ctx["student2"]

    # 1. Cross-tenant student rejection
    other_school = _create_school_hierarchy(db, school_name="SMAN 2 Outside")
    outside_student = other_school["student1"]
    with pytest.raises(BusinessException) as exc_tenant:
        ExamService.validate_student_exam_eligibility(db, schedule, outside_student.id)
    assert exc_tenant.value.status_code == 403
    assert "tidak terdaftar pada sekolah penyelenggara" in str(exc_tenant.value)

    # 2. Student in same school but not enrolled in schedule.class_id
    with pytest.raises(BusinessException) as exc_class:
        ExamService.validate_student_exam_eligibility(db, schedule, student2.id)
    assert exc_class.value.status_code == 403
    assert "tidak terdaftar aktif di kelas jadwal ujian ini" in str(exc_class.value)

    # 3. Enrolled student succeeds
    valid_sched = ExamService.validate_student_exam_eligibility(db, schedule, student1.id)
    assert valid_sched.id == schedule.id


def test_eligibility_helper_selected_target_type(db):
    ctx = _create_school_hierarchy(db)
    schedule = ctx["schedule"]
    student1 = ctx["student1"]
    student2 = ctx["student2"]

    # Enroll student2 into the class as well
    enrollment2 = StudentClassEnrollment(
        school_id=ctx["school"].id,
        academic_year_id=ctx["year"].id,
        class_id=ctx["class"].id,
        student_id=student2.id,
        status=EnrollmentStatus.ACTIVE.value,
        start_date=datetime.now(timezone.utc),
    )
    db.add(enrollment2)
    db.commit()

    # Set schedule target_type = SELECTED with only student1 allowed
    schedule.target_type = "SELECTED"
    schedule.allowed_student_ids = [student1.id]
    db.commit()

    # student2 is in class, but not in allowed_student_ids -> 403
    with pytest.raises(BusinessException) as exc_sel:
        ExamService.validate_student_exam_eligibility(db, schedule, student2.id)
    assert exc_sel.value.status_code == 403
    assert "tidak terdaftar dalam daftar peserta yang diizinkan" in str(exc_sel.value)

    # student1 is allowed -> succeeds
    valid_sched = ExamService.validate_student_exam_eligibility(db, schedule, student1.id)
    assert valid_sched.id == schedule.id


# ─────────────────────────────────────────────────────────────────────────────
# Boundary 3: Check-in + Start Attempt Authorization Enforcement
# ─────────────────────────────────────────────────────────────────────────────
def test_checkin_and_start_attempt_enforce_eligibility(db, client):
    ctx = _create_school_hierarchy(db)
    schedule = ctx["schedule"]
    session = ctx["session"]
    student2 = ctx["student2"]  # student2 not enrolled in class

    # Generate signed QR check-in token
    expires_ts = int(time.time()) + 180
    payload_str = f"{schedule.id}:{expires_ts}"
    sig = hmac.new(SECRET_KEY.encode(), payload_str.encode(), hashlib.sha256).hexdigest()[:16]
    token = f"{schedule.id}:{expires_ts}:{sig}"

    # Student 2 attempts QR check-in -> 403
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": str(student2.id),
        "role": "STUDENT",
        "school_id": ctx["school"].id,
    }
    try:
        qr_res = client.post(
            f"/api/v1/exam/checkin?token={token}&expected_schedule_id={schedule.id}",
            headers={"X-Device-Id": "device-student-2"},
        )
        assert qr_res.status_code == 403
        assert "tidak terdaftar aktif di kelas" in qr_res.json().get("detail", "")

        # Student 2 attempts start-attempt -> 403
        start_res = client.post(
            f"/api/v1/exam/sessions/{session.id}/start-attempt",
            headers={"X-Device-Id": "device-student-2"},
        )
        assert start_res.status_code == 403
        assert "tidak terdaftar aktif di kelas" in start_res.json().get("detail", "")
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ─────────────────────────────────────────────────────────────────────────────
# Boundary 4: Strict Timer Expiration (No Auto-Extension)
# ─────────────────────────────────────────────────────────────────────────────
def test_autosave_strict_timer_expiration(db):
    ctx = _create_school_hierarchy(db)
    session = ctx["session"]
    student1 = ctx["student1"]

    # Create attempt with expired deadline
    expired_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    attempt = ExamAttempt(
        exam_session_id=session.id,
        student_id=student1.id,
        status=ExamAttemptStatus.IN_PROGRESS,
        randomized_order=[ctx["question"].id],
        deadline_at=expired_time,
    )
    db.add(attempt)
    db.commit()

    device = DeviceSession(
        exam_attempt_id=attempt.id,
        device_id="dev_timer_test",
        session_token="token_timer_123",
        ip_address="127.0.0.1",
        status=DeviceSessionStatus.ACTIVE,
        last_active_at=datetime.now(timezone.utc),
    )
    db.add(device)
    db.commit()

    # Autosave after deadline MUST trigger auto-submit and reject with 400
    with pytest.raises(BusinessException) as exc_timer:
        ExamService.autosave_answer(
            db=db,
            attempt_id=attempt.id,
            question_id=ctx["question"].id,
            selected_option="A",
            text_answer=None,
            student_id=student1.id,
            token="token_timer_123",
        )
    assert exc_timer.value.status_code == 400
    assert "Waktu ujian telah berakhir" in str(exc_timer.value)

    # Verify attempt is now automatically submitted, NOT extended
    db.expire_all()
    refreshed_attempt = db.query(ExamAttempt).filter_by(id=attempt.id).first()
    assert refreshed_attempt.status in (ExamAttemptStatus.SUBMITTED, ExamAttemptStatus.GRADED)
    assert refreshed_attempt.deadline_at == expired_time


# ─────────────────────────────────────────────────────────────────────────────
# Boundary 5: Device Session Token Lifecycle & Tamper Rejection
# ─────────────────────────────────────────────────────────────────────────────
def test_device_token_lifecycle_and_validation(db, client):
    ctx = _create_school_hierarchy(db)
    session = ctx["session"]
    student1 = ctx["student1"]

    # Pre-checkin required before starting attempt
    from app.models.exam.exam_checkin import ExamCheckin

    checkin = ExamCheckin(
        schedule_id=ctx["schedule"].id,
        student_id=student1.id,
        device_id="device_safe_1",
        checked_in_at=datetime.now(timezone.utc),
    )
    db.add(checkin)
    db.commit()

    # 1. Start attempt returns device_session_token
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": str(student1.id),
        "role": "STUDENT",
        "school_id": ctx["school"].id,
    }
    try:
        start_res = client.post(
            f"/api/v1/exam/sessions/{session.id}/start-attempt",
            headers={"X-Device-Id": "device_safe_1"},
        )
        assert start_res.status_code == 200
        data = start_res.json()
        token = data.get("device_session_token")
        assert token is not None and len(token) > 10
        attempt_id = data["id"]

        # 2. Autosave with invalid token -> 403
        save_bad_res = client.post(
            f"/api/v1/exam/attempts/{attempt_id}/autosave",
            json={"question_id": ctx["question"].id, "selected_option": "B"},
            headers={"X-Device-Token": "spoofed_invalid_token"},
        )
        assert save_bad_res.status_code == 403
        assert "Token perangkat tidak valid" in save_bad_res.json().get("detail", "")

        # 3. Autosave with missing token -> 401 or 403
        save_missing_res = client.post(
            f"/api/v1/exam/attempts/{attempt_id}/autosave",
            json={"question_id": ctx["question"].id, "selected_option": "B"},
        )
        assert save_missing_res.status_code in (401, 403)

        # 4. Autosave with valid token -> 200
        save_good_res = client.post(
            f"/api/v1/exam/attempts/{attempt_id}/autosave",
            json={"question_id": ctx["question"].id, "selected_option": "B"},
            headers={"X-Device-Token": token},
        )
        assert save_good_res.status_code == 200
        assert save_good_res.json()["selected_option"] == "B"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ─────────────────────────────────────────────────────────────────────────────
# Boundary 6: Proctor Session Authorization & Broadcast Isolation
# ─────────────────────────────────────────────────────────────────────────────
def test_proctor_authorization_and_broadcast_isolation(db, client):
    ctx = _create_school_hierarchy(db)
    session = ctx["session"]
    assigned_proctor = ctx["teacher"]

    # Create an unassigned teacher
    unassigned_teacher = AuthAccount(
        school_id=ctx["school"].id,
        username=f"rogue_teacher_{uuid4().hex[:8]}",
        name="Guru Tidak Ditugaskan",
        password_hash="fake_hash",
        role=UserRole.TEACHER.value,
        is_active=True,
    )
    db.add(unassigned_teacher)
    db.flush()

    # 1. Service Layer rejection for unassigned proctor
    with pytest.raises(BusinessException) as exc_p:
        ProctorService.validate_proctor_session_authorization(
            db=db,
            exam_session_id=session.id,
            user_id=unassigned_teacher.id,
            user_role="TEACHER",
        )
    assert exc_p.value.status_code == 403
    assert "bukan pengawas yang ditugaskan" in str(exc_p.value)

    # 2. API Layer rejection on broadcast for unassigned teacher
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": str(unassigned_teacher.id),
        "role": "TEACHER",
        "school_id": ctx["school"].id,
    }
    try:
        bcast_rogue = client.post(
            "/api/v1/proctor/commands/broadcast",
            json={"exam_session_id": session.id, "message": "Palsu!", "extra_minutes": 0},
        )
        assert bcast_rogue.status_code == 403
        assert "bukan pengawas yang ditugaskan" in bcast_rogue.json().get("detail", "")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    # 3. Assigned proctor succeeds
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": str(assigned_proctor.id),
        "role": "TEACHER",
        "school_id": ctx["school"].id,
    }
    try:
        bcast_ok = client.post(
            "/api/v1/proctor/commands/broadcast",
            json={"exam_session_id": session.id, "message": "Harap tenang.", "extra_minutes": 0},
        )
        assert bcast_ok.status_code == 200
        assert bcast_ok.json().get("status") == "SUCCESS" or bcast_ok.json().get("success") is True
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ─────────────────────────────────────────────────────────────────────────────
# Boundary 7: AI Endpoints RBAC Lockdown
# ─────────────────────────────────────────────────────────────────────────────
def test_ai_endpoints_rbac_lockdown(client):
    ai_endpoints = [
        ("POST", "/api/v1/ai/rubric/generate", {"question": "q", "subject": "s"}),
        ("POST", "/api/v1/ai/rubric/validate", {"question": "q", "answer_key": "k"}),
        ("POST", "/api/v1/ai/grading/evaluate", {"question": "q", "student_answer": "a"}),
        ("POST", "/api/v1/ai/grading/batch-question", {"question_id": 1, "submissions": []}),
        ("POST", "/api/v1/ai/grading/post-exam/start", {"exam_schedule_id": 1}),
    ]

    # 1. Unauthenticated requests MUST return 401
    for _method, path, payload in ai_endpoints:
        res = client.post(path, json=payload)
        assert (
            res.status_code == 401
        ), f"Expected 401 for unauthenticated {path}, got {res.status_code}"

    # 2. Student role requests MUST return 403 Forbidden
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "999",
        "role": "STUDENT",
        "school_id": 1,
    }
    try:
        for _method, path, payload in ai_endpoints:
            res = client.post(path, json=payload)
            assert res.status_code == 403, f"Expected 403 for student {path}, got {res.status_code}"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ─────────────────────────────────────────────────────────────────────────────
# Boundary 9: Strict Proctor Separation (Teacher Pengampu != Proctor Authority)
# ─────────────────────────────────────────────────────────────────────────────
def test_teacher_pengampu_cannot_proctor_unless_assigned(db, client):
    """Memastikan bahwa guru pengampu/pembuat jadwal (teacher_id) TIDAK memiliki
    otoritas proctor/broadcast jika schedule.proctor_id ditugaskan ke guru lain."""
    ctx = _create_school_hierarchy(db)
    session = ctx["session"]
    schedule = ctx["schedule"]

    teacher_pengampu = ctx["teacher"]

    # Buat guru proctor resmi yang ditugaskan ke jadwal
    assigned_proctor = AuthAccount(
        school_id=ctx["school"].id,
        username=f"real_proctor_{uuid4().hex[:8]}",
        name="Pengawas Resmi",
        password_hash="fake_hash",
        role=UserRole.TEACHER.value,
        is_active=True,
    )
    db.add(assigned_proctor)
    db.flush()

    schedule.teacher_id = teacher_pengampu.id
    schedule.proctor_id = assigned_proctor.id
    db.commit()

    # 1. Guru Pengampu (bukan proctor_id) mencoba validasi -> MUST 403
    with pytest.raises(BusinessException) as exc_info:
        ProctorService.validate_proctor_session_authorization(
            db=db,
            exam_session_id=session.id,
            user_id=teacher_pengampu.id,
            user_role="TEACHER",
        )
    assert exc_info.value.status_code == 403
    assert "bukan pengawas yang ditugaskan" in str(exc_info.value)

    # 2. Guru Pengampu mencoba broadcast via API -> MUST 403
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": str(teacher_pengampu.id),
        "role": "TEACHER",
        "school_id": ctx["school"].id,
    }
    try:
        res = client.post(
            "/api/v1/proctor/commands/broadcast",
            json={"exam_session_id": session.id, "message": "Pesan ilegal", "extra_minutes": 0},
        )
        assert res.status_code == 403
        assert "bukan pengawas yang ditugaskan" in res.json().get("detail", "")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    # 3. Pengawas Resmi yang ditugaskan (assigned_proctor) -> MUST 200 OK
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": str(assigned_proctor.id),
        "role": "TEACHER",
        "school_id": ctx["school"].id,
    }
    try:
        res = client.post(
            "/api/v1/proctor/commands/broadcast",
            json={"exam_session_id": session.id, "message": "Pesan resmi", "extra_minutes": 0},
        )
        assert res.status_code == 200
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ─────────────────────────────────────────────────────────────────────────────
# Boundary 10: Strict JWT 'kid' Rejection
# ─────────────────────────────────────────────────────────────────────────────
def test_jwt_unknown_and_missing_kid_rejected():
    """Memastikan token JWT dengan 'kid' tidak dikenal atau hilang langsung ditolak."""
    from jose import jwt

    from app.core.security.jwt import verify_token
    from app.core.security.keys import ALGORITHM, SECRET_KEY

    payload = {"sub": "123", "role": "STUDENT", "exp": int(time.time()) + 3600}

    # 1. Valid token dengan active Key ID ('v1') -> PASS
    valid_token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM, headers={"kid": "v1"})
    assert verify_token(valid_token) is not None

    # 2. Token dengan forged/unknown kid -> MUST BE REJECTED (None)
    forged_kid_token = jwt.encode(
        payload, SECRET_KEY, algorithm=ALGORITHM, headers={"kid": "unknown_forged_key"}
    )
    assert verify_token(forged_kid_token) is None

    # 3. Token tanpa kid header -> MUST BE REJECTED (None)
    no_kid_token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    assert verify_token(no_kid_token) is None


# ─────────────────────────────────────────────────────────────────────────────
# Boundary 11: Extra Time Attempt-Level Audit Trail
# ─────────────────────────────────────────────────────────────────────────────
def test_extra_time_audit_trail_logging(db, client):
    """Memastikan penambahan waktu ujian mencatat old_deadline dan new_deadline per attempt."""
    from app.models.teacher.proctor_event import ProctorAuditEvent

    ctx = _create_school_hierarchy(db)
    session = ctx["session"]
    proctor = ctx["teacher"]
    student = ctx["student1"]

    now = datetime.now(timezone.utc)
    initial_deadline = now + timedelta(minutes=45)

    attempt = ExamAttempt(
        exam_session_id=session.id,
        student_id=student.id,
        status=ExamAttemptStatus.IN_PROGRESS,
        randomized_order=[ctx["question"].id],
        deadline_at=initial_deadline,
        remaining_seconds=2700,
    )
    db.add(attempt)
    db.commit()

    app.dependency_overrides[get_current_user] = lambda: {
        "sub": str(proctor.id),
        "role": "TEACHER",
        "school_id": ctx["school"].id,
    }
    try:
        res = client.post(
            "/api/v1/proctor/commands/broadcast",
            json={
                "exam_session_id": session.id,
                "message": "Tambahan waktu listrik padam",
                "extra_minutes": 15,
            },
        )
        assert res.status_code == 200

        # Verifikasi event audit per attempt di database
        audit_events = (
            db.query(ProctorAuditEvent)
            .filter(
                ProctorAuditEvent.proctor_assignment_id == session.id,
                ProctorAuditEvent.student_id == student.id,
                ProctorAuditEvent.event_type == "EXTRA_TIME",
            )
            .all()
        )
        assert len(audit_events) >= 1
        ev = audit_events[0]
        assert ev.action_taken == "EXTRA_TIME_ADDED"
        assert f"Attempt ID: {attempt.id}" in ev.reason
        assert "Old Deadline:" in ev.reason
        assert "New Deadline:" in ev.reason
        assert "Tambahan waktu listrik padam" in ev.reason
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ─────────────────────────────────────────────────────────────────────────────
# Boundary 12: Serverless Cross-Instance PIN & Telemetry Persistence
# ─────────────────────────────────────────────────────────────────────────────
def test_serverless_cross_instance_pin_and_telemetry_persistence(db, client):
    """Memastikan PIN dan Telemetry tersimpan di database sehingga tidak split-brain
    saat request masuk ke instance serverless yang berbeda."""
    from app.api.exam import ACTIVE_PIN_CACHE, TELEMETRY_STORE
    from app.models.exam.attempt_telemetry import AttemptTelemetry
    from app.models.exam.exam_checkin_pin import ExamCheckinPin

    ctx = _create_school_hierarchy(db)
    schedule = ctx["schedule"]
    teacher = ctx["teacher"]
    student = ctx["student1"]
    session = ctx["session"]

    # 1. Guru generate QR/PIN di Instance A
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": str(teacher.id),
        "role": "TEACHER",
        "school_id": ctx["school"].id,
    }
    try:
        qr_res = client.get(f"/api/v1/exam/schedules/{schedule.id}/qr-token")
        assert qr_res.status_code == 200
        pin_code = qr_res.json()["pin_code"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    # Verifikasi tersimpan di tabel exam_checkin_pins
    db_pin = db.query(ExamCheckinPin).filter(ExamCheckinPin.pin_code == pin_code).first()
    assert db_pin is not None

    # Simulasikan Instance B: Bersihkan in-memory cache total
    ACTIVE_PIN_CACHE.clear()
    assert pin_code not in ACTIVE_PIN_CACHE

    # Siswa check-in menggunakan PIN di Instance B -> DB fallback MUST SUCCEED
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": str(student.id),
        "role": "STUDENT",
        "school_id": ctx["school"].id,
    }
    try:
        checkin_res = client.post(
            f"/api/v1/exam/checkin?token={pin_code}&expected_schedule_id={schedule.id}",
            headers={"X-Device-Id": "device_srvless_1"},
        )
        assert checkin_res.status_code == 200
        assert (
            checkin_res.json().get("success") is True
            or checkin_res.json().get("status") == "SUCCESS"
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    # 2. Siswa mengirim Telemetry di Instance A
    attempt = ExamAttempt(
        exam_session_id=session.id,
        student_id=student.id,
        status=ExamAttemptStatus.IN_PROGRESS,
        randomized_order=[ctx["question"].id],
        deadline_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )
    db.add(attempt)
    db.commit()

    app.dependency_overrides[get_current_user] = lambda: {
        "sub": str(student.id),
        "role": "STUDENT",
        "school_id": ctx["school"].id,
    }
    try:
        telem_res = client.post(
            f"/api/v1/exam/attempts/{attempt.id}/telemetry",
            json={
                "battery_level": 15,
                "is_charging": False,
                "ping_ms": 42,
                "is_offline": False,
                "violation_type": None,
            },
        )
        assert telem_res.status_code == 200
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    # Verifikasi tersimpan di tabel attempt_telemetry
    db_telem = db.query(AttemptTelemetry).filter(AttemptTelemetry.attempt_id == attempt.id).first()
    assert db_telem is not None
    assert db_telem.battery_level == 15

    # Simulasikan Instance B: Bersihkan in-memory TELEMETRY_STORE total
    TELEMETRY_STORE.clear()
    assert attempt.id not in TELEMETRY_STORE

    # Pengawas membaca monitoring di Instance B -> DB fallback MUST SUCCEED
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": str(teacher.id),
        "role": "TEACHER",
        "school_id": ctx["school"].id,
    }
    try:
        mon_res = client.get(f"/api/v1/teacher/sessions/{session.id}/attempts")
        assert mon_res.status_code == 200
        data = mon_res.json()
        student_cards = [c for c in data if c.get("student_id") == student.id]
        assert len(student_cards) == 1
        card = student_cards[0]
        assert card["battery_level"] == 15
        assert card["ping_ms"] == 42
        assert card["monitoring_card_state"] == "YELLOW"  # battery <= 20%
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ─────────────────────────────────────────────────────────────────────────────
# Boundary 13: QR Token Generation Requester Authorization & Existence
# ─────────────────────────────────────────────────────────────────────────────
def test_qr_token_existence_and_requester_authorization(db, client):
    """Memastikan QR check-in token hanya bisa dibuat untuk schedule yang ada,
    dan hanya oleh pengawas yang ditugaskan, guru pengampu, atau admin sekolah."""
    ctx = _create_school_hierarchy(db)
    schedule = ctx["schedule"]
    assigned_proctor = ctx["teacher"]

    # 1. Nonexistent schedule_id -> MUST return 404
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": str(assigned_proctor.id),
        "role": "TEACHER",
        "school_id": ctx["school"].id,
    }
    try:
        res_404 = client.get("/api/v1/exam/schedules/99999999/qr-token")
        assert res_404.status_code == 404
        assert "tidak ditemukan" in res_404.json().get("detail", "")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    # 2. Guru dari sekolah lain -> MUST return 403
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "888888",
        "role": "TEACHER",
        "school_id": ctx["school"].id + 999,
    }
    try:
        res_cross = client.get(f"/api/v1/exam/schedules/{schedule.id}/qr-token")
        assert res_cross.status_code == 403
        assert "bukan milik sekolah Anda" in res_cross.json().get("detail", "")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    # 3. Guru yang tidak berwenang pada sekolah yang sama -> MUST return 403
    unrelated_teacher = AuthAccount(
        school_id=ctx["school"].id,
        username=f"unrelated_{uuid4().hex[:8]}",
        name="Guru Tanpa Penugasan",
        password_hash="fake",
        role=UserRole.TEACHER.value,
        is_active=True,
    )
    db.add(unrelated_teacher)
    db.flush()

    app.dependency_overrides[get_current_user] = lambda: {
        "sub": str(unrelated_teacher.id),
        "role": "TEACHER",
        "school_id": ctx["school"].id,
    }
    try:
        res_unauth = client.get(f"/api/v1/exam/schedules/{schedule.id}/qr-token")
        assert res_unauth.status_code == 403
        assert "Akses ditolak" in res_unauth.json().get("detail", "")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    # 4. Pengawas atau guru pengampu yang berwenang -> MUST return 200
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": str(assigned_proctor.id),
        "role": "TEACHER",
        "school_id": ctx["school"].id,
    }
    try:
        res_ok = client.get(f"/api/v1/exam/schedules/{schedule.id}/qr-token")
        assert res_ok.status_code == 200
        assert "qr_token" in res_ok.json()
        assert "pin_code" in res_ok.json()
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ─────────────────────────────────────────────────────────────────────────────
# Boundary 14: AI Resource Authorization (Object-Level Authorization)
# ─────────────────────────────────────────────────────────────────────────────
def test_ai_resource_authorization_boundary(db, client):
    """Memastikan endpoint AI memvalidasi eksistensi dan kepemilikan jadwal ujian
    serta menolak cross-school dan unauthorized teacher."""
    ctx = _create_school_hierarchy(db)
    schedule = ctx["schedule"]
    teacher = ctx["teacher"]

    # 1. Nonexistent schedule_id -> MUST return 404
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": str(teacher.id),
        "role": "TEACHER",
        "school_id": ctx["school"].id,
    }
    try:
        res_404 = client.post(
            "/api/v1/ai/grading/post-exam/start",
            json={"exam_schedule_id": 99999999},
        )
        assert res_404.status_code == 404
        assert "tidak ditemukan" in res_404.json().get("detail", "")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    # 2. Guru dari sekolah lain -> MUST return 403
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "77777",
        "role": "TEACHER",
        "school_id": ctx["school"].id + 888,
    }
    try:
        res_cross = client.post(
            "/api/v1/ai/grading/post-exam/start",
            json={"exam_schedule_id": schedule.id},
        )
        assert res_cross.status_code == 403
        assert "bukan milik sekolah Anda" in res_cross.json().get("detail", "")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    # 3. Guru di sekolah yang sama tetapi bukan pengampu/pengawas -> MUST return 403
    unrelated_teacher = AuthAccount(
        school_id=ctx["school"].id,
        username=f"ai_unrelated_{uuid4().hex[:8]}",
        name="Guru Lain",
        password_hash="fake",
        role=UserRole.TEACHER.value,
        is_active=True,
    )
    db.add(unrelated_teacher)
    db.flush()

    app.dependency_overrides[get_current_user] = lambda: {
        "sub": str(unrelated_teacher.id),
        "role": "TEACHER",
        "school_id": ctx["school"].id,
    }
    try:
        res_unauth = client.post(
            "/api/v1/ai/grading/post-exam/start",
            json={"exam_schedule_id": schedule.id},
        )
        assert res_unauth.status_code == 403
        assert "bukan guru pengampu atau pengawas" in res_unauth.json().get("detail", "")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
