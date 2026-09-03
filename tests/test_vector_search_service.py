import math
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

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
from app.services.ai.embedding_service import EmbeddingService
from app.services.ai.vector_search_service import (
    SimilarAssessmentResult,
    VectorSearchService,
)


def create_vector_test_environment(db):
    """Creates a multi-tenant test environment with School A and School B with valid DB lineage."""
    level = db.query(SchoolLevel).first()
    if not level:
        level = SchoolLevel(code="SMA", name="Sekolah Menengah Atas")
        db.add(level)
        db.flush()

    # School A
    code_a = f"SCH_A_{uuid4().hex[:6]}"
    school_a = School(
        name="SMA Negeri 1 Jakarta",
        code=code_a,
        domain=f"{code_a.lower()}.sch.id",
        npsn=f"NPSN_{uuid4().hex[:6]}",
        school_level_id=level.id,
        is_active=True,
    )
    # School B
    code_b = f"SCH_B_{uuid4().hex[:6]}"
    school_b = School(
        name="SMA Negeri 2 Bandung",
        code=code_b,
        domain=f"{code_b.lower()}.sch.id",
        npsn=f"NPSN_{uuid4().hex[:6]}",
        school_level_id=level.id,
        is_active=True,
    )
    db.add_all([school_a, school_b])
    db.flush()

    now = datetime.now(timezone.utc)
    year_a = AcademicYear(
        school_id=school_a.id,
        name="2026/2027",
        start_date=now,
        end_date=now + timedelta(days=365),
        status=AcademicStatus.ACTIVE.value,
    )
    year_b = AcademicYear(
        school_id=school_b.id,
        name="2026/2027",
        start_date=now,
        end_date=now + timedelta(days=365),
        status=AcademicStatus.ACTIVE.value,
    )
    db.add_all([year_a, year_b])
    db.flush()

    sem_a = AcademicSemester(
        academic_year_id=year_a.id,
        code="GANJIL",
        display_name="Semester Ganjil",
        status=AcademicStatus.ACTIVE.value,
    )
    sem_b = AcademicSemester(
        academic_year_id=year_b.id,
        code="GANJIL",
        display_name="Semester Ganjil",
        status=AcademicStatus.ACTIVE.value,
    )
    db.add_all([sem_a, sem_b])
    db.flush()

    cls_a = ClassService.create_class(db, school_a.id, year_a.id, name="XI IPA 1")
    cls_b = ClassService.create_class(db, school_b.id, year_b.id, name="XI IPA 1")

    subj_kim_a = SubjectService.create_subject(db, school_a.id, code="KIM", name="Kimia")
    subj_fis_a = SubjectService.create_subject(db, school_a.id, code="FIS", name="Fisika")
    subj_kim_b = SubjectService.create_subject(db, school_b.id, code="KIM", name="Kimia")

    teacher_a = AuthAccount(
        school_id=school_a.id,
        username=f"guru_a_{uuid4().hex[:6]}",
        name="Guru A",
        password_hash="fake_hash",
        role=UserRole.TEACHER.value,
        nip=f"19850101{uuid4().hex[:6]}",
        is_active=True,
    )
    teacher_b = AuthAccount(
        school_id=school_b.id,
        username=f"guru_b_{uuid4().hex[:6]}",
        name="Guru B",
        password_hash="fake_hash",
        role=UserRole.TEACHER.value,
        nip=f"19850102{uuid4().hex[:6]}",
        is_active=True,
    )
    student_a = AuthAccount(
        school_id=school_a.id,
        username=f"student_a_{uuid4().hex[:6]}",
        name="Siswa A",
        password_hash="fake_hash",
        role=UserRole.STUDENT.value,
        nisn=f"098{uuid4().hex[:6]}",
        is_active=True,
    )
    student_b = AuthAccount(
        school_id=school_b.id,
        username=f"student_b_{uuid4().hex[:6]}",
        name="Siswa B",
        password_hash="fake_hash",
        role=UserRole.STUDENT.value,
        nisn=f"099{uuid4().hex[:6]}",
        is_active=True,
    )
    db.add_all([teacher_a, teacher_b, student_a, student_b])
    db.flush()

    SubjectService.assign_teacher_competency(db, school_a.id, teacher_a.id, subj_kim_a.id)
    SubjectService.assign_teacher_competency(db, school_a.id, teacher_a.id, subj_fis_a.id)
    SubjectService.assign_teacher_competency(db, school_b.id, teacher_b.id, subj_kim_b.id)

    ClassStructureService.assign_teacher_to_class_subject(
        db, school_a.id, cls_a.id, subj_kim_a.id, teacher_a.id
    )
    ClassStructureService.assign_teacher_to_class_subject(
        db, school_a.id, cls_a.id, subj_fis_a.id, teacher_a.id
    )
    ClassStructureService.assign_teacher_to_class_subject(
        db, school_b.id, cls_b.id, subj_kim_b.id, teacher_b.id
    )

    ClassStructureService.enroll_student_to_class(db, school_a.id, student_a.id, cls_a.id)
    ClassStructureService.enroll_student_to_class(db, school_b.id, student_b.id, cls_b.id)

    return {
        "school_a": school_a,
        "school_b": school_b,
        "year_a": year_a,
        "year_b": year_b,
        "sem_a": sem_a,
        "sem_b": sem_b,
        "cls_a": cls_a,
        "cls_b": cls_b,
        "subj_kim_a": subj_kim_a,
        "subj_fis_a": subj_fis_a,
        "subj_kim_b": subj_kim_b,
        "teacher_a": teacher_a,
        "teacher_b": teacher_b,
        "student_a": student_a,
        "student_b": student_b,
        "_schedule_offset": 1,
    }


