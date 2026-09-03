import math
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.models.academic.academic_semester import AcademicSemester
from app.models.academic.academic_year import AcademicYear
from app.models.academic.enums import AcademicStatus
from app.models.ai.assessment_embedding import AssessmentEmbedding
from app.models.ai.assessment_history import AssessmentHistory
from app.models.exam.answer_evaluation import ExamAnswerEvaluation
from app.models.exam.enums import (
    ExamAttemptStatus,
    ExamSessionStatus,
    GradingSource,
    GradingStatus,
)
from app.models.exam.exam_attempt import ExamAttempt
from app.models.exam.exam_session import ExamSession
from app.models.master.school_level import SchoolLevel
from app.models.school.school import School
from app.models.security.auth_account import AuthAccount
from app.models.security.enums import UserRole
from app.models.teacher.enums import PackageStatus, QuestionType
from app.models.teacher.question import Question
from app.models.teacher.question_package import QuestionPackage
from app.services.academic.class_service import ClassService
from app.services.academic.class_structure_service import ClassStructureService
from app.services.academic.exam_schedule_service import ExamScheduleService
from app.services.academic.subject_service import SubjectService
from app.services.ai.assessment_document_service import AssessmentDocumentService
from app.services.ai.benchmark_evaluation_service import (
    BenchmarkEvaluationService,
)
from app.services.ai.embedding_service import EmbeddingService


