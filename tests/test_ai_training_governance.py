import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.ai.dataset_version import DatasetVersion
from app.models.ai.training_candidate import TrainingCandidate
from app.models.exam.answer_evaluation import ExamAnswerEvaluation
from app.repositories.ai.assessment_history_repository import (
    assessment_history_repository,
)
from app.services.ai.governance.dataset_builder_service import DatasetBuilderService
from app.services.ai.governance.pii_sanitization_service import PiiSanitizationService
from app.services.ai.governance.quality_gate_service import QualityGateService
from app.services.ai.governance.training_candidate_service import TrainingCandidateService
from app.services.exam.exam_service import ExamService
from main import app
from tests.test_assessment_history import setup_exam_environment

client = TestClient(app)


def test_pii_sanitization_detects_and_masks_student_and_teacher_pii():
    raw_answer = (
        "Perkenalkan nama saya Muhammad Rizky dari SMA 1 Bandung. "
        "NISN saya adalah 0012345678. "
        "Jika ada koreksi hubungi email rizky@example.com atau WA 081234567890. "
        "Mitokondria berfungsi sebagai tempat respirasi seluler."
    )
    sanitized_ans, detected, status = PiiSanitizationService.sanitize_text(
        raw_answer, field_name="student_answer"
    )

    assert status == "SANITIZED"
    assert len(detected) >= 4
    assert "[STUDENT_NAME]" in sanitized_ans
    assert "[NISN_NUMBER]" in sanitized_ans
    assert "[EMAIL_ADDRESS]" in sanitized_ans
    assert "[PHONE_NUMBER]" in sanitized_ans
    assert "0012345678" not in sanitized_ans
    assert "rizky@example.com" not in sanitized_ans

    # Critical P0 Assertion: Never store raw PII value in detected metadata!
    for ent in detected:
        assert "raw_value" not in ent
        assert "type" in ent
        assert "field" in ent
        assert "char_length" in ent
        assert "detection_method" in ent


def test_pii_sanitization_clean_text_remains_clean():
    clean_text = "Proses fotosintesis menghasilkan glukosa dan oksigen dengan bantuan klorofil."
    sanitized, detected, status = PiiSanitizationService.sanitize_text(clean_text)
    assert status == "CLEAN"
    assert len(detected) == 0
    assert sanitized == clean_text


def test_quality_gate_rejects_empty_and_trivial_feedback():
    # 1. Empty feedback
    res_empty = QualityGateService.evaluate_quality(
        student_answer="Mitokondria adalah penghasil energi utama dalam sel eukariotik.",
        teacher_feedback="",
        teacher_score=8.0,
        max_score=10.0,
        rubrics=[{"ku_id": "C1", "text": "Fungsi mitokondria", "weight": 100.0}],
    )
    assert not res_empty.is_eligible
    assert "FEEDBACK_EMPTY" in res_empty.rejection_reasons

    # 2. Trivial 1-word feedback
    res_trivial = QualityGateService.evaluate_quality(
        student_answer="Mitokondria adalah penghasil energi utama dalam sel eukariotik.",
        teacher_feedback="Bagus.",
        teacher_score=9.0,
        max_score=10.0,
        rubrics=[{"ku_id": "C1", "text": "Fungsi mitokondria", "weight": 100.0}],
    )
    assert not res_trivial.is_eligible
    assert "FEEDBACK_TRIVIAL" in res_trivial.rejection_reasons


def test_quality_gate_structural_rubric_check():
    # Malformed empty dict in rubric
    res_bad_rubric = QualityGateService.evaluate_quality(
        student_answer="Mitokondria menghasilkan ATP melalui respirasi sel.",
        teacher_feedback="Penjelasan sudah baik dan sesuai indikator respirasi.",
        teacher_score=9.0,
        max_score=10.0,
        rubrics=[{}],
    )
    assert "MISSING_OR_EMPTY_RUBRIC" in res_bad_rubric.rejection_reasons


def test_quality_gate_accepts_substantive_pedagogical_feedback():
    res_substantive = QualityGateService.evaluate_quality(
        student_answer="Mitokondria berperan dalam respirasi sel melalui siklus Krebs dan fosforilasi oksidatif untuk sintesis ATP.",
        teacher_feedback="Penjelasan sangat komprehensif, mencakup siklus Krebs dan pembentukan molekul ATP dengan tepat sesuai rubrik C1.",
        teacher_score=10.0,
        max_score=10.0,
        rubrics=[
            {"ku_id": "C1", "text": "Menjelaskan siklus respirasi", "weight": 50.0},
            {"ku_id": "C2", "text": "Menjelaskan sintesis ATP", "weight": 50.0},
        ],
    )
    assert res_substantive.is_eligible
    assert res_substantive.quality_status == "ELIGIBLE"
    assert res_substantive.quality_score >= 0.85
    assert len(res_substantive.rejection_reasons) == 0