def create_persisted_assessment_and_embedding(
    db,
    env: dict,
    school_key: str = "school_a",
    subject_key: str = "subj_kim_a",
    year_key: str = "year_a",
    teacher_key: str = "teacher_a",
    student_key: str = "student_a",
    cls_key: str = "cls_a",
    sem_key: str = "sem_a",
    subject_name: str = "Kimia",
    class_level: str = "XI",
    question_text: str = "Jelaskan Hukum Dalton!",
    student_answer: str = "Perbandingan massa unsur adalah bulat sederhana.",
    teacher_feedback: str = "Sangat akurat.",
    final_score: float = 9.5,
    version: int = 1,
    is_current: bool = True,
    is_rag_eligible: bool = True,
    custom_vector: list[float] | None = None,
) -> tuple[AssessmentHistory, AssessmentEmbedding]:
    """Helper to create valid FK relational chain for AssessmentHistory and AssessmentEmbedding."""
    school = env[school_key]
    year = env[year_key]
    subject = env[subject_key]
    teacher = env[teacher_key]
    student = env[student_key]
    cls = env.get(cls_key)
    sem = env.get(sem_key)

    pkg = QuestionPackage(
        owner_teacher_account_id=teacher.id,
        school_id=school.id,
        name=f"Paket {subject_name} {uuid4().hex[:4]}",
        class_level=class_level,
        target_counts={"ES": 1},
        subject=subject_name,
        status=PackageStatus.READY.value,
    )
    db.add(pkg)
    db.flush()

    q = Question(
        owner_teacher_account_id=teacher.id,
        type=QuestionType.ES,
        content=question_text,
        options=None,
        answer_key="Kunci jawaban...",
        rubrics=[{"name": "Konsep", "points": 5}],
        subject=subject_name,
        class_level=class_level,
        ai_grading=True,
    )
    db.add(q)
    db.flush()

    # Use unique, non-overlapping schedule times to avoid conflict exception
    offset = env.get("_schedule_offset", 1)
    env["_schedule_offset"] = offset + 1
    base_time = datetime.now(timezone.utc) + timedelta(days=offset * 2)

    schedule = ExamScheduleService.create_exam_schedule(
        db,
        school_id=school.id,
        academic_year_id=year.id,
        academic_semester_id=sem.id if sem else year.semesters[0].id,
        class_id=cls.id if cls else None,
        subject_id=subject.id,
        title=f"Ujian {subject_name} {uuid4().hex[:4]}",
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
        student_id=student.id,
        status=ExamAttemptStatus.SUBMITTED,
        randomized_order=[q.id],
    )
    db.add(attempt)
    db.flush()

    evaluation = ExamAnswerEvaluation(
        exam_attempt_id=attempt.id,
        question_id=q.id,
        score=final_score,
        max_score=10.0,
        feedback=teacher_feedback,
        grading_status=GradingStatus.FINALIZED,
        grading_source=GradingSource.TEACHER,
        grading_version=1,
        last_evaluated_at=base_time,
    )
    db.add(evaluation)
    db.flush()

    history = AssessmentHistory(
        school_id=school.id,
        academic_year_id=year.id,
        subject_id=subject.id,
        subject_name=subject_name,
        class_level=class_level,
        evaluation_id=evaluation.id,
        exam_attempt_id=attempt.id,
        question_id=q.id,
        exam_teacher_id=teacher.id,
        finalized_by_teacher_id=teacher.id,
        version=version,
        is_current=is_current,
        question_text=question_text,
        question_type="ES",
        answer_key="Kunci jawaban...",
        rubrics_json=[{"name": "Konsep", "points": 5}],
        max_score=10.0,
        student_answer=student_answer,
        teacher_score=final_score,
        teacher_feedback=teacher_feedback,
        final_score=final_score,
        score_delta=0.0,
        is_rag_eligible=is_rag_eligible,
        embedding_status="EMBEDDED" if is_current else "SUPERSEDED",
        embedded_at=base_time,
    )
    db.add(history)
    db.flush()

    doc = AssessmentDocumentService.construct_canonical_document(history)
    vector = (
        custom_vector
        if custom_vector is not None
        else EmbeddingService.encode_passage(doc.e5_passage_text)
    )

    embedding = AssessmentEmbedding(
        assessment_history_id=history.id,
        version=version,
        is_current=is_current,
        content_hash=doc.content_hash,
        school_id=school.id,
        academic_year_id=year.id,
        subject_id=subject.id,
        class_level=class_level,
        embedding_model="intfloat/multilingual-e5-large",
        dimension=1024,
        vector_data=vector,
    )
    db.add(embedding)
    db.flush()

    history.vector_id = str(embedding.id)
    db.flush()

    return history, embedding


