import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.models.academic.academic_semester import AcademicSemester
from app.models.academic.academic_year import AcademicYear
from app.models.academic.class_entity import ClassEntity
from app.models.academic.enums import AcademicStatus, ExamScheduleStatus, GradingRunStatus
from app.models.academic.exam_schedule import ExamSchedule
from app.models.academic.grading_run import GradingRun
from app.models.academic.subject import Subject
from app.models.exam.enums import ExamAttemptStatus, ExamSessionStatus
from app.models.exam.exam_attempt import ExamAttempt
from app.models.exam.exam_session import ExamSession
from app.models.exam.student_answer import StudentAnswer
from app.models.master.school_level import SchoolLevel
from app.models.school.school import School
from app.models.security.auth_account import AuthAccount
from app.models.security.enums import UserRole
from app.services.academic.exam_schedule_service import ExamScheduleService
from app.services.ai.grading.batch_grading_schema import (
    BatchGradingQuestionRequest,
    BatchGradingQuestionResponse,
    BatchSubmissionItem,
)
from app.services.ai.grading.batch_grading_service import BatchGradingService
from main import app

client = TestClient(app)


def setup_batch_test_environment(db):
    level = db.query(SchoolLevel).first()
    if not level:
        level = SchoolLevel(code="SMA", name="Sekolah Menengah Atas")
        db.add(level)
        db.flush()

    uid = uuid.uuid4().hex[:8]
    school = School(
        name=f"SMA Labschool Batch {uid}",
        code=f"SCH_{uid}",
        domain=f"sch_{uid}.sch.id",
        npsn=f"NPSN_{uid[:6]}",
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

    cls = ClassEntity(
        school_id=school.id,
        academic_year_id=year.id,
        name="XI MIPA 1",
        grade_level="11",
    )
    db.add(cls)
    db.flush()

    subj = Subject(school_id=school.id, code="KIM", name="Kimia")
    db.add(subj)
    db.flush()

    teacher = AuthAccount(
        school_id=school.id,
        username=f"guru_{uid}",
        name="Guru Pengampu Kimia",
        password_hash="fake_hash",
        role=UserRole.TEACHER.value,
        nip=f"NIP_{uid}",
        is_active=True,
    )
    db.add(teacher)
    db.flush()

    return {
        "school": school,
        "year": year,
        "sem": sem,
        "class": cls,
        "subject": subj,
        "teacher": teacher,
    }


def test_batch_grade_question_success():
    mock_llm_data = {
        "results": [
            {
                "student_id": "std_101",
                "feedback": "Penjelasan sangat lengkap dan runtut.",
                "rubric_scores": [
                    {"ku_id": "C1", "achieved": 100},
                    {"ku_id": "C2", "achieved": 80},
                ],
            },
            {
                "student_id": "std_102",
                "feedback": "Cukup baik, tetapi bagian respirasi seluler kurang mendalam.",
                "rubric_scores": [
                    {"ku_id": "C1", "achieved": 60},
                    {"ku_id": "C2", "achieved": 40},
                ],
            },
        ]
    }

    with patch(
        "app.services.ai.shared.llm_client.LlmClient.call_chat_completion",
        return_value={"status": "success", "data": mock_llm_data, "model": "openai/gpt-oss-120b"},
    ):
        req = BatchGradingQuestionRequest(
            question_id=1,
            question_text="Jelaskan peran mitokondria dalam produksi ATP!",
            answer_key="Mitokondria melakukan respirasi seluler untuk sintesis ATP.",
            rubric=[
                {"ku_id": "C1", "text": "Menjelaskan respirasi sel", "weight": 50.0},
                {"ku_id": "C2", "text": "Menjelaskan sintesis ATP", "weight": 50.0},
            ],
            max_score=10.0,
            submissions=[
                BatchSubmissionItem(
                    student_id="std_101",
                    student_answer="Mitokondria melakukan respirasi sel dan menghasilkan ATP.",
                ),
                BatchSubmissionItem(
                    student_id="std_102", student_answer="Mitokondria tempat energi sel."
                ),
                BatchSubmissionItem(student_id="std_103", student_answer="   "),  # Empty answer
            ],
        )

        res = BatchGradingService.grade_question_batch(req)

        assert isinstance(res, BatchGradingQuestionResponse)
        assert res.total_submissions == 3
        assert res.total_evaluated == 3
        assert len(res.results) == 3

        # Student 1: (100*0.5 + 80*0.5) = 90% -> 9.0
        assert res.results[0].student_id == "std_101"
        assert res.results[0].final_score == 90.0
        assert res.results[0].score == 9.0

        # Student 2: (60*0.5 + 40*0.5) = 50% -> 5.0
        assert res.results[1].student_id == "std_102"
        assert res.results[1].final_score == 50.0
        assert res.results[1].score == 5.0

        # Student 3: Empty answer -> 0.0 deterministic
        assert res.results[2].student_id == "std_103"
        assert res.results[2].final_score == 0.0
        assert res.results[2].score == 0.0


def test_batch_grading_missing_student_triggers_retry():
    mock_batch_data = {
        "results": [
            {
                "student_id": "std_201",
                "feedback": "Bagus.",
                "rubric_scores": [{"ku_id": "C1", "achieved": 100}],
            }
        ]
    }
    mock_single_data = {
        "feedback": "Hasil evaluasi retry.",
        "rubric_scores": [{"ku_id": "C1", "achieved": 70}],
    }

    with patch(
        "app.services.ai.shared.llm_client.LlmClient.call_chat_completion",
        side_effect=[
            {"status": "success", "data": mock_batch_data, "model": "openai/gpt-oss-120b"},
            {"status": "success", "data": mock_single_data, "model": "openai/gpt-oss-120b"},
        ],
    ):
        req = BatchGradingQuestionRequest(
            question_id=2,
            question_text="Soal biologi",
            answer_key="Kunci biologi",
            rubric=[{"ku_id": "C1", "text": "Kriteria 1", "weight": 100.0}],
            max_score=10.0,
            submissions=[
                BatchSubmissionItem(student_id="std_201", student_answer="Jawaban 1"),
                BatchSubmissionItem(student_id="std_202", student_answer="Jawaban 2"),
            ],
        )

        res = BatchGradingService.grade_question_batch(req)
        assert res.total_evaluated == 2
        assert res.results[0].student_id == "std_201"
        assert res.results[0].final_score == 100.0
        assert res.results[1].student_id == "std_202"
        assert res.results[1].final_score == 70.0


def test_post_exam_batch_workflow_and_grading_run(db):
    env = setup_batch_test_environment(db)
    now = datetime.now(timezone.utc)
    schedule = ExamSchedule(
        school_id=env["school"].id,
        academic_year_id=env["year"].id,
        academic_semester_id=env["sem"].id,
        class_id=env["class"].id,
        subject_id=env["subject"].id,
        teacher_id=env["teacher"].id,
        title="Ujian Kimia Pasca-Kunci",
        start_time=now - timedelta(hours=2),
        end_time=now - timedelta(minutes=10),
        duration_minutes=90,
        status=ExamScheduleStatus.LOCKED.value,
    )
    db.add(schedule)
    db.commit()

    session = ExamSession(
        schedule_id=schedule.id,
        package_id=1,
        scheduled_start_at=now - timedelta(hours=2),
        scheduled_end_at=now - timedelta(minutes=10),
        duration_minutes=90,
        status=ExamSessionStatus.COMPLETED,
    )
    db.add(session)
    db.commit()

    from app.models.exam.package_snapshot import ExamPackageSnapshot

    snapshot = ExamPackageSnapshot(
        exam_session_id=session.id,
        source_package_id=1,
        school_id=env["school"].id,
        owner_teacher_account_id=env["teacher"].id,
        snapshot_version=1,
        questions_json=[
            {
                "id": 101,
                "type": "ES",
                "content": "Jelaskan hukum perbandingan berganda Dalton!",
                "answer_key": "Massa berbanding bulat sederhana.",
                "rubrics": [{"ku_id": "C1", "text": "Hukum Dalton", "weight": 100.0}],
                "max_score": 10.0,
            }
        ],
    )
    db.add(snapshot)
    db.commit()

    att1 = ExamAttempt(
        exam_session_id=session.id,
        student_id=501,
        status=ExamAttemptStatus.SUBMITTED,
        randomized_order=[101],
    )
    att2 = ExamAttempt(
        exam_session_id=session.id,
        student_id=502,
        status=ExamAttemptStatus.SUBMITTED,
        randomized_order=[101],
    )
    db.add_all([att1, att2])
    db.commit()

    ans1 = StudentAnswer(
        exam_attempt_id=att1.id,
        question_id=101,
        text_answer="Perbandingan bulat sederhana.",
        last_updated_at=now,
    )
    ans2 = StudentAnswer(
        exam_attempt_id=att2.id,
        question_id=101,
        text_answer="Massa tetap sama.",
        last_updated_at=now,
    )
    db.add_all([ans1, ans2])
    db.commit()

    mock_llm_data = {
        "results": [
            {
                "student_id": "501",
                "feedback": "Sangat tepat.",
                "rubric_scores": [{"ku_id": "C1", "achieved": 100}],
            },
            {
                "student_id": "502",
                "feedback": "Salah konsep.",
                "rubric_scores": [{"ku_id": "C1", "achieved": 20}],
            },
        ]
    }

    with patch(
        "app.services.ai.shared.llm_client.LlmClient.call_chat_completion",
        return_value={"status": "success", "data": mock_llm_data, "model": "openai/gpt-oss-120b"},
    ):
        run = BatchGradingService.start_post_exam_grading(db, schedule.id)

        assert isinstance(run, GradingRun)
        assert run.status == GradingRunStatus.COMPLETED.value
        assert run.total_questions == 1
        assert run.total_submissions == 2
        assert run.processed_batches == 1

        db.refresh(att1)
        db.refresh(att2)
        assert att1.status == ExamAttemptStatus.GRADED
        assert att1.final_score == 100.0
        assert att2.status == ExamAttemptStatus.GRADED
        assert att2.final_score == 20.0


def test_reopen_exam_cancels_active_grading_run(db):
    env = setup_batch_test_environment(db)
    now = datetime.now(timezone.utc)
    schedule = ExamSchedule(
        school_id=env["school"].id,
        academic_year_id=env["year"].id,
        academic_semester_id=env["sem"].id,
        class_id=env["class"].id,
        subject_id=env["subject"].id,
        teacher_id=env["teacher"].id,
        title="Ujian Terkunci Reopen Test",
        start_time=now - timedelta(hours=2),
        end_time=now - timedelta(minutes=5),
        duration_minutes=90,
        status=ExamScheduleStatus.LOCKED.value,
    )
    db.add(schedule)
    db.commit()

    run = GradingRun(
        id=uuid.uuid4(),
        exam_schedule_id=schedule.id,
        status=GradingRunStatus.PROCESSING.value,
    )
    db.add(run)
    db.commit()

    # Reopen exam
    reopened = ExamScheduleService.reopen_exam_schedule(
        db, school_id=env["school"].id, public_id=schedule.public_id, extended_minutes=20
    )

    assert reopened.status == ExamScheduleStatus.ACTIVE.value
    db.refresh(run)
    assert run.status == GradingRunStatus.CANCELLED.value
    assert run.cancelled_at is not None


def test_extend_exam_schedule_on_time_ended(db):
    env = setup_batch_test_environment(db)
    now = datetime.now(timezone.utc)
    schedule = ExamSchedule(
        school_id=env["school"].id,
        academic_year_id=env["year"].id,
        academic_semester_id=env["sem"].id,
        class_id=env["class"].id,
        subject_id=env["subject"].id,
        teacher_id=env["teacher"].id,
        title="Ujian Extend Time Ended",
        start_time=now - timedelta(hours=2),
        end_time=now - timedelta(minutes=1),
        duration_minutes=90,
        status=ExamScheduleStatus.TIME_ENDED.value,
    )
    db.add(schedule)
    db.commit()

    new_end = now + timedelta(minutes=45)
    extended = ExamScheduleService.extend_exam_schedule(
        db, school_id=env["school"].id, public_id=schedule.public_id, new_end_time=new_end
    )

    assert extended.status == ExamScheduleStatus.ACTIVE.value


def test_api_batch_grade_question_endpoint():
    from app.core.dependencies import get_current_user

    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "1",
        "role": "TEACHER",
        "school_id": 1,
    }
    mock_llm_data = {
        "results": [
            {
                "student_id": "std_1",
                "feedback": "Tepat.",
                "rubric_scores": [{"ku_id": "C1", "achieved": 100}],
            }
        ]
    }

    try:
        with patch(
            "app.services.ai.shared.llm_client.LlmClient.call_chat_completion",
            return_value={
                "status": "success",
                "data": mock_llm_data,
                "model": "openai/gpt-oss-120b",
            },
        ):
            response = client.post(
                "/api/v1/ai/grading/batch-question",
                json={
                    "question_id": 99,
                    "question_text": "Jelaskan hukum gravitasi!",
                    "answer_key": "Gaya tarik berbanding terbalik kuadrat jarak.",
                    "rubric": [{"ku_id": "C1", "text": "Hukum gravitasi", "weight": 100.0}],
                    "submissions": [
                        {
                            "student_id": "std_1",
                            "student_answer": "Gaya tarik antara dua massa berbanding terbalik kuadrat jarak.",
                        }
                    ],
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["total_evaluated"] == 1
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        assert data["results"][0]["final_score"] == 100.0


def test_failed_batch_student_does_not_commit_zero_and_keeps_attempt_incomplete(db):
    env = setup_batch_test_environment(db)
    now = datetime.now(timezone.utc)
    schedule = ExamSchedule(
        school_id=env["school"].id,
        academic_year_id=env["year"].id,
        academic_semester_id=env["sem"].id,
        class_id=env["class"].id,
        subject_id=env["subject"].id,
        teacher_id=env["teacher"].id,
        title="Ujian Integrity Partial Test",
        start_time=now - timedelta(hours=2),
        end_time=now - timedelta(minutes=10),
        duration_minutes=90,
        status=ExamScheduleStatus.LOCKED.value,
    )
    db.add(schedule)
    db.commit()

    session = ExamSession(
        schedule_id=schedule.id,
        package_id=1,
        scheduled_start_at=now - timedelta(hours=2),
        scheduled_end_at=now - timedelta(minutes=10),
        duration_minutes=90,
        status=ExamSessionStatus.COMPLETED,
    )
    db.add(session)
    db.commit()

    from app.models.exam.package_snapshot import ExamPackageSnapshot

    snapshot = ExamPackageSnapshot(
        exam_session_id=session.id,
        source_package_id=1,
        school_id=env["school"].id,
        owner_teacher_account_id=env["teacher"].id,
        snapshot_version=1,
        questions_json=[
            {
                "id": 201,
                "type": "ES",
                "content": "Jelaskan hukum Termodinamika 1!",
                "answer_key": "Energi tidak dapat diciptakan atau dimusnahkan.",
                "rubrics": [{"ku_id": "C1", "text": "Kekekalan energi", "weight": 100.0}],
                "max_score": 10.0,
            }
        ],
    )
    db.add(snapshot)
    db.commit()

    att1 = ExamAttempt(
        exam_session_id=session.id,
        student_id=701,
        status=ExamAttemptStatus.SUBMITTED,
        randomized_order=[201],
    )
    att2 = ExamAttempt(
        exam_session_id=session.id,
        student_id=702,
        status=ExamAttemptStatus.SUBMITTED,
        randomized_order=[201],
    )
    db.add_all([att1, att2])
    db.commit()

    ans1 = StudentAnswer(
        exam_attempt_id=att1.id,
        question_id=201,
        text_answer="Energi bersifat kekal.",
        last_updated_at=now,
    )
    ans2 = StudentAnswer(
        exam_attempt_id=att2.id,
        question_id=201,
        text_answer="Energi bisa hilang jadi panas.",
        last_updated_at=now,
    )
    db.add_all([ans1, ans2])
    db.commit()

    # LLM returns ONLY student 701, completely omitting student 702.
    mock_batch_data = {
        "results": [
            {
                "student_id": "701",
                "feedback": "Benar.",
                "rubric_scores": [{"ku_id": "C1", "achieved": 100}],
            }
        ]
    }

    # Simulate targeted retry failure for student 702
    with patch(
        "app.services.ai.shared.llm_client.LlmClient.call_chat_completion",
        side_effect=[
            {"status": "success", "data": mock_batch_data, "model": "openai/gpt-oss-120b"},
            RuntimeError("Rate limit / timeout during single student retry"),
        ],
    ):
        run = BatchGradingService.start_post_exam_grading(db, schedule.id)

        # Run is marked PARTIAL because student 702 could not be graded
        assert run.status == GradingRunStatus.PARTIAL.value

        db.refresh(att1)
        db.refresh(att2)
        # Att1 was successfully graded
        assert att1.status == ExamAttemptStatus.GRADED
        assert att1.final_score == 100.0

        # Att2 was NOT marked GRADED and score 0.0 was NOT committed
        assert att2.status == ExamAttemptStatus.GRADING
        from app.repositories.exam.evaluation_repository import evaluation_repository

        eval2 = evaluation_repository.get_by_attempt_and_question_with_lock(db, att2.id, 201)
        assert eval2 is None  # Evaluation was safely omitted, preventing fake 0.0 grade