def test_candidate_ingestion_from_assessment_history(db: Session):
    attempt, questions, teacher, student, school, subj = setup_exam_environment(
        db, school_name="SMA Labschool Governance 1"
    )
    ExamService.submit_attempt(db, attempt.id, student_id=attempt.student_id)

    evals = (
        db.query(ExamAnswerEvaluation)
        .filter(ExamAnswerEvaluation.exam_attempt_id == attempt.id)
        .all()
    )
    essay_eval = next(ev for ev in evals if ev.question_id == questions[1].id)

    ExamService.finalize_evaluation(
        db=db,
        evaluation_id=essay_eval.id,
        score=9.0,
        feedback="Penjelasan tahapan transkripsi dan translasi sangat terstruktur dan sesuai indikator rubrik.",
        teacher_account_id=teacher.id,
    )

    history = assessment_history_repository.get_current_by_evaluation(db, essay_eval.id)
    assert history is not None

    # Ingest through TrainingCandidateService
    candidate = TrainingCandidateService.evaluate_and_ingest_history(db, history.id)

    assert candidate is not None
    assert candidate.assessment_history_id == history.id
    assert candidate.quality_status == "ELIGIBLE"
    assert candidate.quality_score >= 0.80
    assert candidate.question_group_key is not None
    assert candidate.academic_year_id == history.academic_year_id
    assert candidate.formatted_sft_payload["task"] == "essay_grading"
    assert candidate.formatted_sft_payload["target"]["score"] == 9.0


def test_leakage_free_group_split_dataset_building(db: Session):
    candidate_ids = []
    for q_idx in range(1, 5):
        attempt, questions, teacher, student, school, subj = setup_exam_environment(
            db, school_name=f"SMA Group Split School {q_idx}"
        )
        ExamService.submit_attempt(db, attempt.id, student_id=attempt.student_id)

        evals = (
            db.query(ExamAnswerEvaluation)
            .filter(ExamAnswerEvaluation.exam_attempt_id == attempt.id)
            .all()
        )
        essay_eval = next(ev for ev in evals if ev.question_id == questions[1].id)

        ExamService.finalize_evaluation(
            db=db,
            evaluation_id=essay_eval.id,
            score=8.5,
            feedback=f"Penilaian substantif untuk soal {q_idx} dengan rincian yang tepat dan terarah.",
            teacher_account_id=teacher.id,
        )

        history = assessment_history_repository.get_current_by_evaluation(db, essay_eval.id)
        history.question_text = (
            f"Soal Konsep Biologi ke-{q_idx} mengenai metabolisme dan fotosintesis."
        )
        history.answer_key = f"Kunci jawaban resmi untuk nomor {q_idx}."
        db.flush()

        cand = TrainingCandidateService.evaluate_and_ingest_history(db, history.id)
        candidate_ids.append(cand.id)

    version_tag = f"v1.0.0-group-test-{uuid.uuid4().hex[:4]}"
    dv = DatasetBuilderService.build_dataset_version(
        db=db,
        version_tag=version_tag,
        min_quality_score=0.70,
        train_ratio=0.50,
        val_ratio=0.25,
        test_ratio=0.25,
        split_strategy="QUESTION_GROUP_SPLIT",
    )

    assert isinstance(dv, DatasetVersion)
    assert dv.total_samples > 0
    assert dv.train_count > 0
    assert dv.test_count > 0
    assert len(dv.dataset_hash) == 64
    assert len(dv.manifest_hash) == 64

    # Leakage Guard Assertion: Verify train and test question group keys are mutually disjoint!
    train_cands = (
        db.query(TrainingCandidate)
        .filter(TrainingCandidate.id.in_(dv.split_manifest["train"]))
        .all()
    )
    test_cands = (
        db.query(TrainingCandidate)
        .filter(TrainingCandidate.id.in_(dv.split_manifest["test"]))
        .all()
    )

    train_group_keys = {c.question_group_key for c in train_cands}
    test_group_keys = {c.question_group_key for c in test_cands}

    assert train_group_keys.isdisjoint(test_group_keys)


