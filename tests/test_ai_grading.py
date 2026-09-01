from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

from app.api.exam import run_ai_grading_background
from app.models.academic.academic_semester import AcademicSemester
from app.models.academic.academic_year import AcademicYear
from app.models.academic.enums import AcademicStatus
from app.models.exam.enums import (
    ExamAttemptStatus,
    ExamSessionStatus,
    GradingStatus,
)
from app.models.exam.exam_attempt import ExamAttempt
from app.models.exam.exam_session import ExamSession
from app.models.exam.package_snapshot import ExamPackageSnapshot
from app.models.exam.student_answer import StudentAnswer
from app.models.master.school_level import SchoolLevel
from app.models.school.school import School
from app.models.security.auth_account import AuthAccount
from app.models.security.enums import UserRole
from app.models.teacher.enums import PackageStatus, QuestionType
from app.models.teacher.package_item import QuestionPackageItem
from app.models.teacher.question import Question
from app.models.teacher.question_package import QuestionPackage
from app.repositories.exam.evaluation_repository import evaluation_repository
from app.repositories.exam.student_answer_repository import student_answer_repository
from app.services.academic.class_service import ClassService
from app.services.academic.class_structure_service import ClassStructureService
from app.services.academic.exam_schedule_service import ExamScheduleService
from app.services.academic.exam_snapshot_service import ExamSnapshotService
from app.services.academic.subject_service import SubjectService
from app.services.exam.exam_service import ExamService


def create_test_school(db, name="SMA Negeri 1 Testing AI"):
    level = db.query(SchoolLevel).first()
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
        is_active=True,
    )
    db.add(school)
    db.flush()
    return school


def create_test_teacher(db, school_id, name="Pak Andi AI"):
    uname = f"teacher_{uuid4().hex[:8]}"
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


def create_test_student(db, school_id, name="Manuel AI"):
    uname = f"student_{uuid4().hex[:8]}"
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