# ── TEST 1: Identical vectors yield similarity 1.0 ───────────────────────────
def test_exact_identical_similarity(db):
    env = create_vector_test_environment(db)
    hist, emb = create_persisted_assessment_and_embedding(db, env)

    query_vec = emb.vector_data
    results = VectorSearchService.search_similar_assessments(
        db=db,
        query_vector=query_vec,
        school_id=env["school_a"].id,
        subject_id=env["subj_kim_a"].id,
        academic_year_id=env["year_a"].id,
        top_k=3,
        similarity_threshold=0.50,
    )

    assert len(results) == 1
    assert results[0].assessment_history_id == hist.id
    assert math.isclose(results[0].similarity_score, 1.0, rel_tol=1e-4)


# ── TEST 2: Orthogonal vectors yield similarity approx 0.0 ──────────────────
def test_orthogonal_vectors_similarity(db):
    vec_a = [1.0] + [0.0] * 1023
    vec_b = [0.0, 1.0] + [0.0] * 1022

    sim = VectorSearchService.compute_cosine_similarity(vec_a, vec_b)
    assert math.isclose(sim, 0.0, abs_tol=1e-6)


# ── TEST 3: Correct ranking order (highest to lowest) ────────────────────────
def test_similarity_ranking_descending(db):
    env = create_vector_test_environment(db)
    query_vec = [1.0] + [0.0] * 1023

    vec_high = [0.95, math.sqrt(1 - 0.95**2)] + [0.0] * 1022
    vec_med = [0.75, math.sqrt(1 - 0.75**2)] + [0.0] * 1022
    vec_low = [0.50, math.sqrt(1 - 0.50**2)] + [0.0] * 1022

    hist_med, _ = create_persisted_assessment_and_embedding(
        db, env, question_text="Med sim", custom_vector=vec_med
    )
    hist_high, _ = create_persisted_assessment_and_embedding(
        db, env, question_text="High sim", custom_vector=vec_high
    )
    hist_low, _ = create_persisted_assessment_and_embedding(
        db, env, question_text="Low sim", custom_vector=vec_low
    )

    results = VectorSearchService.search_similar_assessments(
        db=db,
        query_vector=query_vec,
        school_id=env["school_a"].id,
        subject_id=env["subj_kim_a"].id,
        academic_year_id=env["year_a"].id,
        top_k=5,
        similarity_threshold=0.40,
    )

    assert len(results) == 3
    assert results[0].assessment_history_id == hist_high.id
    assert results[1].assessment_history_id == hist_med.id
    assert results[2].assessment_history_id == hist_low.id
    assert results[0].similarity_score > results[1].similarity_score > results[2].similarity_score