def test_dataset_version_true_immutability_and_hash_identity(db: Session):
    attempt, questions, teacher, student, school, subj = setup_exam_environment(
        db, school_name="SMA Immutability School"
    )
    ExamService.submit_attempt(db, attempt.id, student_id=attempt.student_id)

    evals = (
        db.query(ExamAnswerEvaluation)
        .filter(ExamAnswerEvaluation.exam_attempt_id == attempt.id)
        .all()
    )
    essay_eval = next(ev for ev in evals if ev.question_id == questions[1].id)

    ExamService.finalize_evaluation(
        db=db,
        evaluation_id=essay_eval.id,
        score=10.0,
        feedback="Analisis struktur dan fungsi molekuler sangat mendalam dan lengkap.",
        teacher_account_id=teacher.id,
    )

    history = assessment_history_repository.get_current_by_evaluation(db, essay_eval.id)
    cand = TrainingCandidateService.evaluate_and_ingest_history(db, history.id)

    v_tag = f"v_immutable_{uuid.uuid4().hex[:4]}"
    dv = DatasetBuilderService.build_dataset_version(
        db=db,
        version_tag=v_tag,
        min_quality_score=0.60,
        train_ratio=1.0,
        val_ratio=0.0,
        test_ratio=0.0,
    )

    # 1. Verify cryptographic hashes
    initial_dataset_hash = dv.dataset_hash
    assert len(initial_dataset_hash) == 64

    # 2. Export train split
    exported_before = DatasetBuilderService.export_dataset_split(db, v_tag, split_name="train")
    assert len(exported_before) >= 1
    original_target_score = exported_before[0]["target"]["score"]

    # 3. Simulate candidate modification in database
    cand.formatted_sft_payload["target"]["score"] = 0.0
    cand.formatted_sft_payload["target"]["feedback"] = "MUTATED_AFTER_RELEASE"
    db.flush()

    # 4. Export train split again — MUST remain untouched from frozen snapshot!
    exported_after = DatasetBuilderService.export_dataset_split(db, v_tag, split_name="train")
    assert exported_after[0]["target"]["score"] == original_target_score
    assert exported_after[0]["target"]["feedback"] != "MUTATED_AFTER_RELEASE"
    assert dv.dataset_hash == initial_dataset_hash


def test_split_strategy_strict_validation_and_ratio_guard(db: Session):
    attempt, questions, teacher, student, school, subj = setup_exam_environment(
        db, school_name="SMA Ratio Validation School"
    )
    ExamService.submit_attempt(db, attempt.id, student_id=attempt.student_id)

    evals = (
        db.query(ExamAnswerEvaluation)
        .filter(ExamAnswerEvaluation.exam_attempt_id == attempt.id)
        .all()
    )
    essay_eval = next(ev for ev in evals if ev.question_id == questions[1].id)

    ExamService.finalize_evaluation(
        db=db,
        evaluation_id=essay_eval.id,
        score=9.5,
        feedback="Uraian konsep hukum dasar kimia sangat tepat.",
        teacher_account_id=teacher.id,
    )

    history = assessment_history_repository.get_current_by_evaluation(db, essay_eval.id)
    TrainingCandidateService.evaluate_and_ingest_history(db, history.id)

    # 1. Unsafe split strategy must be rejected
    with pytest.raises(ValueError, match="Unsupported split strategy"):
        DatasetBuilderService.build_dataset_version(
            db=db,
            version_tag=f"v_invalid_strategy_{uuid.uuid4().hex[:4]}",
            split_strategy="UNSAFE_RANDOM_SPLIT",
        )

    # 2. Invalid ratio sum must be rejected
    with pytest.raises(ValueError, match="Split ratios must sum to 1.0"):
        DatasetBuilderService.build_dataset_version(
            db=db,
            version_tag=f"v_invalid_ratios_{uuid.uuid4().hex[:4]}",
            train_ratio=0.8,
            val_ratio=0.5,
            test_ratio=0.1,
        )


from app.core.dependencies import get_current_user