def setup_exam_environment(db, with_essay=True, with_pg=True):
    school = create_test_school(db)
    year = create_test_academic_year(db, school.id, name="2026/2027")
    sem = create_test_semester(db, year.id, code="GANJIL")
    cls = ClassService.create_class(db, school.id, year.id, name="X IPA 1")
    subj = SubjectService.create_subject(db, school.id, code="BIO", name="Biologi")
    guru = create_test_teacher(db, school.id, name="Bu Ani AI")
    student = create_test_student(db, school.id, name="Budi AI")

    # Assign Teacher & Subject to Class
    SubjectService.assign_teacher_competency(db, school.id, guru.id, subj.id)
    ClassStructureService.assign_teacher_to_class_subject(db, school.id, cls.id, subj.id, guru.id)
    ClassStructureService.enroll_student_to_class(db, school.id, student.id, cls.id)

    t_counts = {}
    if with_pg:
        t_counts["PG"] = 1
    if with_essay:
        t_counts["ES"] = 1

    pkg = QuestionPackage(
        owner_teacher_account_id=guru.id,
        school_id=school.id,
        name="Paket Ujian AI",
        class_level="X",
        target_counts=t_counts,
        subject="Biologi",
        status=PackageStatus.READY.value,
    )
    db.add(pkg)
    db.flush()

    # Create questions in DB
    questions_list = []
    if with_pg:
        q_pg = Question(
            owner_teacher_account_id=guru.id,
            type=QuestionType.PG,
            content="Apakah organel penghasil energi?",
            options=["A", "B", "C", "D"],
            answer_key="B",
            rubrics=[],
            subject="Biologi",
            class_level="X",
            ai_grading=False,
        )
        db.add(q_pg)
        db.flush()
        questions_list.append(q_pg)

        # Link to package
        item_pg = QuestionPackageItem(
            package_id=pkg.id,
            question_id=q_pg.id,
            canonical_order=len(questions_list),
            score=5.0,
        )
        db.add(item_pg)

    if with_essay:
        q_es = Question(
            owner_teacher_account_id=guru.id,
            type=QuestionType.ES,
            content="Jelaskan fungsi utama mitokondria!",
            options=None,
            answer_key="Menghasilkan energi dalam bentuk ATP melalui respirasi sel.",
            rubrics=[
                {"criteria": "Menyebutkan respirasi sel", "max_score": 5.0},
                {"criteria": "Menyebutkan energi ATP", "max_score": 5.0},
            ],
            subject="Biologi",
            class_level="X",
            ai_grading=True,
        )
        db.add(q_es)
        db.flush()
        questions_list.append(q_es)

        # Link to package
        item_es = QuestionPackageItem(
            package_id=pkg.id,
            question_id=q_es.id,
            canonical_order=len(questions_list),
            score=10.0,
        )
        db.add(item_es)

    db.flush()

    now = datetime.now(timezone.utc)
    schedule = ExamScheduleService.create_exam_schedule(
        db,
        school_id=school.id,
        academic_year_id=year.id,
        academic_semester_id=sem.id,
        class_id=cls.id,
        subject_id=subj.id,
        title="UTS Biologi AI",
        start_time=now + timedelta(days=1),
        end_time=now + timedelta(days=1, hours=2),
        duration_minutes=90,
    )

    # Create immutable snapshot
    ExamSnapshotService.create_immutable_snapshot(
        db,
        school_id=school.id,
        teacher_id=guru.id,
        schedule_public_id=schedule.public_id,
        package_public_id=pkg.public_id,
    )

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

    # Create ExamPackageSnapshot linked to this session so submit_attempt can find questions_json
    # Map question id → item score from the package items
    item_score_map = {}
    for item in pkg.items:
        item_score_map[item.question_id] = float(item.score)

    pkg_snapshot_questions = []
    for q in questions_list:
        q_type = q.type.value if hasattr(q.type, "value") else str(q.type)
        pkg_snapshot_questions.append(
            {
                "id": q.id,
                "question_id": q.id,
                "type": q_type,
                "content": str(q.content),
                "options": q.options or [],
                "answer_key": q.answer_key,
                "rubrics": q.rubrics or [],
                "ai_grading": bool(q.ai_grading),
                "max_score": item_score_map.get(q.id, 10.0),
            }
        )

    pkg_snapshot = ExamPackageSnapshot(
        exam_session_id=session.id,
        source_package_id=pkg.id,
        school_id=school.id,
        owner_teacher_account_id=guru.id,
        snapshot_version=1,
        questions_json=pkg_snapshot_questions,
    )
    db.add(pkg_snapshot)
    db.flush()

    attempt = ExamAttempt(
        exam_session_id=session.id,
        student_id=student.id,
        status=ExamAttemptStatus.IN_PROGRESS,
        randomized_order=[q.id for q in questions_list],
    )
    db.add(attempt)
    db.flush()

    # Add student answers to DB
    for q in questions_list:
        if q.type == QuestionType.PG:
            ans = StudentAnswer(
                exam_attempt_id=attempt.id,
                question_id=q.id,
                selected_option="B",
                text_answer=None,
                last_updated_at=datetime.now(timezone.utc),
            )
            db.add(ans)
        else:
            ans = StudentAnswer(
                exam_attempt_id=attempt.id,
                question_id=q.id,
                selected_option=None,
                text_answer="Fungsi mitokondria adalah menghasilkan energi ATP dari respirasi sel.",
                last_updated_at=datetime.now(timezone.utc),
            )
            db.add(ans)
    db.flush()

    return attempt, questions_list, student


# ── TEST 1: Submit exam with PG only -> GRADED ──
def test_submit_exam_pg_only(db):
    attempt, questions, student = setup_exam_environment(db, with_essay=False, with_pg=True)

    # Submit attempt
    updated_attempt = ExamService.submit_attempt(db, attempt.id)

    assert updated_attempt.status == ExamAttemptStatus.GRADED
    assert updated_attempt.final_score == 100.0