# ── TEST 4: Top-K limit enforcement ──────────────────────────────────────────
def test_top_k_limit(db):
    env = create_vector_test_environment(db)
    query_vec = [1.0] + [0.0] * 1023

    for i in range(5):
        s = 0.9 - (i * 0.05)
        vec = [s, math.sqrt(1 - s**2)] + [0.0] * 1022
        create_persisted_assessment_and_embedding(
            db, env, question_text=f"Q {i}", custom_vector=vec
        )

    results_k2 = VectorSearchService.search_similar_assessments(
        db=db,
        query_vector=query_vec,
        school_id=env["school_a"].id,
        subject_id=env["subj_kim_a"].id,
        academic_year_id=env["year_a"].id,
        top_k=2,
        similarity_threshold=0.0,
    )
    assert len(results_k2) == 2


# ── TEST 5: Threshold filtering ──────────────────────────────────────────────
def test_similarity_threshold_filtering(db):
    env = create_vector_test_environment(db)
    query_vec = [1.0] + [0.0] * 1023

    # Vector with similarity 0.85
    vec_above = [0.85, math.sqrt(1 - 0.85**2)] + [0.0] * 1022
    # Vector with similarity 0.60
    vec_below = [0.60, math.sqrt(1 - 0.60**2)] + [0.0] * 1022

    create_persisted_assessment_and_embedding(
        db, env, question_text="Above", custom_vector=vec_above
    )
    create_persisted_assessment_and_embedding(
        db, env, question_text="Below", custom_vector=vec_below
    )

    results = VectorSearchService.search_similar_assessments(
        db=db,
        query_vector=query_vec,
        school_id=env["school_a"].id,
        subject_id=env["subj_kim_a"].id,
        academic_year_id=env["year_a"].id,
        top_k=5,
        similarity_threshold=0.70,
    )

    assert len(results) == 1
    assert results[0].question_text == "Above"
    assert math.isclose(results[0].similarity_score, 0.85, rel_tol=1e-4)


# ── TEST 6: Tenant isolation (School A cannot retrieve School B) ─────────────
def test_tenant_isolation_strict(db):
    env = create_vector_test_environment(db)
    identical_vec = [1.0] + [0.0] * 1023

    hist_a, _ = create_persisted_assessment_and_embedding(
        db,
        env,
        school_key="school_a",
        subject_key="subj_kim_a",
        year_key="year_a",
        teacher_key="teacher_a",
        student_key="student_a",
        cls_key="cls_a",
        sem_key="sem_a",
        question_text="School A Chemistry",
        custom_vector=identical_vec,
    )
    hist_b, _ = create_persisted_assessment_and_embedding(
        db,
        env,
        school_key="school_b",
        subject_key="subj_kim_b",
        year_key="year_b",
        teacher_key="teacher_b",
        student_key="student_b",
        cls_key="cls_b",
        sem_key="sem_b",
        question_text="School B Chemistry",
        custom_vector=identical_vec,
    )

    results_a = VectorSearchService.search_similar_assessments(
        db=db,
        query_vector=identical_vec,
        school_id=env["school_a"].id,
        subject_id=env["subj_kim_a"].id,
        academic_year_id=env["year_a"].id,
        top_k=10,
        similarity_threshold=0.0,
    )

    assert len(results_a) == 1
    assert results_a[0].assessment_history_id == hist_a.id
    assert results_a[0].school_id == env["school_a"].id
    assert results_a[0].question_text == "School A Chemistry"


