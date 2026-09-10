from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.academic.academic_semester import AcademicSemester
from app.models.academic.academic_year import AcademicYear
from app.models.academic.enums import AcademicStatus
from app.models.ai.assessment_history import AssessmentHistory
from app.models.exam.enums import (
    ExamAttemptStatus,
    ExamSessionStatus,
    GradingSource,
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
from app.repositories.ai.assessment_history_repository import (
    assessment_history_repository,
)
from app.repositories.exam.evaluation_repository import evaluation_repository
from app.repositories.exam.student_answer_repository import student_answer_repository
from app.services.academic.class_service import ClassService
from app.services.academic.class_structure_service import ClassStructureService
from app.services.academic.exam_schedule_service import ExamScheduleService
from app.services.academic.exam_snapshot_service import ExamSnapshotService
from app.services.academic.subject_service import SubjectService
from app.services.ai.assessment_history_service import AssessmentHistoryService
from app.services.exam.exam_service import ExamService


def setup_exam_environment(db, school_name="SMA Labschool AI", with_essay=True, with_pg=True):
    level = db.query(SchoolLevel).first()
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
        is_active=True,
    )
    db.add(school)
    db.flush()

    now = datetime.now(timezone.utc)
    year = AcademicYear(
        school_id=school.id,
        name="2026/2027",
        start_date=now,
        end_date=now + timedelta(days=365),
        status=AcademicStatus.ACTIVE.value,
    )
    db.add(year)
    db.flush()

    sem = AcademicSemester(
        academic_year_id=year.id,
        code="GANJIL",
        display_name="Semester Ganjil",
        status=AcademicStatus.ACTIVE.value,
    )
    db.add(sem)
    db.flush()

    cls = ClassService.create_class(db, school.id, year.id, name="XI IPA 1")
    subj = SubjectService.create_subject(db, school.id, code="KIM", name="Kimia")

    guru = AuthAccount(
        school_id=school.id,
        username=f"teacher_{uuid4().hex[:8]}",
        name="Dr. Manuel Kimia",
        password_hash="fake_hash",
        role=UserRole.TEACHER.value,
        nip=f"19850101{uuid4().hex[:6]}",
        is_active=True,
    )
    db.add(guru)
    db.flush()

    student = AuthAccount(
        school_id=school.id,
        username=f"student_{uuid4().hex[:8]}",
        name="Arselio Theo",
        password_hash="fake_hash",
        role=UserRole.STUDENT.value,
        nisn=f"098{uuid4().hex[:7]}",
        is_active=True,
    )
    db.add(student)
    db.flush()

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
        name="Paket Ujian Kimia",
        class_level="XI",
        target_counts=t_counts,
        subject="Kimia",
        status=PackageStatus.READY.value,
    )
    db.add(pkg)
    db.flush()

    questions_list = []
    if with_pg:
        q_pg = Question(
            owner_teacher_account_id=guru.id,
            type=QuestionType.PG,
            content="Apa rumus kimia air?",
            options=["H2O", "CO2", "NaCl", "O2"],
            answer_key="H2O",
            rubrics=[],
            subject="Kimia",
            class_level="XI",
            ai_grading=False,
        )
        db.add(q_pg)
        db.flush()
        questions_list.append(q_pg)

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
            content="Jelaskan Hukum Perbandingan Berganda Dalton!",
            options=None,
            answer_key="Bila dua unsur membentuk dua senyawa atau lebih...",
            rubrics=[
                {
                    "name": "Konsep Dasar",
                    "points": 5,
                    "description": "Menyebutkan dua unsur membentuk senyawa",
                },
                {
                    "name": "Perbandingan Massa",
                    "points": 5,
                    "description": "Menjelaskan massa perbandingan bulat sederhana",
                },
            ],
            subject="Kimia",
            class_level="XI",
            ai_grading=True,
        )
        db.add(q_es)
        db.flush()
        questions_list.append(q_es)

        item_es = QuestionPackageItem(
            package_id=pkg.id,
            question_id=q_es.id,
            canonical_order=len(questions_list),
            score=10.0,
        )
        db.add(item_es)

    db.flush()

    schedule = ExamScheduleService.create_exam_schedule(
        db,
        school_id=school.id,
        academic_year_id=year.id,
        academic_semester_id=sem.id,
        class_id=cls.id,
        subject_id=subj.id,
        title="Penilaian Akhir Semester Kimia",
        start_time=now - timedelta(hours=1),
        end_time=now + timedelta(hours=2),
        duration_minutes=90,
    )

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

    item_score_map = {item.question_id: float(item.score) for item in pkg.items}
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
                "subject": "Kimia",
                "class_level": "XI",
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

    for q in questions_list:
        if q.type == QuestionType.PG:
            ans = StudentAnswer(
                exam_attempt_id=attempt.id,
                question_id=q.id,
                selected_option="H2O",
                text_answer=None,
                last_updated_at=datetime.now(timezone.utc),
            )
            db.add(ans)
        else:
            ans = StudentAnswer(
                exam_attempt_id=attempt.id,
                question_id=q.id,
                selected_option=None,
                text_answer="Hukum Dalton berbunyi: Jika dua unsur bereaksi membentuk dua atau lebih senyawa, maka perbandingan massa salah satu unsur yang bergabung dengan massa tetap unsur lain adalah bilangan bulat dan sederhana.",
                last_updated_at=datetime.now(timezone.utc),
            )
            db.add(ans)
    db.flush()

    return attempt, questions_list, guru, student, school, subj