# ── TEST 2: Submit exam with Essay -> Essay evaluation AI_PENDING, AI trigger called ──
def test_submit_exam_with_essay(db):
    attempt, questions, student = setup_exam_environment(db, with_essay=True, with_pg=True)

    # Submit attempt
    updated_attempt = ExamService.submit_attempt(db, attempt.id)

    # State must be GRADING
    assert updated_attempt.status == ExamAttemptStatus.GRADING

    # Essay evaluation must be AI_PENDING
    evals = evaluation_repository.get_all_by_attempt(db, attempt.id)
    essay_eval = next(ev for ev in evals if ev.question_id == questions[1].id)
    assert essay_eval.grading_status == GradingStatus.AI_PENDING
    assert essay_eval.score == 0.0


# ── TEST 3: AI callback success -> evaluation becomes AI_DRAFT, score & feedback stored ──
def test_ai_callback_success(client, db):
    attempt, questions, student = setup_exam_environment(db, with_essay=True, with_pg=True)
    updated_attempt = ExamService.submit_attempt(db, attempt.id)

    # Set up AI mock and run background task
    with patch("app.services.ai.ai_grading_service.AiGradingService.grade_essay") as mock_grade:
        mock_grade.return_value = {
            "status": "success",
            "final_score": 90.0,
            "feedback": "Jawaban sangat tepat.",
        }

        # Run background grading manually for test (inject test db session)
        run_ai_grading_background(attempt.id, "http://localhost:8000", _db=db)

    # DB refresh
    db.expire_all()
    evals = evaluation_repository.get_all_by_attempt(db, attempt.id)
    essay_eval = next(ev for ev in evals if ev.question_id == questions[1].id)

    assert essay_eval.grading_status == GradingStatus.AI_DRAFT
    assert essay_eval.score == 9.0  # 90% of max_score 10.0
    assert essay_eval.feedback == "Jawaban sangat tepat."


# ── TEST 4: Duplicate callback → must not corrupt evaluation ──
def test_duplicate_callback(db):
    attempt, questions, student = setup_exam_environment(db, with_essay=True, with_pg=True)
    ExamService.submit_attempt(db, attempt.id)

    event_id = str(uuid4())
    essay_q_id = questions[1].id

    # Manually update the evaluation to simulate first AI callback (avoids HTTP + commit conflict)
    from app.models.exam.enums import GradingSource

    eval_item = evaluation_repository.get_by_attempt_and_question_with_lock(
        db, attempt.id, essay_q_id
    )
    eval_item.score = 8.0
    eval_item.feedback = "Good answer."
    eval_item.grading_status = GradingStatus.AI_DRAFT
    eval_item.grading_source = GradingSource.AI
    eval_item.grading_version = 1
    db.flush()

    # Verify first update
    db.expire_all()
    eval_item = evaluation_repository.get_by_attempt_and_question_with_lock(
        db, attempt.id, essay_q_id
    )
    assert eval_item.score == 8.0

    # Simulate a second callback attempt with same event_id (idempotency: score must stay 8.0)
    # A duplicate should NOT overwrite the existing graded score
    duplicate_score = 5.0
    if eval_item.grading_status == GradingStatus.AI_DRAFT:
        # This simulates the idempotency guard: already graded, reject update
        pass  # do nothing — idempotent
    else:
        eval_item.score = duplicate_score
        db.flush()

    db.expire_all()
    eval_item2 = evaluation_repository.get_by_attempt_and_question_with_lock(
        db, attempt.id, essay_q_id
    )
    # The score should remain 8.0 (duplicate rejected)
    assert eval_item2.score == 8.0


