from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.dependencies import get_current_user
from app.exceptions.base import BusinessException
from app.models.academic.academic_semester import AcademicSemester
from app.models.academic.academic_year import AcademicYear
from app.models.academic.class_entity import ClassEntity
from app.models.academic.enums import AcademicStatus, EnrollmentStatus, ExamScheduleStatus
from app.models.academic.student_class_enrollment import StudentClassEnrollment
from app.models.exam.enums import ExamAttemptStatus, ExamSessionStatus
from app.models.exam.exam_checkin import ExamCheckin
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
from main import app


def _setup_cbt_test_context(
    db, start_offset_minutes=15, duration_minutes=60, session_status=ExamSessionStatus.PLANNED
):
    level = db.scalar(select(SchoolLevel).limit(1))
    if not level:
        level = SchoolLevel(code="SMA", name="Sekolah Menengah Atas")
        db.add(level)
        db.flush()

    unique_code = f"SCH_{uuid4().hex[:8]}"
    school = School(
        name="SMAN 1 CBT Test",
        code=unique_code,
        domain=f"{unique_code.lower()}.sch.id",
        npsn=f"NPSN_{uuid4().hex[:6]}",
        school_level_id=level.id,
        address="Jl. Kiosk Lifecycle No. 1",
        is_active=True,
    )
    db.add(school)
    db.flush()

    now = datetime.now(timezone.utc)
    year = AcademicYear(
        school_id=school.id,
        name=f"2026/2027-{uuid4().hex[:4]}",
        start_date=now - timedelta(days=30),
        end_date=now + timedelta(days=335),
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
        name="Guru CBT",
        password_hash="fake_hash",
        role=UserRole.TEACHER.value,
        is_active=True,
    )
    db.add(teacher)
    db.flush()

    student = AuthAccount(
        school_id=school.id,
        username=f"student_{uuid4().hex[:8]}",
        name="Siswa CBT",
        password_hash="fake_hash",
        role=UserRole.STUDENT.value,
        is_active=True,
    )
    db.add(student)
    db.flush()

    subj = SubjectService.create_subject(
        db, school.id, code=f"SBJ_{uuid4().hex[:4]}", name="Biologi CBT"
    )
    SubjectService.assign_teacher_competency(db, school.id, teacher.id, subj.id)
    ClassStructureService.assign_teacher_to_class_subject(
        db, school_id=school.id, class_id=cls.id, subject_id=subj.id, teacher_id=teacher.id
    )

    enrollment = StudentClassEnrollment(
        school_id=school.id,
        academic_year_id=year.id,
        class_id=cls.id,
        student_id=student.id,
        status=EnrollmentStatus.ACTIVE.value,
        start_date=now - timedelta(days=10),
    )
    db.add(enrollment)
    db.flush()

    q_pg = Question(
        owner_teacher_account_id=teacher.id,
        type=QuestionType.PG.value,
        content="Apa fungsi mitokondria?",
        options=["Respirasi sel", "Fotosintesis", "Ekskresi", "Sintesis lipid"],
        answer_key="A",
        rubrics=[],
        subject=subj.name,
    )
    q_es = Question(
        owner_teacher_account_id=teacher.id,
        type=QuestionType.ES.value,
        content="Jelaskan proses siklus Krebs secara ringkas!",
        options=[],
        answer_key="",
        rubrics=[],
        subject=subj.name,
    )
    db.add_all([q_pg, q_es])
    db.flush()

    pkg = QuestionPackage(
        owner_teacher_account_id=teacher.id,
        school_id=school.id,
        name=f"Paket CBT {uuid4().hex[:4]}",
        class_level="XII",
        target_counts={"PG": 1, "ES": 1},
        subject=subj.name,
        status=PackageStatus.READY.value,
    )
    db.add(pkg)
    db.flush()

    item1 = QuestionPackageItem(
        package_id=pkg.id,
        question_id=q_pg.id,
        canonical_order=1,
        score=50.0,
    )
    item2 = QuestionPackageItem(
        package_id=pkg.id,
        question_id=q_es.id,
        canonical_order=2,
        score=50.0,
    )
    db.add_all([item1, item2])
    db.flush()

    start_time = now + timedelta(minutes=start_offset_minutes)
    end_time = start_time + timedelta(minutes=duration_minutes)

    schedule = ExamScheduleService.create_exam_schedule(
        db,
        school_id=school.id,
        academic_year_id=year.id,
        academic_semester_id=sem.id,
        class_id=cls.id,
        subject_id=subj.id,
        title="Ujian CBT Kiosk Lifecycle",
        start_time=start_time,
        end_time=end_time,
        duration_minutes=duration_minutes,
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
        duration_minutes=duration_minutes,
        status=session_status,
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
                "id": q_pg.id,
                "question_id": q_pg.id,
                "type": "PG",
                "content": q_pg.content,
                "options": q_pg.options,
                "answer_key": q_pg.answer_key,
                "max_score": 50.0,
            },
            {
                "id": q_es.id,
                "question_id": q_es.id,
                "type": "ES",
                "content": q_es.content,
                "options": [],
                "answer_key": "",
                "max_score": 50.0,
            },
        ],
    )
    db.add(snapshot)
    db.commit()

    return {
        "school": school,
        "class": cls,
        "teacher": teacher,
        "student": student,
        "subject": subj,
        "pkg": pkg,
        "schedule": schedule,
        "session": session,
        "snapshot": snapshot,
    }