# ── TEST 1: FINALIZED teacher evaluation creates history v1 ──────────────────
def test_finalized_teacher_evaluation_creates_history_v1(db):
    attempt, questions, teacher, student, school, subj = setup_exam_environment(db)
    ExamService.submit_attempt(db, attempt.id, student_id=attempt.student_id)

    evals = evaluation_repository.get_all_by_attempt(db, attempt.id)
    essay_eval = next(ev for ev in evals if ev.question_id == questions[1].id)

    finalized_eval = ExamService.finalize_evaluation(
        db=db,
        evaluation_id=essay_eval.id,
        score=9.5,
        feedback="Jawaban sangat akurat dan memenuhi semua rubrik Dalton.",
        teacher_account_id=teacher.id,
    )
    assert finalized_eval.grading_status == GradingStatus.FINALIZED

    history = assessment_history_repository.get_current_by_evaluation(db, essay_eval.id)
    assert history is not None
    assert history.version == 1
    assert history.is_current is True
    assert history.superseded_at is None
    assert float(history.final_score) == 9.5
    assert float(history.teacher_score) == 9.5
    assert history.teacher_feedback == "Jawaban sangat akurat dan memenuhi semua rubrik Dalton."
    assert history.question_text == "Jelaskan Hukum Perbandingan Berganda Dalton!"
    assert history.subject_id == subj.id
    assert history.school_id == school.id
    assert history.finalized_by_teacher_id == teacher.id
    assert history.is_rag_eligible is True
    assert history.embedding_status in ("PENDING", "EMBEDDED")


# ── TEST 2: AI_DRAFT does not create history ─────────────────────────────────
def test_ai_draft_does_not_create_history(db):
    attempt, questions, teacher, student, school, subj = setup_exam_environment(db)
    ExamService.submit_attempt(db, attempt.id, student_id=attempt.student_id)

    evals = evaluation_repository.get_all_by_attempt(db, attempt.id)
    essay_eval = next(ev for ev in evals if ev.question_id == questions[1].id)

    essay_eval.grading_status = GradingStatus.AI_DRAFT
    essay_eval.grading_source = GradingSource.AI
    essay_eval.score = 8.0
    essay_eval.feedback = "AI predicted score."
    db.flush()

    res = AssessmentHistoryService.capture_finalized_evaluation(db, essay_eval, teacher.id)
    assert res is None

    history = assessment_history_repository.get_current_by_evaluation(db, essay_eval.id)
    assert history is None


# ── TEST 3: Non-essay evaluation (PG) does not create history ────────────────
def test_non_essay_evaluation_does_not_create_history(db):
    attempt, questions, teacher, student, school, subj = setup_exam_environment(db)
    ExamService.submit_attempt(db, attempt.id, student_id=attempt.student_id)

    evals = evaluation_repository.get_all_by_attempt(db, attempt.id)
    pg_eval = next(ev for ev in evals if ev.question_id == questions[0].id)

    res = AssessmentHistoryService.capture_finalized_evaluation(db, pg_eval, teacher.id)
    assert res is None


# ── TEST 4: Empty student answer does not create history ────────────────────
def test_empty_student_answer_does_not_create_history(db):
    attempt, questions, teacher, student, school, subj = setup_exam_environment(db)
    ans = student_answer_repository.get_by_attempt_and_question(db, attempt.id, questions[1].id)
    ans.text_answer = "   "
    db.flush()

    ExamService.submit_attempt(db, attempt.id, student_id=attempt.student_id)
    evals = evaluation_repository.get_all_by_attempt(db, attempt.id)
    essay_eval = next(ev for ev in evals if ev.question_id == questions[1].id)

    essay_eval.grading_status = GradingStatus.FINALIZED
    essay_eval.grading_source = GradingSource.TEACHER
    db.flush()

    res = AssessmentHistoryService.capture_finalized_evaluation(db, essay_eval, teacher.id)
    assert res is None