# ── TEST 7: Subject isolation (Chemistry query cannot retrieve Physics) ──────
def test_subject_isolation(db):
    env = create_vector_test_environment(db)
    identical_vec = [1.0] + [0.0] * 1023

    hist_kim, _ = create_persisted_assessment_and_embedding(
        db, env, subject_key="subj_kim_a", subject_name="Kimia", custom_vector=identical_vec
    )
    hist_fis, _ = create_persisted_assessment_and_embedding(
        db, env, subject_key="subj_fis_a", subject_name="Fisika", custom_vector=identical_vec
    )

    results_kim = VectorSearchService.search_similar_assessments(
        db=db,
        query_vector=identical_vec,
        school_id=env["school_a"].id,
        subject_id=env["subj_kim_a"].id,
        academic_year_id=env["year_a"].id,
        top_k=10,
        similarity_threshold=0.0,
    )

    assert len(results_kim) == 1
    assert results_kim[0].assessment_history_id == hist_kim.id
    assert results_kim[0].subject_id == env["subj_kim_a"].id


# ── TEST 8: Academic year isolation ──────────────────────────────────────────
def test_academic_year_isolation(db):
    env = create_vector_test_environment(db)
    identical_vec = [1.0] + [0.0] * 1023

    year_old = AcademicYear(
        school_id=env["school_a"].id,
        name="2025/2026",
        start_date=datetime.now(timezone.utc) - timedelta(days=400),
        end_date=datetime.now(timezone.utc) - timedelta(days=35),
        status=AcademicStatus.ARCHIVED.value,
    )
    db.add(year_old)
    db.flush()
    sem_old = AcademicSemester(
        academic_year_id=year_old.id,
        code="GANJIL",
        display_name="Semester Ganjil",
        status=AcademicStatus.ARCHIVED.value,
    )
    db.add(sem_old)
    db.flush()
    cls_old = ClassService.create_class(db, env["school_a"].id, year_old.id, name="XI IPA Old")
    ClassStructureService.assign_teacher_to_class_subject(
        db, env["school_a"].id, cls_old.id, env["subj_kim_a"].id, env["teacher_a"].id
    )
    ClassStructureService.enroll_student_to_class(
        db, env["school_a"].id, env["student_a"].id, cls_old.id
    )

    env["year_old"] = year_old
    env["sem_old"] = sem_old
    env["cls_old"] = cls_old

    hist_curr, _ = create_persisted_assessment_and_embedding(
        db, env, year_key="year_a", sem_key="sem_a", cls_key="cls_a", custom_vector=identical_vec
    )
    hist_old, _ = create_persisted_assessment_and_embedding(
        db,
        env,
        year_key="year_old",
        sem_key="sem_old",
        cls_key="cls_old",
        custom_vector=identical_vec,
    )

    results_curr = VectorSearchService.search_similar_assessments(
        db=db,
        query_vector=identical_vec,
        school_id=env["school_a"].id,
        subject_id=env["subj_kim_a"].id,
        academic_year_id=env["year_a"].id,
        top_k=10,
        similarity_threshold=0.0,
    )

    assert len(results_curr) == 1
    assert results_curr[0].assessment_history_id == hist_curr.id


