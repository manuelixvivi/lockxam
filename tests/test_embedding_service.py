import math
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.models.academic.academic_semester import AcademicSemester
from app.models.academic.academic_year import AcademicYear
from app.models.academic.enums import AcademicStatus
from app.models.exam.enums import (
    ExamAttemptStatus,
    ExamSessionStatus,
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
from app.services.academic.class_service import ClassService
from app.services.academic.class_structure_service import ClassStructureService
from app.services.academic.exam_schedule_service import ExamScheduleService
from app.services.academic.exam_snapshot_service import ExamSnapshotService
from app.services.academic.subject_service import SubjectService
from app.services.ai.assessment_document_service import AssessmentDocumentService
from app.services.ai.embedding_service import EmbeddingService
from app.services.exam.exam_service import ExamService


def setup_assessment_history_fixture(db, school_name="SMA Labschool AI"):
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

    pkg = QuestionPackage(
        owner_teacher_account_id=guru.id,
        school_id=school.id,
        name="Paket Ujian Kimia",
        class_level="XI",
        target_counts={"ES": 1},
        subject="Kimia",
        status=PackageStatus.READY.value,
    )
    db.add(pkg)
    db.flush()

    q_es = Question(
        owner_teacher_account_id=guru.id,
        type=QuestionType.ES,
        content="Jelaskan Hukum Perbandingan Berganda Dalton!",
        options=None,
        answer_key="Bila dua unsur membentuk dua senyawa atau lebih...",
        rubrics=[{"name": "Konsep", "points": 5}],
        subject="Kimia",
        class_level="XI",
        ai_grading=True,
    )
    db.add(q_es)
    db.flush()

    item_es = QuestionPackageItem(
        package_id=pkg.id,
        question_id=q_es.id,
        canonical_order=1,
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

    pkg_snapshot = ExamPackageSnapshot(
        exam_session_id=session.id,
        source_package_id=pkg.id,
        school_id=school.id,
        owner_teacher_account_id=guru.id,
        snapshot_version=1,
        questions_json=[
            {
                "id": q_es.id,
                "question_id": q_es.id,
                "type": "ES",
                "content": str(q_es.content),
                "options": [],
                "answer_key": q_es.answer_key,
                "rubrics": q_es.rubrics or [],
                "ai_grading": True,
                "max_score": 10.0,
                "subject": "Kimia",
                "class_level": "XI",
            }
        ],
    )
    db.add(pkg_snapshot)
    db.flush()

    attempt = ExamAttempt(
        exam_session_id=session.id,
        student_id=student.id,
        status=ExamAttemptStatus.IN_PROGRESS,
        randomized_order=[q_es.id],
    )
    db.add(attempt)
    db.flush()

    ans = StudentAnswer(
        exam_attempt_id=attempt.id,
        question_id=q_es.id,
        selected_option=None,
        text_answer="Hukum Dalton menyatakan perbandingan massa unsur yang bergabung adalah bulat dan sederhana.",
        last_updated_at=datetime.now(timezone.utc),
    )
    db.add(ans)
    db.flush()

    ExamService.submit_attempt(db, attempt.id, student_id=attempt.student_id)
    eval_item = ExamService.finalize_evaluation(
        db=db,
        evaluation_id=attempt.evaluations[0].id,
        score=9.0,
        feedback="Penjelasan sangat akurat.",
        teacher_account_id=guru.id,
    )

    history = assessment_history_repository.get_current_by_evaluation(db, eval_item.id)
    return history, guru, attempt


# ── TEST 1: Model loads successfully ─────────────────────────────────────────
def test_model_loads_successfully():
    model = EmbeddingService.get_model()
    assert model is not None


# ── TEST 2: Passage prefix applied exactly once ──────────────────────────────
def test_passage_prefix_applied_exactly_once():
    raw_text = "Hukum Dalton tentang perbandingan massa."
    vec1 = EmbeddingService.encode_passage(raw_text)
    vec2 = EmbeddingService.encode_passage(f"passage: {raw_text}")

    assert len(vec1) == 1024
    assert len(vec2) == 1024
    assert math.isclose(sum(a * b for a, b in zip(vec1, vec2, strict=False)), 1.0, rel_tol=1e-4)


# ── TEST 3: Query prefix applied exactly once ────────────────────────────────
def test_query_prefix_applied_exactly_once():
    raw_query = "Apa bunyi Hukum Dalton?"
    vec1 = EmbeddingService.encode_query(raw_query)
    vec2 = EmbeddingService.encode_query(f"query: {raw_query}")

    assert len(vec1) == 1024
    assert len(vec2) == 1024
    assert math.isclose(sum(a * b for a, b in zip(vec1, vec2, strict=False)), 1.0, rel_tol=1e-4)


# ── TEST 4: Embedding dimension is correct (1024) ────────────────────────────
def test_embedding_dimension_is_1024():
    config = EmbeddingService.get_config()
    assert config["dimension"] == 1024
    vec = EmbeddingService.encode_passage("Contoh teks asesmen kimia.")
    assert len(vec) == 1024


# ── TEST 5: Output is finite (No NaN / Inf) ──────────────────────────────────
def test_output_is_finite():
    vec = EmbeddingService.encode_passage("Uji finite float.")
    for val in vec:
        assert not math.isnan(val)
        assert not math.isinf(val)
        assert isinstance(val, float)


# ── TEST 6: Normalized vector norm is approximately 1.0 ──────────────────────
def test_normalized_vector_l2_norm():
    vec = EmbeddingService.encode_passage("Verifikasi L2 unit norm.")
    l2_norm = math.sqrt(sum(x * x for x in vec))
    assert math.isclose(l2_norm, 1.0, rel_tol=1e-5)


# ── TEST 7: Same input produces equivalent embedding ────────────────────────
def test_same_input_reproducible_embedding():
    text = "Hukum Lavoisier: Massa zat sebelum dan sesudah reaksi adalah sama."
    vec1 = EmbeddingService.encode_passage(text)
    vec2 = EmbeddingService.encode_passage(text)
    assert vec1 == vec2


# ── TEST 8: Different semantic text produces different embedding ─────────────
def test_different_text_produces_different_embedding():
    vec_chem = EmbeddingService.encode_passage("Hukum Lavoisier dan Dalton dalam reaksi kimia.")
    vec_bio = EmbeddingService.encode_passage(
        "Mitokondria adalah organel respirasi sel penghasil ATP."
    )

    assert vec_chem != vec_bio
    cosine_sim = sum(a * b for a, b in zip(vec_chem, vec_bio, strict=False))
    assert cosine_sim < 0.99


# ── TEST 9: Batch encoding works ─────────────────────────────────────────────
def test_batch_encoding():
    texts = [
        "Soal 1: Termokimia endoterm dan eksoterm.",
        "Soal 2: Laju reaksi dan energi aktivasi.",
        "Soal 3: Kesetimbangan kimia dinamis.",
    ]
    batch_vecs = EmbeddingService.encode_batch(texts, is_query=False)
    assert len(batch_vecs) == 3
    for v in batch_vecs:
        assert len(v) == 1024


# ── TEST 10: Empty input rejected safely ─────────────────────────────────────
def test_empty_input_rejected_safely():
    with pytest.raises(ValueError):
        EmbeddingService.encode_passage("   ")
    with pytest.raises(ValueError):
        EmbeddingService.encode_query("")


# ── TEST 11: Oversized input detected via token count measurement ───────────
def test_oversized_input_token_measurement():
    huge_text = "Hukum dasar kimia " * 600
    token_count = EmbeddingService.estimate_token_count(huge_text)
    assert token_count > 512


# ── TEST 12: PII is not stored in embedding metadata ─────────────────────────
def test_pii_excluded_from_embedding_metadata(db):
    hist, guru, attempt = setup_assessment_history_fixture(db)
    doc = AssessmentDocumentService.construct_canonical_document(hist)
    embedding = EmbeddingService.embed_and_persist_history(db, hist)

    assert embedding.school_id == hist.school_id
    assert embedding.subject_id == hist.subject_id
    assert embedding.class_level == "XI"
    assert embedding.version == 1
    assert embedding.content_hash == doc.content_hash

    # Ensure no student identifiers on embedding object
    assert not hasattr(embedding, "student_name")
    assert not hasattr(embedding, "student_nisn")
    assert not hasattr(embedding, "ip_address")


# ── TEST 13: Content hash prevents unnecessary re-embedding ──────────────────
def test_content_hash_idempotency(db):
    hist, guru, attempt = setup_assessment_history_fixture(db)
    emb1 = EmbeddingService.embed_and_persist_history(db, hist)
    emb2 = EmbeddingService.embed_and_persist_history(db, hist)

    assert emb1.id == emb2.id
    assert emb1.content_hash == emb2.content_hash


# ── TEST 14: v1 and v2 remain independently traceable ────────────────────────
def test_v1_and_v2_independently_traceable(db):
    hist_v1, guru, attempt = setup_assessment_history_fixture(db)
    emb_v1 = EmbeddingService.embed_and_persist_history(db, hist_v1)

    # Re-finalize creates v2
    ExamService.finalize_evaluation(
        db=db,
        evaluation_id=attempt.evaluations[0].id,
        score=10.0,
        feedback="Penyempurnaan feedback Dalton.",
        teacher_account_id=guru.id,
    )
    hist_v2 = assessment_history_repository.get_current_by_evaluation(db, attempt.evaluations[0].id)
    emb_v2 = EmbeddingService.embed_and_persist_history(db, hist_v2)

    db.expire_all()
    # v1 is superseded
    assert emb_v1.version == 1
    assert emb_v1.is_current is False
    # v2 is active
    assert emb_v2.version == 2
    assert emb_v2.is_current is True
    assert emb_v1.id != emb_v2.id


# ── TEST 15: Model configuration is not hardcoded ───────────────────────────
def test_model_configuration_configurable():
    config = EmbeddingService.get_config()
    assert "model_name" in config
    assert "device" in config
    assert "batch_size" in config
    assert config["model_name"] == "intfloat/multilingual-e5-large"


# ── TEST 16: Small performance benchmark ────────────────────────────────────
def test_embedding_performance_benchmark():
    sample_docs = [
        "passage: [Mata Pelajaran]: Kimia\n\n[Soal]: Jelaskan entalpi pembentukan standar!",
        "passage: [Mata Pelajaran]: Fisika\n\n[Soal]: Jelaskan Hukum II Newton tentang gerak!",
        "passage: [Mata Pelajaran]: Biologi\n\n[Soal]: Jelaskan perbedaan mitosis dan meiosis!",
    ]
    t0 = time.perf_counter()
    vecs = EmbeddingService.encode_batch(sample_docs)
    elapsed = time.perf_counter() - t0

    assert len(vecs) == 3
    assert elapsed < 5.0


# ── TEST 17: Engine Provenance and Transparency ─────────────────────────────
def test_engine_info_provenance_transparency():
    info = EmbeddingService.get_engine_info()
    assert "model_name" in info
    assert "engine_type" in info
    assert "is_neural_transformer" in info
    assert info["model_name"] == "intfloat/multilingual-e5-large"
    assert info["dimension"] == 1024
    assert info["normalization"] == "L2 (Unit Euclidean)"


# ── TEST 18: Strict Transformer Mode Enforcement ────────────────────────────
def test_strict_transformer_mode():
    config = EmbeddingService.get_config()
    assert "strict_transformer" in config
    # In fallback mock mode, strict requirement raises RuntimeError
    if not EmbeddingService.is_neural_engine_available():
        with pytest.raises(RuntimeError, match="STRICT_TRANSFORMER"):
            EmbeddingService.get_model(require_transformer=True)