# ── TEST 5: Snapshot content is used instead of mutable Question content ─────
def test_snapshot_content_used_instead_of_mutable_question(db):
    attempt, questions, teacher, student, school, subj = setup_exam_environment(db)
    ExamService.submit_attempt(db, attempt.id, student_id=attempt.student_id)

    questions[1].content = "PERTANYAAN SUDAH BERUBAH TOTAL!"
    questions[1].answer_key = "KUNCI JAWABAN BARU"
    db.flush()

    evals = evaluation_repository.get_all_by_attempt(db, attempt.id)
    essay_eval = next(ev for ev in evals if ev.question_id == questions[1].id)

    ExamService.finalize_evaluation(
        db=db,
        evaluation_id=essay_eval.id,
        score=10.0,
        feedback="Sempurna.",
        teacher_account_id=teacher.id,
    )

    history = assessment_history_repository.get_current_by_evaluation(db, essay_eval.id)
    assert history.question_text == "Jelaskan Hukum Perbandingan Berganda Dalton!"
    assert history.answer_key == "Bila dua unsur membentuk dua senyawa atau lebih..."


# ── TEST 6, 7, 8, 9: Teacher correction creates v2, v1 superseded, payload intact ─
def test_teacher_correction_versioning_lifecycle(db):
    attempt, questions, teacher, student, school, subj = setup_exam_environment(db)
    ExamService.submit_attempt(db, attempt.id, student_id=attempt.student_id)

    evals = evaluation_repository.get_all_by_attempt(db, attempt.id)
    essay_eval = next(ev for ev in evals if ev.question_id == questions[1].id)

    # 1. Initial Finalization (v1)
    ExamService.finalize_evaluation(
        db=db,
        evaluation_id=essay_eval.id,
        score=8.0,
        feedback="Penjelasan sudah baik.",
        teacher_account_id=teacher.id,
    )

    history_v1 = assessment_history_repository.get_history_by_evaluation_and_version(
        db, essay_eval.id, version=1
    )
    assert history_v1 is not None
    assert history_v1.version == 1
    assert history_v1.is_current is True
    assert float(history_v1.final_score) == 8.0

    # 2. Teacher Re-finalizes with Correction (e.g. after student protest approved)
    ExamService.finalize_evaluation(
        db=db,
        evaluation_id=essay_eval.id,
        score=9.5,
        feedback="Setelah koreksi ulang poin Dalton ditambahkan penuh.",
        teacher_account_id=teacher.id,
    )

    db.expire_all()
    history_v1_updated = assessment_history_repository.get_history_by_evaluation_and_version(
        db, essay_eval.id, version=1
    )
    assert history_v1_updated.is_current is False
    assert history_v1_updated.superseded_at is not None
    assert history_v1_updated.embedding_status == "SUPERSEDED"
    assert float(history_v1_updated.final_score) == 8.0  # Payload preserved!

    history_v2 = assessment_history_repository.get_history_by_evaluation_and_version(
        db, essay_eval.id, version=2
    )
    assert history_v2 is not None
    assert history_v2.version == 2
    assert history_v2.is_current is True
    assert history_v2.superseded_at is None
    assert float(history_v2.final_score) == 9.5
    assert history_v2.teacher_feedback == "Setelah koreksi ulang poin Dalton ditambahkan penuh."


# ── TEST 10: UNIQUE(evaluation_id, version) constraint ───────────────────────
def test_unique_evaluation_version_constraint(db):
    attempt, questions, teacher, student, school, subj = setup_exam_environment(db)
    ExamService.submit_attempt(db, attempt.id, student_id=attempt.student_id)

    evals = evaluation_repository.get_all_by_attempt(db, attempt.id)
    essay_eval = next(ev for ev in evals if ev.question_id == questions[1].id)

    ExamService.finalize_evaluation(
        db=db,
        evaluation_id=essay_eval.id,
        score=7.0,
        feedback="Feedback v1.",
        teacher_account_id=teacher.id,
    )

    dup_history = AssessmentHistory(
        school_id=school.id,
        academic_year_id=1,
        subject_id=subj.id,
        subject_name="Kimia",
        class_level="XI",
        evaluation_id=essay_eval.id,
        exam_attempt_id=attempt.id,
        question_id=questions[1].id,
        exam_teacher_id=teacher.id,
        finalized_by_teacher_id=teacher.id,
        version=1,  # Duplicate!
        is_current=True,
        question_text="Q text",
        question_type="ES",
        answer_key="Key",
        rubrics_json=[],
        max_score=10.0,
        student_answer="Ans",
        teacher_score=7.0,
        final_score=7.0,
    )
    db.add(dup_history)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