def test_api_governance_endpoints(db: Session):
    attempt, questions, teacher, student, school, subj = setup_exam_environment(
        db, school_name="SMA API Gov School"
    )
    ExamService.submit_attempt(db, attempt.id, student_id=attempt.student_id)

    evals = (
        db.query(ExamAnswerEvaluation)
        .filter(ExamAnswerEvaluation.exam_attempt_id == attempt.id)
        .all()
    )
    essay_eval = next(ev for ev in evals if ev.question_id == questions[1].id)

    ExamService.finalize_evaluation(
        db=db,
        evaluation_id=essay_eval.id,
        score=10.0,
        feedback="Penjelasan fungsi enzim dan katalis biologi sangat komprehensif dan runtut.",
        teacher_account_id=teacher.id,
    )

    history = assessment_history_repository.get_current_by_evaluation(db, essay_eval.id)

    # Set authenticated user context
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": str(teacher.id),
        "role": "ADMIN",
        "school_id": school.id,
    }

    try:
        # 1. API: Ingest Candidate
        ingest_res = client.post(f"/api/v1/ai/governance/candidates/ingest/{history.id}")
        assert ingest_res.status_code == 200
        ingest_data = ingest_res.json()
        assert ingest_data["quality_status"] == "ELIGIBLE"
        assert ingest_data["academic_year_id"] == history.academic_year_id
        assert ingest_data["created_by_user_id"] == teacher.id

        # 2. API: Build Dataset
        v_tag = f"v_api_test_{uuid.uuid4().hex[:4]}"
        build_res = client.post(
            "/api/v1/ai/governance/datasets/build",
            json={
                "version_tag": v_tag,
                "min_quality_score": 0.60,
                "train_ratio": 0.8,
                "val_ratio": 0.1,
                "test_ratio": 0.1,
                "split_strategy": "QUESTION_GROUP_SPLIT",
            },
        )
        assert build_res.status_code == 200
        build_data = build_res.json()
        assert build_data["version_tag"] == v_tag
        assert build_data["total_samples"] >= 1
        assert len(build_data["dataset_hash"]) == 64
        assert len(build_data["manifest_hash"]) == 64
        assert build_data["created_by_user_id"] == teacher.id

        # 3. API: Export Split
        export_res = client.get(f"/api/v1/ai/governance/datasets/{v_tag}/export?split=train")
        assert export_res.status_code == 200
        export_data = export_res.json()
        assert export_data["version_tag"] == v_tag
        assert export_data["split"] == "train"
        assert "data" in export_data

        # 4. API: Invalid Ratio validation triggers 422
        bad_ratio_res = client.post(
            "/api/v1/ai/governance/datasets/build",
            json={
                "version_tag": f"v_bad_ratio_{uuid.uuid4().hex[:4]}",
                "train_ratio": 0.9,
                "val_ratio": 0.5,
                "test_ratio": 0.5,
            },
        )
        assert bad_ratio_res.status_code == 422
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_api_governance_cross_tenant_isolation_rejected(db: Session):
    # Setup School A and School B
    attempt_a, questions_a, teacher_a, student_a, school_a, subj_a = setup_exam_environment(
        db, school_name="SMA Tenant Alpha"
    )
    attempt_b, questions_b, teacher_b, student_b, school_b, subj_b = setup_exam_environment(
        db, school_name="SMA Tenant Beta"
    )

    ExamService.submit_attempt(db, attempt_b.id, student_id=attempt_b.student_id)
    evals_b = (
        db.query(ExamAnswerEvaluation)
        .filter(ExamAnswerEvaluation.exam_attempt_id == attempt_b.id)
        .all()
    )
    essay_eval_b = next(ev for ev in evals_b if ev.question_id == questions_b[1].id)

    ExamService.finalize_evaluation(
        db=db,
        evaluation_id=essay_eval_b.id,
        score=9.0,
        feedback="Jawaban substantif untuk sekolah Beta.",
        teacher_account_id=teacher_b.id,
    )
    history_b = assessment_history_repository.get_current_by_evaluation(db, essay_eval_b.id)

    # Ingest for school B by teacher B
    TrainingCandidateService.evaluate_and_ingest_history(db, history_b.id)
    v_tag_b = f"v_tenant_b_{uuid.uuid4().hex[:4]}"
    dv_b = DatasetBuilderService.build_dataset_version(
        db=db,
        version_tag=v_tag_b,
        school_id=school_b.id,
        train_ratio=1.0,
        val_ratio=0.0,
        test_ratio=0.0,
    )

    # Now authenticate as Teacher from School A
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": str(teacher_a.id),
        "role": "ADMIN",
        "school_id": school_a.id,
    }

    try:
        # 1. School A tries to ingest School B's history -> 403 Forbidden
        ingest_cross = client.post(f"/api/v1/ai/governance/candidates/ingest/{history_b.id}")
        assert ingest_cross.status_code == 403

        # 2. School A tries to build dataset explicitly specifying School B's ID -> 403 Forbidden
        build_cross = client.post(
            "/api/v1/ai/governance/datasets/build",
            json={
                "version_tag": f"v_cross_attack_{uuid.uuid4().hex[:4]}",
                "school_id": school_b.id,
                "train_ratio": 0.8,
                "val_ratio": 0.1,
                "test_ratio": 0.1,
            },
        )
        assert build_cross.status_code == 403

        # 3. School A tries to export School B's dataset -> 403 Forbidden
        export_cross = client.get(f"/api/v1/ai/governance/datasets/{v_tag_b}/export?split=train")
        assert export_cross.status_code == 403

    finally:
        app.dependency_overrides.pop(get_current_user, None)