# ── TEST 9: Class level filtering ────────────────────────────────────────────
def test_class_level_filtering(db):
    env = create_vector_test_environment(db)
    identical_vec = [1.0] + [0.0] * 1023

    hist_xi, _ = create_persisted_assessment_and_embedding(
        db, env, class_level="XI", custom_vector=identical_vec
    )
    hist_xii, _ = create_persisted_assessment_and_embedding(
        db, env, class_level="XII", custom_vector=identical_vec
    )

    results_xi = VectorSearchService.search_similar_assessments(
        db=db,
        query_vector=identical_vec,
        school_id=env["school_a"].id,
        subject_id=env["subj_kim_a"].id,
        academic_year_id=env["year_a"].id,
        class_level="XI",
        top_k=10,
        similarity_threshold=0.0,
    )
    assert len(results_xi) == 1
    assert results_xi[0].class_level == "XI"

    results_all = VectorSearchService.search_similar_assessments(
        db=db,
        query_vector=identical_vec,
        school_id=env["school_a"].id,
        subject_id=env["subj_kim_a"].id,
        academic_year_id=env["year_a"].id,
        class_level=None,
        top_k=10,
        similarity_threshold=0.0,
    )
    assert len(results_all) == 2


# ── TEST 10: RAG eligibility (excludes non-eligible) ─────────────────────────
def test_rag_eligibility_enforcement(db):
    env = create_vector_test_environment(db)
    identical_vec = [1.0] + [0.0] * 1023

    create_persisted_assessment_and_embedding(
        db, env, is_rag_eligible=False, custom_vector=identical_vec
    )

    results = VectorSearchService.search_similar_assessments(
        db=db,
        query_vector=identical_vec,
        school_id=env["school_a"].id,
        subject_id=env["subj_kim_a"].id,
        academic_year_id=env["year_a"].id,
        top_k=10,
        similarity_threshold=0.0,
    )
    assert len(results) == 0


# ── TEST 11: Current version filtering & Superseded exclusion ────────────────
def test_superseded_version_excluded_from_retrieval(db):
    env = create_vector_test_environment(db)
    vec_v1 = [1.0] + [0.0] * 1023
    vec_v2 = [0.9, math.sqrt(1 - 0.9**2)] + [0.0] * 1022

    create_persisted_assessment_and_embedding(
        db, env, version=1, is_current=False, custom_vector=vec_v1
    )
    hist_v2, _ = create_persisted_assessment_and_embedding(
        db, env, version=2, is_current=True, custom_vector=vec_v2
    )

    results = VectorSearchService.search_similar_assessments(
        db=db,
        query_vector=vec_v1,
        school_id=env["school_a"].id,
        subject_id=env["subj_kim_a"].id,
        academic_year_id=env["year_a"].id,
        top_k=10,
        similarity_threshold=0.0,
    )

    assert len(results) == 1
    assert results[0].assessment_history_id == hist_v2.id
    assert results[0].version == 2


# ── TEST 12: Empty knowledge base handling ───────────────────────────────────
def test_empty_knowledge_base_returns_empty_list(db):
    env = create_vector_test_environment(db)
    dummy_vec = [1.0] + [0.0] * 1023

    results = VectorSearchService.search_similar_assessments(
        db=db,
        query_vector=dummy_vec,
        school_id=env["school_a"].id,
        subject_id=env["subj_kim_a"].id,
        academic_year_id=env["year_a"].id,
    )
    assert results == []


# ── TEST 13: Dimension mismatch rejection ────────────────────────────────────
def test_dimension_mismatch_raises_value_error(db):
    env = create_vector_test_environment(db)
    wrong_dim_vec = [0.1] * 512

    with pytest.raises(ValueError, match="dimension mismatch"):
        VectorSearchService.search_similar_assessments(
            db=db,
            query_vector=wrong_dim_vec,
            school_id=env["school_a"].id,
            subject_id=env["subj_kim_a"].id,
            academic_year_id=env["year_a"].id,
        )


# ── TEST 14: Zero student PII leakage in search results ──────────────────────
def test_zero_student_pii_leakage(db):
    env = create_vector_test_environment(db)
    identical_vec = [1.0] + [0.0] * 1023

    create_persisted_assessment_and_embedding(db, env, custom_vector=identical_vec)

    results = VectorSearchService.search_similar_assessments(
        db=db,
        query_vector=identical_vec,
        school_id=env["school_a"].id,
        subject_id=env["subj_kim_a"].id,
        academic_year_id=env["year_a"].id,
    )

    assert len(results) == 1
    res = results[0]
    assert isinstance(res, SimilarAssessmentResult)
    assert not hasattr(res, "student_name")
    assert not hasattr(res, "student_nisn")
    assert not hasattr(res, "student_id")
    assert not hasattr(res, "ip_address")