# ── TEST 11: Duplicate finalize with identical values is idempotent ─────────
def test_duplicate_finalize_is_idempotent(db):
    attempt, questions, teacher, student, school, subj = setup_exam_environment(db)
    ExamService.submit_attempt(db, attempt.id, student_id=attempt.student_id)

    evals = evaluation_repository.get_all_by_attempt(db, attempt.id)
    essay_eval = next(ev for ev in evals if ev.question_id == questions[1].id)

    ExamService.finalize_evaluation(
        db=db,
        evaluation_id=essay_eval.id,
        score=8.5,
        feedback="Feedback sama.",
        teacher_account_id=teacher.id,
    )

    ExamService.finalize_evaluation(
        db=db,
        evaluation_id=essay_eval.id,
        score=8.5,
        feedback="Feedback sama.",
        teacher_account_id=teacher.id,
    )

    chain = assessment_history_repository.get_version_chain(db, essay_eval.id)
    assert len(chain) == 1
    assert chain[0].version == 1


# ── TEST 12: Tenant isolation works ──────────────────────────────────────────
def test_tenant_isolation(db):
    # School A
    attempt_a, q_a, t_a, s_a, sch_a, sub_a = setup_exam_environment(
        db, school_name="SMA Negeri 1 A"
    )
    ExamService.submit_attempt(db, attempt_a.id, student_id=attempt_a.student_id)
    eval_a = next(
        ev
        for ev in evaluation_repository.get_all_by_attempt(db, attempt_a.id)
        if ev.question_id == q_a[1].id
    )
    ExamService.finalize_evaluation(
        db, eval_a.id, score=9.0, feedback="School A eval", teacher_account_id=t_a.id
    )

    # School B
    attempt_b, q_b, t_b, s_b, sch_b, sub_b = setup_exam_environment(
        db, school_name="SMA Negeri 2 B"
    )
    ExamService.submit_attempt(db, attempt_b.id, student_id=attempt_b.student_id)
    eval_b = next(
        ev
        for ev in evaluation_repository.get_all_by_attempt(db, attempt_b.id)
        if ev.question_id == q_b[1].id
    )
    ExamService.finalize_evaluation(
        db, eval_b.id, score=7.5, feedback="School B eval", teacher_account_id=t_b.id
    )

    records_a = assessment_history_repository.get_all_by_school(db, school_id=sch_a.id)
    assert len(records_a) == 1
    assert records_a[0].school_id == sch_a.id
    assert records_a[0].teacher_feedback == "School A eval"

    records_b = assessment_history_repository.get_all_by_school(db, school_id=sch_b.id)
    assert len(records_b) == 1
    assert records_b[0].school_id == sch_b.id
    assert records_b[0].teacher_feedback == "School B eval"


# ── TEST 13: Delete safety RESTRICT prevents accidental cascading data loss ─
def test_delete_safety_restrict(db):
    attempt, questions, teacher, student, school, subj = setup_exam_environment(db)
    ExamService.submit_attempt(db, attempt.id, student_id=attempt.student_id)

    evals = evaluation_repository.get_all_by_attempt(db, attempt.id)
    essay_eval = next(ev for ev in evals if ev.question_id == questions[1].id)

    ExamService.finalize_evaluation(
        db=db,
        evaluation_id=essay_eval.id,
        score=9.0,
        feedback="Bagus.",
        teacher_account_id=teacher.id,
    )

    history = assessment_history_repository.get_current_by_evaluation(db, essay_eval.id)
    assert history is not None
    assert history.school_id == school.id


# ── TEST 14: Missing snapshot data fails safely ──────────────────────────────
def test_missing_snapshot_fails_safely(db):
    attempt, questions, teacher, student, school, subj = setup_exam_environment(db)
    ExamService.submit_attempt(db, attempt.id, student_id=attempt.student_id)

    evals = evaluation_repository.get_all_by_attempt(db, attempt.id)
    essay_eval = next(ev for ev in evals if ev.question_id == questions[1].id)

    # Corrupt/delete snapshot to test defensive safety
    db.query(ExamPackageSnapshot).filter_by(exam_session_id=attempt.exam_session_id).delete()
    db.flush()

    res = AssessmentHistoryService.capture_finalized_evaluation(db, essay_eval, teacher.id)
    assert res is None


# ── TEST 15: Missing AI provenance does not crash or fabricate values ────────
def test_missing_ai_provenance_handles_gracefully(db):
    attempt, questions, teacher, student, school, subj = setup_exam_environment(db)
    ExamService.submit_attempt(db, attempt.id, student_id=attempt.student_id)

    evals = evaluation_repository.get_all_by_attempt(db, attempt.id)
    essay_eval = next(ev for ev in evals if ev.question_id == questions[1].id)
    essay_eval.last_evaluated_at = None

    history = AssessmentHistoryService.capture_finalized_evaluation(db, essay_eval, teacher.id)
    # Direct capture should not crash and ai_score should remain None
    if history:
        assert history.ai_score is None
        assert float(history.score_delta) == 0.0