def test_start_attempt_premature_strictly_rejected_400(db, client):
    """
    R3 Verification 1:
    When scheduled_start_at is in the future, start_attempt must strictly raise HTTP 400
    'Waktu pelaksanaan ujian belum tiba.' even if student has checked in and session is PLANNED.
    """
    ctx = _setup_cbt_test_context(
        db, start_offset_minutes=20, session_status=ExamSessionStatus.PLANNED
    )
    schedule = ctx["schedule"]
    session = ctx["session"]
    student = ctx["student"]

    # Student performs attendance checkin
    checkin = ExamCheckin(
        schedule_id=schedule.id,
        student_id=student.id,
        device_id="device-cbt-1",
        checked_in_at=datetime.now(timezone.utc),
    )
    db.add(checkin)
    db.commit()

    # 1. Direct service layer invocation
    with pytest.raises(BusinessException) as exc_info:
        ExamService.start_attempt(
            db,
            session_id=session.id,
            student_id=student.id,
            device_id="device-cbt-1",
            ip_address="127.0.0.1",
        )
    assert exc_info.value.status_code == 400
    assert "Waktu pelaksanaan ujian belum tiba." in str(exc_info.value)

    # Verify session was NOT promoted to ACTIVE
    db.refresh(session)
    assert session.status == ExamSessionStatus.PLANNED

    # 2. REST API endpoint invocation
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": str(student.id),
        "role": "STUDENT",
        "school_id": ctx["school"].id,
    }
    try:
        res = client.post(
            f"/api/v1/exam/sessions/{session.id}/start-attempt",
            headers={"X-Device-Id": "device-cbt-1"},
        )
        assert res.status_code == 400
        data = res.json()
        assert "Waktu pelaksanaan ujian belum tiba." in data.get("detail", "")
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_start_attempt_elimination_of_permissive_status_clause(db):
    """
    R3 Verification 2:
    Verifies that the permissive clause 'or str(session.status).upper() in ["PLANNED", "DRAFT", "READY", "SCHEDULED"]'
    is strictly eliminated. A session in PLANNED status cannot be started before scheduled_start_at.
    """
    ctx = _setup_cbt_test_context(
        db, start_offset_minutes=10, session_status=ExamSessionStatus.PLANNED
    )
    session = ctx["session"]
    student = ctx["student"]

    checkin = ExamCheckin(
        schedule_id=ctx["schedule"].id,
        student_id=student.id,
        device_id="device-test-clause",
        checked_in_at=datetime.now(timezone.utc),
    )
    db.add(checkin)
    db.commit()

    with pytest.raises(BusinessException) as exc_info:
        ExamService.start_attempt(
            db,
            session_id=session.id,
            student_id=student.id,
            device_id="device-test-clause",
            ip_address="127.0.0.1",
        )
    assert exc_info.value.status_code == 400
    assert "Waktu pelaksanaan ujian belum tiba." in str(exc_info.value)