def create_benchmark_db_environment(db):
    """Sets up a clean multi-tenant test environment."""
    level = db.query(SchoolLevel).first()
    if not level:
        level = SchoolLevel(code="SMA", name="Sekolah Menengah Atas")
        db.add(level)
        db.flush()

    code_a = f"SCH_BNCH_{uuid4().hex[:6]}"
    school = School(
        name="SMA 1 Benchmark Jakarta",
        code=code_a,
        domain=f"{code_a.lower()}.sch.id",
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
    subj_kim = SubjectService.create_subject(db, school.id, code="KIM", name="Kimia")

    teacher = AuthAccount(
        school_id=school.id,
        username=f"guru_{uuid4().hex[:6]}",
        name="Guru Kimia",
        password_hash="fake_hash",
        role=UserRole.TEACHER.value,
        nip=f"19850101{uuid4().hex[:6]}",
        is_active=True,
    )
    student = AuthAccount(
        school_id=school.id,
        username=f"siswa_{uuid4().hex[:6]}",
        name="Siswa Uji",
        password_hash="fake_hash",
        role=UserRole.STUDENT.value,
        nisn=f"098{uuid4().hex[:6]}",
        is_active=True,
    )
    db.add_all([teacher, student])
    db.flush()

    SubjectService.assign_teacher_competency(db, school.id, teacher.id, subj_kim.id)
    ClassStructureService.assign_teacher_to_class_subject(
        db, school.id, cls.id, subj_kim.id, teacher.id
    )
    ClassStructureService.enroll_student_to_class(db, school.id, student.id, cls.id)

    return {
        "school": school,
        "year": year,
        "sem": sem,
        "cls": cls,
        "subj_kim": subj_kim,
        "teacher": teacher,
        "student": student,
        "_schedule_offset": 1,
    }


def populate_knowledge_base_presets(db, env):
    """Indexes benchmark knowledge presets into the Vector Store."""
    presets = BenchmarkEvaluationService.get_benchmark_knowledge_corpus()
    indexed_records = []

    for preset in presets:
        offset = env.get("_schedule_offset", 1)
        env["_schedule_offset"] = offset + 1
        base_time = datetime.now(timezone.utc) + timedelta(days=offset * 2)

        pkg = QuestionPackage(
            owner_teacher_account_id=env["teacher"].id,
            school_id=env["school"].id,
            name=f"Paket {preset.subject_name} {uuid4().hex[:4]}",
            class_level=preset.class_level,
            target_counts={"ES": 1},
            subject=preset.subject_name,
            status=PackageStatus.READY.value,
        )
        db.add(pkg)
        db.flush()

        q = Question(
            owner_teacher_account_id=env["teacher"].id,
            type=QuestionType.ES,
            content=preset.question_text,
            options=None,
            answer_key=preset.answer_key,
            rubrics=preset.rubrics_json,
            subject=preset.subject_name,
            class_level=preset.class_level,
            ai_grading=True,
        )
        db.add(q)
        db.flush()

        schedule = ExamScheduleService.create_exam_schedule(
            db,
            school_id=env["school"].id,
            academic_year_id=env["year"].id,
            academic_semester_id=env["sem"].id,
            class_id=env["cls"].id,
            subject_id=env["subj_kim"].id,
            title=f"Ujian {preset.subject_name} {uuid4().hex[:4]}",
            start_time=base_time,
            end_time=base_time + timedelta(hours=1),
            duration_minutes=60,
        )

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

        attempt = ExamAttempt(
            exam_session_id=session.id,
            student_id=env["student"].id,
            status=ExamAttemptStatus.SUBMITTED,
            randomized_order=[q.id],
        )
        db.add(attempt)
        db.flush()

        evaluation = ExamAnswerEvaluation(
            exam_attempt_id=attempt.id,
            question_id=q.id,
            score=preset.teacher_score,
            max_score=preset.max_score,
            feedback=preset.teacher_feedback,
            grading_status=GradingStatus.FINALIZED,
            grading_source=GradingSource.TEACHER,
            grading_version=1,
            last_evaluated_at=base_time,
        )
        db.add(evaluation)
        db.flush()

        history = AssessmentHistory(
            school_id=env["school"].id,
            academic_year_id=env["year"].id,
            subject_id=env["subj_kim"].id,
            subject_name=preset.subject_name,
            class_level=preset.class_level,
            evaluation_id=evaluation.id,
            exam_attempt_id=attempt.id,
            question_id=q.id,
            exam_teacher_id=env["teacher"].id,
            finalized_by_teacher_id=env["teacher"].id,
            version=1,
            is_current=True,
            question_text=preset.question_text,
            question_type="ES",
            answer_key=preset.answer_key,
            rubrics_json=preset.rubrics_json,
            max_score=preset.max_score,
            student_answer=preset.student_answer,
            teacher_score=preset.teacher_score,
            teacher_feedback=preset.teacher_feedback,
            final_score=preset.teacher_score,
            score_delta=0.0,
            is_rag_eligible=True,
            embedding_status="EMBEDDED",
            embedded_at=base_time,
        )
        db.add(history)
        db.flush()

        doc = AssessmentDocumentService.construct_canonical_document(history)
        vector = EmbeddingService.encode_passage(doc.e5_passage_text)

        embedding = AssessmentEmbedding(
            assessment_history_id=history.id,
            version=1,
            is_current=True,
            content_hash=doc.content_hash,
            school_id=env["school"].id,
            academic_year_id=env["year"].id,
            subject_id=env["subj_kim"].id,
            class_level=preset.class_level,
            embedding_model="intfloat/multilingual-e5-large",
            dimension=1024,
            vector_data=vector,
        )
        db.add(embedding)
        db.flush()

        history.vector_id = str(embedding.id)
        db.flush()
        indexed_records.append((history, embedding))

    return indexed_records


# ── TEST 1: Statistical MAE Calculation ──────────────────────────────────────
def test_mae_calculation():
    preds = [90.0, 80.0, 70.0, 100.0]
    gts = [95.0, 80.0, 65.0, 90.0]
    # |90-95| + |80-80| + |70-65| + |100-90| = 5 + 0 + 5 + 10 = 20 / 4 = 5.0
    mae = BenchmarkEvaluationService.calculate_mae(preds, gts)
    assert math.isclose(mae, 5.0, abs_tol=1e-5)


# ── TEST 2: Statistical RMSE Calculation ─────────────────────────────────────
def test_rmse_calculation():
    preds = [90.0, 80.0, 70.0, 100.0]
    gts = [95.0, 80.0, 65.0, 90.0]
    # (25 + 0 + 25 + 100) / 4 = 150 / 4 = 37.5 -> sqrt(37.5) = 6.1237
    rmse = BenchmarkEvaluationService.calculate_rmse(preds, gts)
    assert math.isclose(rmse, math.sqrt(37.5), abs_tol=1e-4)


# ── TEST 3: Pearson Linear Correlation r Calculation ─────────────────────────
def test_pearson_correlation_calculation():
    x = [10.0, 20.0, 30.0, 40.0, 50.0]
    y = [15.0, 25.0, 35.0, 45.0, 55.0]
    r = BenchmarkEvaluationService.calculate_pearson_correlation(x, y)
    assert math.isclose(r, 1.0, abs_tol=1e-4)


# ── TEST 4: Spearman Rank Correlation rho Calculation ────────────────────────
def test_spearman_correlation_calculation():
    x = [1.0, 2.0, 3.0, 4.0, 5.0]
    y = [5.0, 6.0, 7.0, 8.0, 7.0]
    rho = BenchmarkEvaluationService.calculate_spearman_correlation(x, y)
    assert 0.8 <= rho <= 1.0


# ── TEST 5: Tolerance Agreement Calculation ──────────────────────────────────
def test_tolerance_agreement_calculation():
    preds = [90.0, 84.0, 70.0, 95.0]
    gts = [92.0, 80.0, 65.0, 100.0]
    # abs diff: 2 (<=5), 4 (<=5), 5 (<=5), 5 (<=5) -> 4/4 = 100%
    agree5 = BenchmarkEvaluationService.calculate_tolerance_agreement(preds, gts, tolerance=5.0)
    assert agree5 == 100.0


# ── TEST 6: Feedback Quality Rubric Scoring ──────────────────────────────────
def test_feedback_quality_rubric_scoring():
    fb = "Jawaban sudah tepat karena menjelaskan klorofil dan pelepasan oksigen. Sebaiknya pertahankan pemahaman ini."
    gt = "Penjelasan sangat lengkap mencakup klorofil."
    rubrics = [{"name": "Klorofil"}]

    scores = BenchmarkEvaluationService.evaluate_feedback_rubric(fb, gt, rubrics)
    assert scores["correctness"] == 2.0
    assert scores["relevance"] == 2.0
    assert scores["explanation"] == 2.0
    assert scores["actionability"] == 2.0
    assert scores["average_feedback_score"] >= 1.8


# ── TEST 7: Strict Data Split Separation (Zero Data Leakage) ─────────────────
def test_data_split_separation_zero_leakage():
    knowledge_presets = BenchmarkEvaluationService.get_benchmark_knowledge_corpus()
    test_samples = BenchmarkEvaluationService.get_benchmark_evaluation_test_set()

    kb_texts = {k.student_answer.strip() for k in knowledge_presets}
    test_texts = {t.student_answer.strip() for t in test_samples}

    # Strict assertion: Test set answers MUST NEVER intersect with Knowledge Base
    intersection = kb_texts.intersection(test_texts)
    assert len(intersection) == 0


def mock_benchmark_microservice_response(req, *args, **kwargs):
    """Deterministic fast mock response for benchmark test suite."""
    import json

    data = json.loads(req.data.decode("utf-8"))
    rag_context = data.get("rag_context", "")
    ans = data.get("student_answer", "")

    # Realistic scoring based on essay length & key presence
    score = (
        90.0
        if "dalton" in ans.lower() or "oksigen" in ans.lower() or "kalor" in ans.lower()
        else 75.0
    )
    if rag_context:
        score = min(100.0, score + 5.0)  # RAG context provides small positive adjustment

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_body = {
        "status": "success",
        "final_score": score,
        "decision": {"final_score": score, "status": "EVALUATED"},
        "feedback": "Penjelasan mencakup konsep utama dengan runtut. Tingkatkan penjelasan detail.",
        "rubric_scores": [{"ku_id": "ku_1", "achieved": int(score)}],
        "rag_applied": bool(rag_context.strip()),
    }
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.read.return_value = json.dumps(mock_body).encode("utf-8")
    return mock_resp


# ── TEST 8: Comparative Benchmark Execution on Test Set ──────────────────────
def test_comparative_benchmark_execution(db):
    env = create_benchmark_db_environment(db)
    populate_knowledge_base_presets(db, env)

    with (
        patch.dict(os.environ, {"RAG_ENABLED": "true"}),
        patch("urllib.request.urlopen", side_effect=mock_benchmark_microservice_response),
    ):
        results = BenchmarkEvaluationService.execute_comparative_benchmark(
            db=db,
            school_id=env["school"].id,
            subject_id=env["subj_kim"].id,
            academic_year_id=env["year"].id,
            similarity_threshold=-1.0,
            top_k=3,
        )

        assert results["sample_count"] >= 6
        metrics = results["metrics"]
        assert "mae" in metrics
        assert "rmse" in metrics
        assert "pearson_correlation" in metrics
        assert "agreement_within_5_points" in metrics
        assert "average_latency_ms" in metrics
        assert len(results["sample_evaluations"]) >= 6


# ── TEST 9: Multi-Threshold Parametric Sweep Execution ───────────────────────
def test_multi_threshold_sweep_execution(db):
    env = create_benchmark_db_environment(db)
    populate_knowledge_base_presets(db, env)

    with (
        patch.dict(os.environ, {"RAG_ENABLED": "true"}),
        patch("urllib.request.urlopen", side_effect=mock_benchmark_microservice_response),
    ):
        sweep_results = BenchmarkEvaluationService.execute_threshold_sweep(
            db=db,
            school_id=env["school"].id,
            subject_id=env["subj_kim"].id,
            academic_year_id=env["year"].id,
            thresholds=[0.50, 0.70, 0.80],
        )

        assert len(sweep_results) == 3
        for item in sweep_results:
            assert "threshold" in item
            assert "mae_rag" in item
            assert "rmse_rag" in item
            assert "avg_retrieved_cases" in item


# ── TEST 10: Top-K Parametric Sweep Execution ────────────────────────────────
def test_top_k_sweep_execution(db):
    env = create_benchmark_db_environment(db)
    populate_knowledge_base_presets(db, env)

    with (
        patch.dict(os.environ, {"RAG_ENABLED": "true"}),
        patch("urllib.request.urlopen", side_effect=mock_benchmark_microservice_response),
    ):
        sweep_results = BenchmarkEvaluationService.execute_top_k_sweep(
            db=db,
            school_id=env["school"].id,
            subject_id=env["subj_kim"].id,
            academic_year_id=env["year"].id,
            top_k_values=[1, 3, 5],
        )

        assert len(sweep_results) == 3
        for item in sweep_results:
            assert "top_k" in item
            assert "mae_rag" in item
            assert "avg_latency_ms" in item
