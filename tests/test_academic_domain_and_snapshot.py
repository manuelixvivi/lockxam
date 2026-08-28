from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.exceptions.base import BusinessException
from app.models.academic.academic_semester import AcademicSemester
from app.models.academic.academic_year import AcademicYear
from app.models.academic.enums import AcademicStatus, EnrollmentStatus, ExamScheduleStatus
from app.models.master.school_level import SchoolLevel
from app.models.school.school import School
from app.models.security.auth_account import AuthAccount
from app.models.security.enums import UserRole
from app.models.teacher.enums import PackageStatus, QuestionType
from app.models.teacher.package_item import QuestionPackageItem
from app.models.teacher.question import Question
from app.models.teacher.question_package import QuestionPackage
from app.services.academic.class_service import ClassService
from app.services.academic.class_structure_service import ClassStructureService
from app.services.academic.exam_schedule_service import ExamScheduleService
from app.services.academic.exam_snapshot_service import ExamSnapshotService
from app.services.academic.subject_service import SubjectService


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


def create_test_school(db, name="SMA Negeri 1 Testing"):
    level = db.scalar(select(SchoolLevel).limit(1))
    if not level:
        level = SchoolLevel(code="SMA", name="Sekolah Menengah Atas")
        db.add(level)
        db.flush()

    unique_code = f"SCH_{uuid4().hex[:8]}"
    school = School(
        name=name,
        code=unique_code,
        domain=f"{unique_code.lower()}.sch.id",
        npsn=f"NPSN_{uuid4().hex[:6]}",
        school_level_id=level.id,
        address="Jl. Pendidikan No. 1",
        is_active=True,
    )
    db.add(school)
    db.flush()
    return school


def create_test_teacher(db, school_id, name="Pak Andi", username=None):
    uname = username or f"teacher_{uuid4().hex[:8]}"
    teacher = AuthAccount(
        school_id=school_id,
        username=uname,
        name=name,
        password_hash="fake_hash",
        role=UserRole.TEACHER.value,
        nip=f"19800101{uuid4().hex[:6]}",
        is_active=True,
    )
    db.add(teacher)
    db.flush()
    return teacher


def create_test_student(db, school_id, name="Manuel", username=None):
    uname = username or f"student_{uuid4().hex[:8]}"
    student = AuthAccount(
        school_id=school_id,
        username=uname,
        name=name,
        password_hash="fake_hash",
        role=UserRole.STUDENT.value,
        nisn=f"005{uuid4().hex[:7]}",
        is_active=True,
    )
    db.add(student)
    db.flush()
    return student


def create_test_academic_year(db, school_id, name="2026/2027"):
    now = datetime.now(timezone.utc)
    year = AcademicYear(
        school_id=school_id,
        name=name,
        start_date=now,
        end_date=now + timedelta(days=365),
        status=AcademicStatus.ACTIVE.value,
    )
    db.add(year)
    db.flush()
    return year


def create_test_semester(db, academic_year_id, code="GANJIL"):
    sem = AcademicSemester(
        academic_year_id=academic_year_id,
        code=code,
        display_name=f"Semester {code}",
        status=AcademicStatus.ACTIVE.value,
    )
    db.add(sem)
    db.flush()
    return sem


# ── TEST 1: Class Duplicate Invariant (ACADEMIC-CLASS-001) ──
def test_class_duplicate_invariant(db):
    school = create_test_school(db)
    year_2026 = create_test_academic_year(db, school.id, name="2026/2027")
    year_2027 = create_test_academic_year(db, school.id, name="2027/2028")

    # 1. Create X IPA 1 in 2026/2027 -> SUCCESS
    cls_1 = ClassService.create_class(
        db, school_id=school.id, academic_year_id=year_2026.id, name="X IPA 1"
    )
    assert cls_1.id is not None
    assert cls_1.name == "X IPA 1"

    # 2. Create duplicate X IPA 1 in same 2026/2027 -> MUST FAIL
    with pytest.raises(BusinessException) as exc_info:
        ClassService.create_class(
            db, school_id=school.id, academic_year_id=year_2026.id, name="X IPA 1"
        )
    assert "sudah ada pada tahun ajaran" in str(exc_info.value)

    # 3. Create X IPA 1 in different year 2027/2028 -> SUCCESS
    cls_2 = ClassService.create_class(
        db, school_id=school.id, academic_year_id=year_2027.id, name="X IPA 1"
    )
    assert cls_2.id is not None
    assert cls_2.academic_year_id == year_2027.id