# ── TEST 15: NaN and Inf vector rejection ────────────────────────────────────
def test_nan_and_inf_vector_rejection(db):
    env = create_vector_test_environment(db)
    nan_vec = [float("nan")] * 1024
    inf_vec = [float("inf")] * 1024

    with pytest.raises(ValueError, match="NaN"):
        VectorSearchService.search_similar_assessments(
            db=db,
            query_vector=nan_vec,
            school_id=env["school_a"].id,
            subject_id=env["subj_kim_a"].id,
            academic_year_id=env["year_a"].id,
        )

    with pytest.raises(ValueError, match="Inf"):
        VectorSearchService.search_similar_assessments(
            db=db,
            query_vector=inf_vec,
            school_id=env["school_a"].id,
            subject_id=env["subj_kim_a"].id,
            academic_year_id=env["year_a"].id,
        )


# ── TEST 16: Parameter validation (top_k & threshold) ────────────────────────
def test_parameter_bounds_validation(db):
    env = create_vector_test_environment(db)
    valid_vec = [1.0] + [0.0] * 1023

    with pytest.raises(ValueError, match="Invalid top_k"):
        VectorSearchService.search_similar_assessments(
            db=db,
            query_vector=valid_vec,
            school_id=env["school_a"].id,
            subject_id=env["subj_kim_a"].id,
            academic_year_id=env["year_a"].id,
            top_k=0,
        )

    with pytest.raises(ValueError, match="Invalid similarity_threshold"):
        VectorSearchService.search_similar_assessments(
            db=db,
            query_vector=valid_vec,
            school_id=env["school_a"].id,
            subject_id=env["subj_kim_a"].id,
            academic_year_id=env["year_a"].id,
            similarity_threshold=1.5,
        )


# ── TEST 17: Deterministic tie-breaking ──────────────────────────────────────
def test_deterministic_tie_breaking(db):
    env = create_vector_test_environment(db)
    identical_vec = [1.0] + [0.0] * 1023

    hist1, _ = create_persisted_assessment_and_embedding(
        db, env, question_text="Q1", custom_vector=identical_vec
    )
    hist2, _ = create_persisted_assessment_and_embedding(
        db, env, question_text="Q2", custom_vector=identical_vec
    )

    results = VectorSearchService.search_similar_assessments(
        db=db,
        query_vector=identical_vec,
        school_id=env["school_a"].id,
        subject_id=env["subj_kim_a"].id,
        academic_year_id=env["year_a"].id,
        top_k=5,
        similarity_threshold=0.0,
    )

    assert len(results) == 2
    assert results[0].assessment_history_id < results[1].assessment_history_id


# ── TEST 18: Performance Benchmark (Actual Measured Latencies) ───────────────
def test_measured_performance_benchmark(db):
    env = create_vector_test_environment(db)
    query_vec = [1.0] + [0.0] * 1023

    for i in range(20):
        s = 0.80 + (i % 10) * 0.01
        vec = [s, math.sqrt(1 - s**2)] + [0.0] * 1022
        create_persisted_assessment_and_embedding(
            db, env, question_text=f"Benchmark Q {i}", custom_vector=vec
        )

    iterations = 5
    latencies = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        results = VectorSearchService.search_similar_assessments(
            db=db,
            query_vector=query_vec,
            school_id=env["school_a"].id,
            subject_id=env["subj_kim_a"].id,
            academic_year_id=env["year_a"].id,
            top_k=3,
            similarity_threshold=0.50,
        )
        latencies.append((time.perf_counter() - t0) * 1000.0)

    avg_ms = sum(latencies) / len(latencies)
    assert len(results) == 3
    assert avg_ms < 50.0