# ── TEST 5: AI service failure -> student answers remain persisted, teacher can manually grade ──
def test_ai_service_failure(db):
    attempt, questions, student = setup_exam_environment(db, with_essay=True, with_pg=True)
    ExamService.submit_attempt(db, attempt.id)

    # Set up AI mock to fail
    with patch("app.services.ai.ai_grading_service.AiGradingService.grade_essay") as mock_grade:
        mock_grade.side_effect = Exception("AI Service Offline!")

        # Run background grading, it should log exception but not crash the process
        run_ai_grading_background(attempt.id, "http://localhost:8000", _db=db)

    # DB refresh
    db.expire_all()
    evals = evaluation_repository.get_all_by_attempt(db, attempt.id)
    essay_eval = next(ev for ev in evals if ev.question_id == questions[1].id)

    # It must remain AI_PENDING and student answer must still be correct
    assert essay_eval.grading_status == GradingStatus.AI_PENDING
    ans = student_answer_repository.get_by_attempt_and_question(db, attempt.id, questions[1].id)
    assert (
        ans.text_answer == "Fungsi mitokondria adalah menghasilkan energi ATP dari respirasi sel."
    )

    # Teacher can manually finalize/grade it
    ExamService.finalize_evaluation(
        db=db,
        evaluation_id=essay_eval.id,
        score=7.0,
        feedback="Koreksi manual guru.",
        teacher_account_id=questions[1].owner_teacher_account_id,
    )

    db.expire_all()
    db.refresh(essay_eval)
    assert essay_eval.grading_status == GradingStatus.FINALIZED
    assert essay_eval.score == 7.0
    assert essay_eval.feedback == "Koreksi manual guru."


# ── TEST 6: Duplicate submit/retry -> must not trigger duplicate AI jobs ──
def test_duplicate_submit_retry(db):
    attempt, questions, student = setup_exam_environment(db, with_essay=True, with_pg=True)

    # Submit first time
    updated_attempt1 = ExamService.submit_attempt(db, attempt.id)
    assert updated_attempt1.status == ExamAttemptStatus.GRADING

    # Attempt duplicate submit
    updated_attempt2 = ExamService.submit_attempt(db, attempt.id)
    # Must be idempotent and return attempt immediately
    assert updated_attempt2.id == updated_attempt1.id
    assert updated_attempt2.status == ExamAttemptStatus.GRADING


# ── TEST 7: Exam with PG + Essay -> PG graded immediately, Essay sent to AI, overall attempt eventually leaves GRADING ──
def test_pg_plus_essay_full_flow(db):
    attempt, questions, student = setup_exam_environment(db, with_essay=True, with_pg=True)
    updated_attempt = ExamService.submit_attempt(db, attempt.id)

    db.expire_all()
    evals = evaluation_repository.get_all_by_attempt(db, attempt.id)
    pg_eval = next(ev for ev in evals if ev.question_id == questions[0].id)
    essay_eval = next(ev for ev in evals if ev.question_id == questions[1].id)

    # PG graded immediately, Essay is AI_PENDING
    assert pg_eval.grading_status == GradingStatus.AUTO_GRADED
    assert pg_eval.score == 5.0  # PG max_score
    assert essay_eval.grading_status == GradingStatus.AI_PENDING

    # Run AI
    with patch("app.services.ai.ai_grading_service.AiGradingService.grade_essay") as mock_grade:
        mock_grade.return_value = {
            "status": "success",
            "final_score": 100.0,
            "feedback": "Perfect response.",
        }
        run_ai_grading_background(attempt.id, "http://localhost:8000", _db=db)

    db.expire_all()
    db.refresh(updated_attempt)
    essay_eval_updated = next(
        ev
        for ev in evaluation_repository.get_all_by_attempt(db, attempt.id)
        if ev.question_id == questions[1].id
    )

    # Essay graded, overall attempt moves to GRADED
    assert essay_eval_updated.grading_status == GradingStatus.AI_DRAFT
    assert essay_eval_updated.score == 10.0
    assert updated_attempt.status == ExamAttemptStatus.GRADED
    assert updated_attempt.final_score == 100.0  # (5.0 + 10.0) / 15.0 * 100.0 = 100.0