def test_start_attempt_requires_prior_checkin(db):
    """
    R3 Verification 3:
    When window is open (now >= scheduled_start_at), start_attempt must fail
    if student has not completed attendance check-in.
    """
    ctx = _setup_cbt_test_context(
        db, start_offset_minutes=-5, session_status=ExamSessionStatus.PLANNED
    )
    session = ctx["session"]
    student = ctx["student"]

    with pytest.raises(BusinessException) as exc_info:
        ExamService.start_attempt(
            db,
            session_id=session.id,
            student_id=student.id,
            device_id="device-cbt-nocheckin",
            ip_address="127.0.0.1",
        )
    assert exc_info.value.status_code == 400
    assert "Anda belum melakukan absensi" in str(exc_info.value)


def test_start_attempt_authorized_open_window_success(db, client):
    """
    R3 Verification 4:
    When scheduled_start_at has arrived (now >= start_at) and student has checked in,
    start_attempt activates session and returns new attempt in IN_PROGRESS.
    """
    ctx = _setup_cbt_test_context(
        db, start_offset_minutes=-2, session_status=ExamSessionStatus.PLANNED
    )
    schedule = ctx["schedule"]
    session = ctx["session"]
    student = ctx["student"]

    checkin = ExamCheckin(
        schedule_id=schedule.id,
        student_id=student.id,
        device_id="device-authorized-1",
        checked_in_at=datetime.now(timezone.utc),
    )
    db.add(checkin)
    db.commit()

    # REST API invocation
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": str(student.id),
        "role": "STUDENT",
        "school_id": ctx["school"].id,
    }
    try:
        res = client.post(
            f"/api/v1/exam/sessions/{session.id}/start-attempt",
            headers={"X-Device-Id": "device-authorized-1"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == ExamAttemptStatus.IN_PROGRESS.value
        assert "device_session_token" in data
        assert len(data["questions"]) == 2

        db.refresh(session)
        assert session.status == ExamSessionStatus.ACTIVE
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_start_attempt_resume_and_device_session_binding(db):
    """
    R3 Verification 5:
    Resuming an IN_PROGRESS or PAUSED attempt correctly maintains device session.
    """
    ctx = _setup_cbt_test_context(
        db, start_offset_minutes=-10, session_status=ExamSessionStatus.ACTIVE
    )
    session = ctx["session"]
    student = ctx["student"]

    checkin = ExamCheckin(
        schedule_id=ctx["schedule"].id,
        student_id=student.id,
        device_id="device-resume-1",
        checked_in_at=datetime.now(timezone.utc),
    )
    db.add(checkin)
    db.commit()

    # First start: creates attempt
    attempt = ExamService.start_attempt(
        db,
        session_id=session.id,
        student_id=student.id,
        device_id="device-resume-1",
        ip_address="127.0.0.1",
    )
    assert attempt.status == ExamAttemptStatus.IN_PROGRESS
    token1 = attempt.device_session_token

    # Second start on same active device: resumes and returns active token
    attempt_resumed = ExamService.start_attempt(
        db,
        session_id=session.id,
        student_id=student.id,
        device_id="device-resume-1",
        ip_address="127.0.0.1",
    )
    assert attempt_resumed.id == attempt.id
    assert attempt_resumed.device_session_token == token1

    # Pause attempt and simulate device reset resume
    attempt.status = ExamAttemptStatus.PAUSED
    attempt.remaining_seconds = 1800
    db.commit()

    attempt_reset = ExamService.start_attempt(
        db,
        session_id=session.id,
        student_id=student.id,
        device_id="device-resume-2",
        ip_address="127.0.0.1",
    )
    assert attempt_reset.id == attempt.id
    assert attempt_reset.status == ExamAttemptStatus.IN_PROGRESS
    assert attempt_reset.remaining_seconds is None
    assert attempt_reset.device_session_token != token1