# ── TEST 2: Teacher Assignment Eligibility Invariant (CLASS-TEACHER-001) ──
def test_teacher_assignment_eligibility(db):
    school = create_test_school(db)
    year = create_test_academic_year(db, school.id, name="2026/2027")
    cls = ClassService.create_class(db, school.id, year.id, name="X IPA 1")

    # Create Subjects
    subj_fisika = SubjectService.create_subject(db, school.id, code="FIS", name="Fisika")
    subj_biologi = SubjectService.create_subject(db, school.id, code="BIO", name="Biologi")

    # Create Teachers
    pak_andi = create_test_teacher(db, school.id, name="Pak Andi")
    bu_sari = create_test_teacher(db, school.id, name="Bu Sari")

    # Assign competency: Pak Andi -> Fisika
    SubjectService.assign_teacher_competency(db, school.id, pak_andi.id, subj_fisika.id)
    # Bu Sari -> Biologi
    SubjectService.assign_teacher_competency(db, school.id, bu_sari.id, subj_biologi.id)

    # 1. Assign Pak Andi to teach Fisika in X IPA 1 -> SUCCESS (Qualified)
    cst = ClassStructureService.assign_teacher_to_class_subject(
        db, school_id=school.id, class_id=cls.id, subject_id=subj_fisika.id, teacher_id=pak_andi.id
    )
    assert cst.teacher_id == pak_andi.id
    assert cst.subject_id == subj_fisika.id

    # 2. Try to assign Bu Sari to teach Fisika in X IPA 1 -> MUST FAIL (Not qualified)
    with pytest.raises(BusinessException) as exc_info:
        ClassStructureService.assign_teacher_to_class_subject(
            db,
            school_id=school.id,
            class_id=cls.id,
            subject_id=subj_fisika.id,
            teacher_id=bu_sari.id,
        )
    assert "belum memiliki kompetensi" in str(exc_info.value)


# ── TEST 3: Student Enrollment & Mutation Invariant (STUDENT-ACADEMIC-001) ──
def test_student_enrollment_and_mutation(db):
    school = create_test_school(db)
    year_2026 = create_test_academic_year(db, school.id, name="2026/2027")
    year_2027 = create_test_academic_year(db, school.id, name="2027/2028")

    cls_x1 = ClassService.create_class(db, school.id, year_2026.id, name="X IPA 1")
    cls_x2 = ClassService.create_class(db, school.id, year_2026.id, name="X IPA 2")
    cls_xi1 = ClassService.create_class(db, school.id, year_2027.id, name="XI IPA 1")

    student = create_test_student(db, school.id, name="Manuel")

    # Step 1: Enroll to X IPA 1 (2026/2027)
    enroll_1 = ClassStructureService.enroll_student_to_class(
        db, school_id=school.id, student_id=student.id, class_id=cls_x1.id
    )
    assert enroll_1.status == EnrollmentStatus.ACTIVE.value
    assert student.class_name == "X IPA 1"

    # Step 2: Mutasi to X IPA 2 (2026/2027)
    enroll_2 = ClassStructureService.enroll_student_to_class(
        db, school_id=school.id, student_id=student.id, class_id=cls_x2.id
    )
    assert enroll_2.status == EnrollmentStatus.ACTIVE.value
    assert enroll_2.class_id == cls_x2.id
    assert student.class_name == "X IPA 2"

    # Verify history: enroll_1 must be marked TRANSFERRED
    db.refresh(enroll_1)
    assert enroll_1.status == EnrollmentStatus.TRANSFERRED.value
    assert enroll_1.end_date is not None

    # Step 3: Next Year 2027/2028 -> Enroll to XI IPA 1
    enroll_3 = ClassStructureService.enroll_student_to_class(
        db, school_id=school.id, student_id=student.id, class_id=cls_xi1.id
    )
    assert enroll_3.status == EnrollmentStatus.ACTIVE.value

    # Verify student full history
    history = ClassStructureService.get_student_history(db, student.id)
    assert len(history) == 3


