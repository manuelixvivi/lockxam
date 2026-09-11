import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

# Ensure workspace root is in sys.path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app.core.security import hash_password
from app.models.academic.academic_semester import AcademicSemester
from app.models.academic.academic_year import AcademicYear
from app.models.academic.class_entity import ClassEntity
from app.models.academic.enums import AcademicStatus
from app.models.academic.exam_schedule import ExamSchedule
from app.models.academic.student_class_enrollment import StudentClassEnrollment
from app.models.exam.enums import ExamSessionStatus
from app.models.exam.exam_session import ExamSession
from app.models.master.school_level import SchoolLevel
from app.models.school.school import School
from app.models.security.auth_account import AuthAccount
from app.models.security.enums import UserRole
from app.models.teacher.enums import PackageStatus, QuestionType
from app.models.teacher.package_item import QuestionPackageItem
from app.models.teacher.question import Question
from app.models.teacher.question_package import QuestionPackage
from main import app


@pytest.fixture
def test_student(db, test_school):
    """Creates a standard student auth account and class enrollment."""
    username = f"student_{uuid.uuid4().hex[:6]}"
    password = "StudentPassword123!"
    hashed = hash_password(password)

    student_acc = AuthAccount(
        public_id=uuid.uuid4(),
        school_id=test_school.id,
        username=username,
        name="Test Siswa E2E",
        password_hash=hashed,
        role=UserRole.STUDENT.value if hasattr(UserRole.STUDENT, "value") else "STUDENT",
        is_active=True,
        must_change_password=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(student_acc)
    db.flush()

    return {
        "account": student_acc,
        "username": username,
        "password": password,
        "id": student_acc.id,
    }


@pytest.fixture
def test_student_must_change_pwd(db, test_school):
    """Creates a student auth account flagged with must_change_password=True."""
    username = f"student_pwd_{uuid.uuid4().hex[:6]}"
    password = "InitialPassword123!"
    hashed = hash_password(password)

    student_acc = AuthAccount(
        public_id=uuid.uuid4(),
        school_id=test_school.id,
        username=username,
        name="Test Siswa Forced Pwd",
        password_hash=hashed,
        role=UserRole.STUDENT.value if hasattr(UserRole.STUDENT, "value") else "STUDENT",
        is_active=True,
        must_change_password=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(student_acc)
    db.flush()

    return {
        "account": student_acc,
        "username": username,
        "password": password,
        "id": student_acc.id,
    }


@pytest.fixture
def test_teacher_must_change_pwd(db, test_school):
    """Creates a teacher auth account flagged with must_change_password=True."""
    username = f"teacher_pwd_{uuid.uuid4().hex[:6]}"
    password = "InitialPassword123!"
    hashed = hash_password(password)

    acc = AuthAccount(
        public_id=uuid.uuid4(),
        school_id=test_school.id,
        username=username,
        name="Test Guru Forced Pwd",
        password_hash=hashed,
        role=UserRole.TEACHER.value if hasattr(UserRole.TEACHER, "value") else "TEACHER",
        is_active=True,
        must_change_password=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(acc)
    db.flush()

    return {
        "account": acc,
        "username": username,
        "password": password,
        "id": acc.id,
    }


@pytest.fixture
def apk_headers():
    """Returns valid Lockxam APK request headers."""
    return {
        "x-client-app": "lockxam_apk",
        "user-agent": "LockxamBrowser/1.0 (Android; Mobile)",
        "x-device-id": "DEVICE-E2E-TEST-001",
    }


@pytest.fixture
def browser_headers():
    """Returns standard browser headers without APK signatures."""
    return {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    }


@pytest.fixture
def exam_test_env(db, test_school, test_teacher, test_student):
    """
    Sets up a full academic structure, question package, exam schedule,
    and student enrollment for exam lifecycle testing.
    """
    now = datetime.now(timezone.utc)

    # 1. Academic Year & Semester
    year = AcademicYear(
        school_id=test_school.id,
        name=f"2026/2027-E2E-{uuid.uuid4().hex[:4]}",
        start_date=now,
        end_date=now + timedelta(days=365),
        status=AcademicStatus.ACTIVE.value,
    )
    db.add(year)
    db.flush()

    semester = AcademicSemester(
        academic_year_id=year.id,
        code=f"SEM_E2E_{uuid.uuid4().hex[:4]}",
        display_name="Semester Ganjil E2E",
        status=AcademicStatus.ACTIVE.value,
    )
    db.add(semester)
    db.flush()

    # 2. Class & Student Enrollment
    cls = ClassEntity(
        school_id=test_school.id,
        academic_year_id=year.id,
        name=f"XII-IPA-E2E-{uuid.uuid4().hex[:4]}",
        grade_level="12",
        is_active=True,
    )
    db.add(cls)
    db.flush()

    enrollment = StudentClassEnrollment(
        class_id=cls.id,
        student_id=test_student["id"],
        academic_year_id=year.id,
        is_active=True,
    )
    db.add(enrollment)
    db.flush()

    # 3. Question Package with Essay and Multiple Choice
    pkg = QuestionPackage(
        school_id=test_school.id,
        owner_teacher_account_id=test_teacher["id"],
        title="Paket Ujian E2E Standard",
        subject_id=None,
        status="READY",
        passing_grade=75.0,
    )
    db.add(pkg)
    db.flush()

    q1 = Question(
        school_id=test_school.id,
        owner_teacher_account_id=test_teacher["id"],
        question_text="Jelaskan siklus air dan dampaknya terhadap perubahan iklim!",
        question_type=QuestionType.ESSAY.value if hasattr(QuestionType.ESSAY, "value") else "essay",
        max_score=10.0,
        answer_key="Siklus air meliputi evaporasi, kondensasi, presipitasi, dan infiltrasi.",
        rubric_criteria_json=[
            {"id": "C1", "criterion": "Konsep Evaporasi", "max_points": 3},
            {"id": "C2", "criterion": "Konsep Kondensasi & Presipitasi", "max_points": 3},
            {"id": "C3", "criterion": "Dampak Perubahan Iklim", "max_points": 4},
        ],
    )
    db.add(q1)
    db.flush()

    item1 = QuestionPackageItem(
        package_id=pkg.id,
        question_id=q1.id,
        order_number=1,
        allocated_score=10.0,
    )
    db.add(item1)
    db.flush()

    # 4. Exam Schedule (Window starts in future by default, 1 hour ahead)
    schedule_start = now + timedelta(hours=1)
    schedule_end = schedule_start + timedelta(hours=2)

    sched = ExamSchedule(
        school_id=test_school.id,
        name="Jadwal Ujian E2E",
        academic_year_id=year.id,
        academic_semester_id=semester.id,
        question_package_id=pkg.id,
        class_id=cls.id,
        start_time=schedule_start,
        end_time=schedule_end,
        duration_minutes=90,
        status="PUBLISHED",
    )
    db.add(sched)
    db.flush()

    # 5. Exam Session
    session = ExamSession(
        schedule_id=sched.id,
        session_name="Sesi 1 E2E",
        scheduled_start_at=schedule_start,
        scheduled_end_at=schedule_end,
        duration_minutes=90,
        status=ExamSessionStatus.READY.value if hasattr(ExamSessionStatus.READY, "value") else "READY",
    )
    db.add(session)
    db.flush()
    db.commit()

    return {
        "school": test_school,
        "year": year,
        "semester": semester,
        "class": cls,
        "teacher": test_teacher,
        "student": test_student,
        "package": pkg,
        "question": q1,
        "schedule": sched,
        "session": session,
    }