# ── TEST 4: Historical Exam Integrity & Immutable Snapshotting (EXAM-HISTORY-001/002/003) ──
def test_immutable_exam_snapshot(db):
    school = create_test_school(db)
    year = create_test_academic_year(db, school.id, name="2026/2027")
    sem = create_test_semester(db, year.id, code="GANJIL")
    cls = ClassService.create_class(db, school.id, year.id, name="X IPA 1")
    subj = SubjectService.create_subject(db, school.id, code="BIO", name="Biologi")
    guru = create_test_teacher(db, school.id, name="Bu Guru Biologi")

    # Assign Teacher & Subject to Class
    SubjectService.assign_teacher_competency(db, school.id, guru.id, subj.id)
    ClassStructureService.assign_teacher_to_class_subject(db, school.id, cls.id, subj.id, guru.id)

    # 1. Teacher creates Question with Rubric v1 in Question Bank
    rubric_v1 = [
        {"criteria": "Menjelaskan klorofil", "weight": 25},
        {"criteria": "Menjelaskan cahaya", "weight": 25},
        {"criteria": "Menjelaskan CO2", "weight": 25},
        {"criteria": "Menjelaskan glukosa", "weight": 25},
    ]
    q = Question(
        owner_teacher_account_id=guru.id,
        type=QuestionType.ES.value,
        content="Jelaskan proses fotosintesis secara singkat.",
        answer_key="Klorofil menyerap cahaya untuk fotosintesis.",
        rubrics=rubric_v1,
        subject="Biologi",
    )
    db.add(q)
    db.flush()

    # 2. Teacher creates Question Package and marks READY
    pkg = QuestionPackage(
        owner_teacher_account_id=guru.id,
        school_id=school.id,
        name="Paket UTS Biologi 2026",
        class_level="X",
        target_counts={"ES": 1},
        subject="Biologi",
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

    now = datetime.now(timezone.utc)

    # 3. Admin creates Exam Schedule
    schedule = ExamScheduleService.create_exam_schedule(
        db,
        school_id=school.id,
        academic_year_id=year.id,
        academic_semester_id=sem.id,
        class_id=cls.id,
        subject_id=subj.id,
        title="UTS Biologi Ganjil 2026/2027",
        start_time=now + timedelta(days=1),
        end_time=now + timedelta(days=1, hours=2),
        duration_minutes=90,
    )
    assert schedule.status == ExamScheduleStatus.DRAFT.value
    assert schedule.teacher_id == guru.id  # Auto derived from ClassSubjectTeacher

    # 4. Teacher selects package -> CREATE IMMUTABLE SNAPSHOT
    snapshot = ExamSnapshotService.create_immutable_snapshot(
        db,
        school_id=school.id,
        teacher_id=guru.id,
        schedule_public_id=schedule.public_id,
        package_public_id=pkg.public_id,
    )
    assert snapshot.id is not None
    assert snapshot.is_locked is True
    assert snapshot.total_questions == 1
    assert snapshot.total_points == 100

    # Verify Schedule status advanced to READY
    db.refresh(schedule)
    assert schedule.status == ExamScheduleStatus.READY.value

    # Verify snapshot content contains Rubric v1
    questions_in_snapshot = snapshot.snapshot_data["questions"]
    assert len(questions_in_snapshot) == 1
    assert questions_in_snapshot[0]["rubrics"][0]["criteria"] == "Menjelaskan klorofil"
    assert questions_in_snapshot[0]["rubrics"][0]["weight"] == 25

    # 5. Question in Question Bank is modified to Rubric v2 later
    q.rubrics = [
        {"criteria": "Menjelaskan klorofil", "weight": 20},
        {"criteria": "Menjelaskan cahaya", "weight": 20},
        {"criteria": "Menjelaskan CO2", "weight": 30},
        {"criteria": "Menjelaskan glukosa", "weight": 30},
    ]
    db.flush()

    # 6. INVARIANT CHECK: Exam Snapshot MUST REMAIN UNCHANGED (Rubric v1 preserved!)
    db.refresh(snapshot)
    saved_snapshot_rubrics = snapshot.snapshot_data["questions"][0]["rubrics"]
    assert saved_snapshot_rubrics[0]["weight"] == 25  # Still 25, not 20!
    assert saved_snapshot_rubrics[2]["weight"] == 25  # Still 25, not 30!

    # 7. Updating/overwriting locked package snapshot -> MUST FAIL (Snapshot Immutability)
    with pytest.raises(BusinessException) as exc_info:
        ExamSnapshotService.create_immutable_snapshot(
            db,
            school_id=school.id,
            teacher_id=guru.id,
            schedule_public_id=schedule.public_id,
            package_public_id=pkg.public_id,
        )
    assert "telah dikunci (IMMUTABLE)" in str(exc_info.value)

    # 8. Once active exam session exists, re-assignment must be REJECTED
    from app.models.exam.enums import ExamSessionStatus
    from app.models.exam.exam_session import ExamSession

    active_session = ExamSession(
        schedule_id=schedule.id,
        package_id=pkg.id,
        scheduled_start_at=schedule.start_time,
        scheduled_end_at=schedule.end_time,
        duration_minutes=90,
        status=ExamSessionStatus.ACTIVE,
    )
    db.add(active_session)
    db.flush()

    with pytest.raises(BusinessException) as exc_info:
        ExamSnapshotService.create_immutable_snapshot(
            db,
            school_id=school.id,
            teacher_id=guru.id,
            schedule_public_id=schedule.public_id,
            package_public_id=pkg.public_id,
        )
    assert "telah dikunci (IMMUTABLE)" in str(exc_info.value)


# ── TEST 5: Student & Teacher Historical Data Preservation Invariant ──
def test_historical_preservation_on_student_and_teacher_deactivation(db):
    from app.models.exam.exam_attempt import ExamAttempt
    from app.models.exam.exam_session import ExamSession
    from app.services.school.student_service import SchoolStudentService

    school = create_test_school(db)
    year = create_test_academic_year(db, school.id, name="2026/2027")
    sem = create_test_semester(db, year.id, code="GANJIL")
    cls = ClassService.create_class(db, school.id, year.id, name="X IPA 1")
    subj = SubjectService.create_subject(db, school.id, code="BIO", name="Biologi")
    guru = create_test_teacher(db, school.id, name="Bu Ani Historical")
    student = create_test_student(db, school.id, name="Budi Historical")

    # Assign Teacher & Subject to Class
    SubjectService.assign_teacher_competency(db, school.id, guru.id, subj.id)
    ClassStructureService.assign_teacher_to_class_subject(db, school.id, cls.id, subj.id, guru.id)

    pkg = QuestionPackage(
        owner_teacher_account_id=guru.id,
        school_id=school.id,
        name="Paket UTS Biologi",
        class_level="X",
        target_counts={"ES": 1},
        subject="Biologi",
        status=PackageStatus.READY.value,
    )
    db.add(pkg)
    db.flush()

    now = datetime.now(timezone.utc)
    schedule = ExamScheduleService.create_exam_schedule(
        db,
        school_id=school.id,
        academic_year_id=year.id,
        academic_semester_id=sem.id,
        class_id=cls.id,
        subject_id=subj.id,
        title="UTS Biologi",
        start_time=now + timedelta(days=1),
        end_time=now + timedelta(days=1, hours=2),
        duration_minutes=90,
    )

    from app.models.exam.enums import ExamAttemptStatus, ExamSessionStatus

    session = ExamSession(
        schedule_id=schedule.id,
        package_id=pkg.id,
        scheduled_start_at=schedule.start_time,
        scheduled_end_at=schedule.end_time,
        duration_minutes=90,
        status=ExamSessionStatus.ACTIVE,
    )
    db.add(session)
    db.flush()

    attempt = ExamAttempt(
        exam_session_id=session.id,
        student_id=student.id,
        status=ExamAttemptStatus.IN_PROGRESS,
        randomized_order=[1],
    )
    db.add(attempt)
    db.flush()

    # 1. Attempting hard delete on student with exam attempt -> MUST REJECT!
    with pytest.raises(BusinessException) as exc_info:
        SchoolStudentService.delete_student(db, school.id, str(student.public_id))
    assert "memiliki riwayat ujian tidak dapat dihapus" in str(exc_info.value)

    # 2. Deactivating student -> SUCCESS, attempt remains intact!
    toggled = SchoolStudentService.toggle_student_active(db, school.id, str(student.public_id))
    assert toggled.is_active is False

    db.refresh(attempt)
    assert attempt.id is not None
    assert attempt.student_id == student.id  # Historical attempt preserved!


# =============================================================================
# TeacherSubject Single Source-of-Truth Regression Tests (P1-02)
# =============================================================================


def test_teacher_competency_via_teacher_subject_only(db):
    """
    A. Admin cannot create teacher competency through subjects_taught.
    B. Admin cannot update teacher competency through subjects_taught.
    C. TeacherSubject assignment creates competency.
    D. TeacherSubject removal removes competency.
    E. Candidate teacher lookup uses TeacherSubject only.
    F. Modifying legacy subjects_taught cannot grant competency.
    G. Modifying TeacherSubject changes competency correctly.
    """
    from app.repositories.academic.teacher_subject_repository import teacher_subject_repository
    from app.services.academic.subject_service import SubjectService
    from app.services.school.staff_service import SchoolStaffService

    school = create_test_school(db)

    # Create subject
    subj = SubjectService.create_subject(db, school.id, "MAT", "Matematika")
    db.flush()

    # ── A. Create teacher: subjects_taught NOT accepted as competency authority ─
    nip = f"9{uuid4().int % 10**9:09d}"
    teacher, _ = SchoolStaffService.create_teacher(
        db=db,
        school_id=school.id,
        name="Guru Satu",
        nip=nip,
        gender="L",
        registered_year=2020,
        classes_taught=[],
        # subjects_taught intentionally NOT passed (removed from signature)
    )
    db.flush()

    # Teacher has no competency by default
    ts_records = teacher_subject_repository.list_by_teacher(db, teacher.id)
    assert len(ts_records) == 0, "A: New teacher must have zero TeacherSubject records"

    # ── B. Directly writing subjects_taught on AuthAccount does NOT grant competency ──
    # (This simulates legacy/admin direct attribute write bypassing SubjectService)
    teacher.subjects_taught = ["Matematika"]
    db.flush()

    # TeacherSubject still has zero records — subjects_taught write is NOT competency
    ts_records = teacher_subject_repository.list_by_teacher(db, teacher.id)
    assert (
        len(ts_records) == 0
    ), "B: Writing subjects_taught directly must NOT create TeacherSubject records"

    # ── C. Assigning via SubjectService creates TeacherSubject ──────────────────
    ts = SubjectService.assign_teacher_competency(db, school.id, teacher.id, subj.id)
    db.flush()
    assert ts is not None, "C: assign_teacher_competency must return a TeacherSubject record"
    ts_records = teacher_subject_repository.list_by_teacher(db, teacher.id)
    assert len(ts_records) == 1, "C: TeacherSubject must have exactly 1 record after assignment"
    assert ts_records[0].subject_id == subj.id

    # ── D. Removal via SubjectService deletes TeacherSubject ────────────────────
    SubjectService.unassign_teacher_competency(db, teacher.id, subj.id)
    db.flush()
    ts_records = teacher_subject_repository.list_by_teacher(db, teacher.id)
    assert len(ts_records) == 0, "D: TeacherSubject must be empty after unassignment"

    # ── E. Candidate lookup uses TeacherSubject only (not subjects_taught) ──────
    # teacher.subjects_taught still has ["Matematika"] from step B
    # but TeacherSubject has zero records — candidate list must be empty
    candidates = SubjectService.list_qualified_teachers_for_subject(db, school.id, subj.id)
    assert teacher.id not in [
        c.id for c in candidates
    ], "E: Candidate lookup must use TeacherSubject only, NOT subjects_taught field"

    # ── F. Legacy subjects_taught cannot grant access via candidate lookup ────────
    teacher.subjects_taught = ["Matematika"]
    db.flush()
    candidates = SubjectService.list_qualified_teachers_for_subject(db, school.id, subj.id)
    assert teacher.id not in [
        c.id for c in candidates
    ], "F: Modifying subjects_taught directly must NOT appear in candidate lookup"

    # ── G. Re-assign via TeacherSubject restores candidacy ──────────────────────
    SubjectService.assign_teacher_competency(db, school.id, teacher.id, subj.id)
    db.flush()
    candidates = SubjectService.list_qualified_teachers_for_subject(db, school.id, subj.id)
    assert teacher.id in [
        c.id for c in candidates
    ], "G: After TeacherSubject assignment, teacher must appear in candidate lookup"


def test_legacy_subjects_taught_cannot_pollute_projection(db):
    """
    1. Create teacher.
    2. Set legacy subjects_taught = ["Matematika"].
    3. Ensure TeacherSubject has zero records.
    4. Call list_teachers().
    5. Assert projected subjects_taught does NOT contain "Matematika".
    6. Create TeacherSubject(Math).
    7. Call list_teachers().
    8. Assert projected subjects_taught contains "Matematika".
    9. Remove TeacherSubject.
    10. Call list_teachers().
    11. Assert projection is empty.
    """
    from app.repositories.academic.teacher_subject_repository import teacher_subject_repository
    from app.services.academic.subject_service import SubjectService
    from app.services.school.staff_service import SchoolStaffService

    school = create_test_school(db)

    # 1. Create teacher
    nip = f"9{uuid4().int % 10**9:09d}"
    teacher, _ = SchoolStaffService.create_teacher(
        db=db,
        school_id=school.id,
        name="Guru Dua",
        nip=nip,
        gender="P",
        registered_year=2021,
        classes_taught=[],
    )
    db.flush()

    # 2. Set legacy subjects_taught = ["Matematika"]
    teacher.subjects_taught = ["Matematika"]
    db.flush()

    # 3. Ensure TeacherSubject has zero records
    ts_records = teacher_subject_repository.list_by_teacher(db, teacher.id)
    assert len(ts_records) == 0

    # 4. Call list_teachers()
    teachers = SchoolStaffService.list_teachers(db, school.id)
    t_opt = next((t for t in teachers if t.id == teacher.id), None)
    assert t_opt is not None

    # 5. Assert projected subjects_taught does NOT contain "Matematika"
    assert "Matematika" not in (t_opt.subjects_taught or [])

    # 6. Create TeacherSubject (Math)
    subj = SubjectService.create_subject(db, school.id, "MAT", "Matematika")
    db.flush()
    SubjectService.assign_teacher_competency(db, school.id, teacher.id, subj.id)
    db.flush()

    # 7. Call list_teachers()
    teachers = SchoolStaffService.list_teachers(db, school.id)
    t_opt = next((t for t in teachers if t.id == teacher.id), None)
    assert t_opt is not None

    # 8. Assert projected subjects_taught contains "Matematika"
    assert "Matematika" in (t_opt.subjects_taught or [])

    # 9. Remove TeacherSubject
    SubjectService.unassign_teacher_competency(db, teacher.id, subj.id)
    db.flush()

    # 10. Call list_teachers()
    teachers = SchoolStaffService.list_teachers(db, school.id)
    t_opt = next((t for t in teachers if t.id == teacher.id), None)
    assert t_opt is not None

    # 11. Assert projection is empty
    assert len(t_opt.subjects_taught or []) == 0
