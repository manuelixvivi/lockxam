import json
import os
import tempfile
import uuid

import pytest
from sqlalchemy.orm import Session

from app.models.exam.answer_evaluation import ExamAnswerEvaluation
from app.repositories.ai.assessment_history_repository import assessment_history_repository
from app.services.ai.governance.dataset_builder_service import DatasetBuilderService
from app.services.ai.governance.training_candidate_service import TrainingCandidateService
from app.services.ai.training.datasets.formatter import SftFormatter
from app.services.ai.training.datasets.loader import DatasetLoader
from app.services.ai.training.datasets.validator import DatasetValidator, TrainingPreflightError
from app.services.ai.training.schemas import SftConversationExample, SftMessage
from app.services.ai.training.tokenization.tokenization_config import TokenizationConfig
from app.services.ai.training.tokenization.tokenizer_service import TokenizerService
from app.services.exam.exam_service import ExamService
from tests.test_assessment_history import setup_exam_environment

# ==============================================================================
# 1. DATASET LOADER TESTS
# ==============================================================================


def test_dataset_loader_loads_and_verifies_hash_successfully(db: Session):
    attempt, questions, teacher, student, school, subj = setup_exam_environment(
        db, school_name="SMA Loader Test"
    )
    ExamService.submit_attempt(db, attempt.id)

    evals = (
        db.query(ExamAnswerEvaluation)
        .filter(ExamAnswerEvaluation.exam_attempt_id == attempt.id)
        .all()
    )
    for ev in evals:
        if ev.question_id == questions[1].id:
            ExamService.finalize_evaluation(
                db=db,
                evaluation_id=ev.id,
                score=9.5,
                feedback="Jawaban esai sangat lengkap, sistematis, dan menunjukkan pemahaman konsep mendalam.",
                teacher_account_id=teacher.id,
            )
            h = assessment_history_repository.get_current_by_evaluation(db, ev.id)
            if h:
                TrainingCandidateService.evaluate_and_ingest_history(
                    db, h.id, created_by_user_id=teacher.id
                )

    v_tag = f"v_loader_test_{uuid.uuid4().hex[:4]}"
    DatasetBuilderService.build_dataset_version(
        db=db,
        version_tag=v_tag,
        school_id=school.id,
        created_by_user_id=teacher.id,
        train_ratio=1.0,
        val_ratio=0.0,
        test_ratio=0.0,
    )

    # Load with cryptographic verification
    splits = DatasetLoader.load_from_database(db, v_tag, verify_hash=True)
    assert "train" in splits
    assert len(splits["train"]) >= 1
    assert "question" in splits["train"][0]
    assert "target" in splits["train"][0]


def test_dataset_loader_rejects_corrupted_dataset_hash(db: Session):
    attempt, questions, teacher, student, school, subj = setup_exam_environment(
        db, school_name="SMA Hash Tamper Test"
    )
    ExamService.submit_attempt(db, attempt.id)

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
        feedback="Uraian konsep respirasi selular sangat komprehensif dan akurat.",
        teacher_account_id=teacher.id,
    )
    h = assessment_history_repository.get_current_by_evaluation(db, essay_eval.id)
    TrainingCandidateService.evaluate_and_ingest_history(db, h.id, created_by_user_id=teacher.id)

    v_tag = f"v_tamper_test_{uuid.uuid4().hex[:4]}"
    dv = DatasetBuilderService.build_dataset_version(
        db=db,
        version_tag=v_tag,
        school_id=school.id,
        train_ratio=1.0,
        val_ratio=0.0,
        test_ratio=0.0,
    )

    # Intentionally corrupt the registered dataset_hash
    dv.dataset_hash = "0000000000000000000000000000000000000000000000000000000000000000"
    db.flush()

    with pytest.raises(ValueError, match="Cryptographic dataset integrity error"):
        DatasetLoader.load_from_database(db, v_tag, verify_hash=True)


def test_dataset_loader_export_and_load_jsonl(db: Session):
    attempt, questions, teacher, student, school, subj = setup_exam_environment(
        db, school_name="SMA JSONL Export Test"
    )
    ExamService.submit_attempt(db, attempt.id)

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
        feedback="Penjelasan fungsi mitokondria sangat jelas dan runtut.",
        teacher_account_id=teacher.id,
    )
    h = assessment_history_repository.get_current_by_evaluation(db, essay_eval.id)
    TrainingCandidateService.evaluate_and_ingest_history(db, h.id, created_by_user_id=teacher.id)

    v_tag = f"v_jsonl_test_{uuid.uuid4().hex[:4]}"
    DatasetBuilderService.build_dataset_version(
        db=db,
        version_tag=v_tag,
        school_id=school.id,
        train_ratio=1.0,
        val_ratio=0.0,
        test_ratio=0.0,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        files = DatasetLoader.export_splits_to_jsonl(db, v_tag, tmpdir)
        assert os.path.exists(files["train"])
        assert os.path.exists(files["manifest"])

        loaded_train = DatasetLoader.load_from_jsonl(files["train"])
        assert len(loaded_train) >= 1
        assert loaded_train[0]["task"] == "essay_grading"


# ==============================================================================
# 2. SFT FORMATTER TESTS
# ==============================================================================


def test_sft_formatter_constructs_structured_messages():
    raw_example = {
        "task": "essay_grading",
        "question": "Jelaskan proses fotosintesis reaksi terang!",
        "answer_key": "Klorofil menyerap cahaya dan memecah air menghasilkan O2 dan ATP.",
        "rubric": [{"criterion": "Fotolisis air", "weight": 5.0}],
        "max_score": 10.0,
        "student_answer": "Reaksi terang mengubah cahaya matahari menjadi ATP melalui fotolisis air.",
        "target": {
            "score": 9.0,
            "normalized_score": 0.90,
            "feedback": "Jawaban sangat tepat dalam mengidentifikasi fotolisis air dan ATP.",
        },
    }

    sft_ex = SftFormatter.format_single_example(raw_example)
    assert len(sft_ex.messages) == 3
    assert sft_ex.messages[0].role == "system"
    assert sft_ex.messages[1].role == "user"
    assert sft_ex.messages[2].role == "assistant"

    # Verify user message structure
    assert "### QUESTION" in sft_ex.messages[1].content
    assert "### ANSWER KEY" in sft_ex.messages[1].content
    assert "### SCORING RUBRIC" in sft_ex.messages[1].content
    assert "### STUDENT ESSAY ANSWER" in sft_ex.messages[1].content

    # Verify assistant message JSON parsing
    assistant_json = json.loads(sft_ex.messages[2].content)
    assert assistant_json["score"] == 9.0
    assert assistant_json["normalized_score"] == 0.90
    assert "Jawaban sangat tepat" in assistant_json["feedback"]


def test_sft_formatter_zero_rag_leakage():
    raw_example = {
        "question": "Sebutkan 3 organel sel tanaman!",
        "answer_key": "Kloroplas, vakuola, dinding sel.",
        "rubric": [],
        "max_score": 10.0,
        "student_answer": "Kloroplas, vakuola besar, dan dinding selulosa.",
        "target": {
            "score": 10.0,
            "feedback": "Ketiga organel khusus tumbuhan disebutkan dengan benar.",
        },
    }

    sft_ex = SftFormatter.format_single_example(raw_example)
    full_text = "\n".join([m.content for m in sft_ex.messages])

    # Ensure zero historical reference XML tags are present in pure SFT training data
    assert "<historical_reference_cases>" not in full_text
    assert "<reference_case" not in full_text


def test_sft_formatter_rubric_parsing():
    # Test list of dicts
    rubric_list = [
        {"criterion": "Struktur Gramatika", "weight": 4.0},
        {"criterion": "Ketepatan Argumen", "weight": 6.0},
    ]
    parsed_text = SftFormatter._format_rubric_text(rubric_list)
    assert "1. Struktur Gramatika (Weight/Points: 4.0)" in parsed_text
    assert "2. Ketepatan Argumen (Weight/Points: 6.0)" in parsed_text

    # Test empty rubric fallback
    assert "No explicit rubric provided" in SftFormatter._format_rubric_text(None)


def test_sft_formatter_batch_and_dataset():
    raw_splits = {
        "train": [
            {
                "question": "Q1",
                "student_answer": "A1",
                "max_score": 10.0,
                "target": {"score": 8.0, "feedback": "Good"},
            }
        ],
        "test": [
            {
                "question": "Q2",
                "student_answer": "A2",
                "max_score": 10.0,
                "target": {"score": 9.0, "feedback": "Excellent"},
            }
        ],
    }

    formatted = SftFormatter.format_dataset(raw_splits)
    assert len(formatted["train"]) == 1
    assert len(formatted["test"]) == 1
    assert isinstance(formatted["train"][0], SftConversationExample)


# ==============================================================================
# 3. TOKENIZATION & CHAT TEMPLATE TESTS
# ==============================================================================


def test_chatml_template_rendering():
    messages = [
        SftMessage(role="system", content="System instruction"),
        SftMessage(role="user", content="User question"),
        SftMessage(role="assistant", content="Assistant reply"),
    ]

    rendered = TokenizerService.apply_chat_template(messages, chat_template_format="chatml")
    assert "<|im_start|>system\nSystem instruction<|im_end|>" in rendered
    assert "<|im_start|>user\nUser question<|im_end|>" in rendered
    assert "<|im_start|>assistant\nAssistant reply<|im_end|>" in rendered


def test_llama3_template_rendering():
    messages = [
        SftMessage(role="system", content="System instruction"),
        SftMessage(role="user", content="User question"),
        SftMessage(role="assistant", content="Assistant reply"),
    ]

    rendered = TokenizerService.apply_chat_template(messages, chat_template_format="llama3")
    assert "<|begin_of_text|>" in rendered
    assert "<|start_header_id|>system<|end_header_id|>\n\nSystem instruction<|eot_id|>" in rendered
    assert "<|start_header_id|>user<|end_header_id|>\n\nUser question<|eot_id|>" in rendered


def test_tokenization_label_masking():
    example = SftConversationExample(
        messages=[
            SftMessage(role="system", content="System prompt"),
            SftMessage(role="user", content="Grade this answer"),
            SftMessage(role="assistant", content='{"score": 9.0, "feedback": "Good"}'),
        ]
    )

    config = TokenizationConfig(mask_prompt_labels=True, max_seq_length=512)
    sample = TokenizerService.tokenize_conversation(example, config)

    assert sample.token_length > 0
    assert len(sample.input_ids) == len(sample.attention_mask)
    assert len(sample.input_ids) == len(sample.labels)

    # Prompt tokens must be masked with -100
    assert sample.labels[0] == -100
    # Assistant tokens must NOT be -100
    assert sample.labels[-1] != -100
    assert any(label != -100 for label in sample.labels)


def test_tokenization_truncation_right():
    long_text = "kata " * 500
    example = SftConversationExample(
        messages=[
            SftMessage(role="system", content="System"),
            SftMessage(role="user", content=long_text),
            SftMessage(role="assistant", content="Done"),
        ]
    )

    config = TokenizationConfig(max_seq_length=50, truncation_side="right")
    sample = TokenizerService.tokenize_conversation(example, config)

    assert sample.is_truncated is True
    assert len(sample.input_ids) == 50
    assert len(sample.attention_mask) == 50


def test_tokenization_truncation_left():
    long_text = "kata " * 500
    example = SftConversationExample(
        messages=[
            SftMessage(role="system", content="System"),
            SftMessage(role="user", content=long_text),
            SftMessage(role="assistant", content="Done"),
        ]
    )

    config = TokenizationConfig(max_seq_length=50, truncation_side="left")
    sample = TokenizerService.tokenize_conversation(example, config)

    assert sample.is_truncated is True
    assert len(sample.input_ids) == 50


def test_tokenization_stats_distribution():
    examples = [
        SftConversationExample(
            messages=[
                SftMessage(role="system", content="Sys"),
                SftMessage(role="user", content="Short question"),
                SftMessage(role="assistant", content='{"score": 10}'),
            ]
        ),
        SftConversationExample(
            messages=[
                SftMessage(role="system", content="Sys"),
                SftMessage(
                    role="user", content="A somewhat longer question with multiple sentences."
                ),
                SftMessage(
                    role="assistant", content='{"score": 8, "feedback": "Detailed feedback."}'
                ),
            ]
        ),
    ]

    config = TokenizationConfig(max_seq_length=2048)
    stats = TokenizerService.compute_tokenization_stats(examples, config)

    assert stats.total_samples == 2
    assert stats.total_tokens > 0
    assert stats.avg_tokens_per_sample > 0
    assert stats.min_tokens <= stats.max_tokens
    assert stats.truncated_samples_count == 0
    assert stats.truncation_rate_pct == 0.0


# ==============================================================================
# 4. DATASET VALIDATOR TESTS
# ==============================================================================


def test_dataset_validator_success(db: Session):
    attempt, questions, teacher, student, school, subj = setup_exam_environment(
        db, school_name="SMA Validator Success"
    )
    ExamService.submit_attempt(db, attempt.id)

    evals = (
        db.query(ExamAnswerEvaluation)
        .filter(ExamAnswerEvaluation.exam_attempt_id == attempt.id)
        .all()
    )
    for ev in evals:
        if ev.question_id == questions[1].id:
            ExamService.finalize_evaluation(
                db=db,
                evaluation_id=ev.id,
                score=9.0,
                feedback="Analisis konsep biologi sel sangat komprehensif dan runtut.",
                teacher_account_id=teacher.id,
            )
            h = assessment_history_repository.get_current_by_evaluation(db, ev.id)
            if h:
                TrainingCandidateService.evaluate_and_ingest_history(
                    db, h.id, created_by_user_id=teacher.id
                )

    v_tag = f"v_val_success_{uuid.uuid4().hex[:4]}"
    DatasetBuilderService.build_dataset_version(
        db=db,
        version_tag=v_tag,
        school_id=school.id,
        created_by_user_id=teacher.id,
        train_ratio=1.0,
        val_ratio=0.0,
        test_ratio=0.0,
    )

    report = DatasetValidator.validate_dataset_version(db, v_tag)
    assert report.is_valid is True
    assert report.disjoint_check_passed is True
    assert report.score_bounds_passed is True
    assert report.missing_fields_count == 0
    assert len(report.validation_errors) == 0
    assert "train" in report.tokenization_summary


def test_dataset_validator_detects_data_leakage(db: Session):
    attempt, questions, teacher, student, school, subj = setup_exam_environment(
        db, school_name="SMA Leakage Detection"
    )
    ExamService.submit_attempt(db, attempt.id)

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
        feedback="Penjelasan fungsi ribosom sangat baik.",
        teacher_account_id=teacher.id,
    )
    h = assessment_history_repository.get_current_by_evaluation(db, essay_eval.id)
    TrainingCandidateService.evaluate_and_ingest_history(db, h.id, created_by_user_id=teacher.id)

    v_tag = f"v_leakage_{uuid.uuid4().hex[:4]}"
    dv = DatasetBuilderService.build_dataset_version(
        db=db,
        version_tag=v_tag,
        school_id=school.id,
        train_ratio=1.0,
        val_ratio=0.0,
        test_ratio=0.0,
    )

    # Intentionally inject overlapping candidate ID into test manifest to simulate data leakage
    cand_id = dv.split_manifest["train"][0]
    dv.split_manifest["test"] = [cand_id]
    db.flush()

    report = DatasetValidator.validate_dataset_version(db, v_tag)
    assert report.disjoint_check_passed is False
    assert report.is_valid is False
    assert any("Data leakage detected" in err for err in report.validation_errors)


def test_dataset_validator_detects_out_of_bounds_scores(db: Session):
    attempt, questions, teacher, student, school, subj = setup_exam_environment(
        db, school_name="SMA OutOfBounds Score"
    )
    ExamService.submit_attempt(db, attempt.id)

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
        feedback="Uraian konsep biologi sangat memuaskan.",
        teacher_account_id=teacher.id,
    )
    h = assessment_history_repository.get_current_by_evaluation(db, essay_eval.id)
    TrainingCandidateService.evaluate_and_ingest_history(db, h.id, created_by_user_id=teacher.id)

    v_tag = f"v_score_bounds_{uuid.uuid4().hex[:4]}"
    dv = DatasetBuilderService.build_dataset_version(
        db=db,
        version_tag=v_tag,
        school_id=school.id,
        train_ratio=1.0,
        val_ratio=0.0,
        test_ratio=0.0,
    )

    # Corrupt frozen payload with an impossible score > max_score (e.g. 99.0 on a 10.0 scale)
    corrupted_train = list(dv.frozen_split_payloads["train"])
    corrupted_train[0]["target"]["score"] = 99.0
    dv.frozen_split_payloads["train"] = corrupted_train
    db.flush()

    report = DatasetValidator.validate_dataset_version(db, v_tag)
    assert report.score_bounds_passed is False
    assert report.is_valid is False
    assert any("out of bounds" in err for err in report.validation_errors)


def test_sft_formatter_score_normalization():
    # Test with target final_percentage
    raw_ex1 = {
        "question": "Q1",
        "student_answer": "A1",
        "max_score": 10.0,
        "target": {
            "score": 8.0,
            "final_percentage": 80.0,
            "feedback": "Bagus",
        },
    }
    sft1 = SftFormatter.format_single_example(raw_ex1)
    assistant_json1 = json.loads(sft1.messages[2].content)
    assert assistant_json1["normalized_score"] == 0.80

    # Test fallback normalization from score / max_score
    raw_ex2 = {
        "question": "Q2",
        "student_answer": "A2",
        "max_score": 20.0,
        "target": {
            "score": 15.0,
            "feedback": "Cukup baik",
        },
    }
    sft2 = SftFormatter.format_single_example(raw_ex2)
    assistant_json2 = json.loads(sft2.messages[2].content)
    assert assistant_json2["normalized_score"] == 0.75


def test_tokenization_config_defaults_and_options():
    default_cfg = TokenizationConfig()
    assert default_cfg.max_seq_length == 2048
    assert default_cfg.padding_side == "right"
    assert default_cfg.chat_template_format == "chatml"
    assert default_cfg.mask_prompt_labels is True

    custom_cfg = TokenizationConfig(
        model_name_or_path="meta-llama/Llama-3.1-8B-Instruct",
        max_seq_length=4096,
        chat_template_format="llama3",
        mask_prompt_labels=False,
    )
    assert custom_cfg.max_seq_length == 4096
    assert custom_cfg.chat_template_format == "llama3"
    assert custom_cfg.mask_prompt_labels is False


def test_sha256_mock_tokenizer_deterministic_across_invocations():
    text = "Mitokondria adalah organel tempat respirasi seluler dan pembentukan ATP."
    cfg = TokenizationConfig(use_real_tokenizer=False)

    encoded_1, _ = TokenizerService.encode_text(text, cfg)
    encoded_2, _ = TokenizerService.encode_text(text, cfg)

    assert len(encoded_1) > 0
    assert encoded_1 == encoded_2
    assert all(100 <= tok_id <= 100022 for tok_id in encoded_1)


def test_dataset_validator_detects_semantic_group_leakage(db: Session):
    attempt, questions, teacher, student, school, subj = setup_exam_environment(
        db, school_name="SMA Group Leakage Test"
    )
    ExamService.submit_attempt(db, attempt.id)

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
        feedback="Uraian konsep sangat memuaskan.",
        teacher_account_id=teacher.id,
    )
    h = assessment_history_repository.get_current_by_evaluation(db, essay_eval.id)
    TrainingCandidateService.evaluate_and_ingest_history(db, h.id, created_by_user_id=teacher.id)

    v_tag = f"v_grp_leak_{uuid.uuid4().hex[:4]}"
    dv = DatasetBuilderService.build_dataset_version(
        db=db,
        version_tag=v_tag,
        school_id=school.id,
        train_ratio=1.0,
        val_ratio=0.0,
        test_ratio=0.0,
    )

    # Intentionally duplicate question payload into test split with different candidate ID to simulate semantic leakage
    dup_item = dict(dv.frozen_split_payloads["train"][0])
    dup_item["candidate_id"] = 999999  # Disjoint candidate ID
    dv.frozen_split_payloads["test"] = [dup_item]
    dv.split_manifest["test"] = [999999]
    db.flush()

    report = DatasetValidator.validate_dataset_version(db, v_tag)
    assert report.group_disjoint_passed is False
    assert report.is_valid is False
    assert any("Semantic data leakage detected" in err for err in report.validation_errors)


def test_dataset_validator_fails_on_target_truncation(db: Session):
    attempt, questions, teacher, student, school, subj = setup_exam_environment(
        db, school_name="SMA Truncation Gate Test"
    )
    ExamService.submit_attempt(db, attempt.id)

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
        feedback="Uraian konsep sangat memuaskan dan komprehensif.",
        teacher_account_id=teacher.id,
    )
    h = assessment_history_repository.get_current_by_evaluation(db, essay_eval.id)
    TrainingCandidateService.evaluate_and_ingest_history(db, h.id, created_by_user_id=teacher.id)

    v_tag = f"v_trunc_gate_{uuid.uuid4().hex[:4]}"
    DatasetBuilderService.build_dataset_version(
        db=db,
        version_tag=v_tag,
        school_id=school.id,
        train_ratio=1.0,
        val_ratio=0.0,
        test_ratio=0.0,
    )

    # Set extremely small sequence length (e.g. 20 tokens) so truncation cuts into assistant response
    tight_config = TokenizationConfig(
        max_seq_length=20,
        fail_on_target_truncation=True,
        use_real_tokenizer=False,
    )

    report = DatasetValidator.validate_dataset_version(db, v_tag, token_config=tight_config)
    assert report.is_valid is False
    assert any("Target truncation policy failure" in err for err in report.validation_errors)


def test_dataset_validator_fails_on_truncation_rate_exceeded(db: Session):
    attempt, questions, teacher, student, school, subj = setup_exam_environment(
        db, school_name="SMA Truncation Rate Test"
    )
    ExamService.submit_attempt(db, attempt.id)

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
        feedback="Uraian konsep sangat memuaskan.",
        teacher_account_id=teacher.id,
    )
    h = assessment_history_repository.get_current_by_evaluation(db, essay_eval.id)
    TrainingCandidateService.evaluate_and_ingest_history(db, h.id, created_by_user_id=teacher.id)

    v_tag = f"v_trunc_rate_{uuid.uuid4().hex[:4]}"
    DatasetBuilderService.build_dataset_version(
        db=db,
        version_tag=v_tag,
        school_id=school.id,
        train_ratio=1.0,
        val_ratio=0.0,
        test_ratio=0.0,
    )

    # Allow target truncation but disallow > 0% truncation rate
    strict_rate_config = TokenizationConfig(
        max_seq_length=30,
        max_truncation_rate_pct=0.0,
        fail_on_target_truncation=False,
        use_real_tokenizer=False,
    )

    report = DatasetValidator.validate_dataset_version(db, v_tag, token_config=strict_rate_config)
    assert report.is_valid is False
    assert any("Truncation rate policy failure" in err for err in report.validation_errors)


def test_dataset_validator_assert_training_ready_raises_preflight_error(db: Session):
    attempt, questions, teacher, student, school, subj = setup_exam_environment(
        db, school_name="SMA Hard Stop Gate Test"
    )
    ExamService.submit_attempt(db, attempt.id)

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
        feedback="Uraian konsep sangat memuaskan.",
        teacher_account_id=teacher.id,
    )
    h = assessment_history_repository.get_current_by_evaluation(db, essay_eval.id)
    TrainingCandidateService.evaluate_and_ingest_history(db, h.id, created_by_user_id=teacher.id)

    v_tag = f"v_preflight_stop_{uuid.uuid4().hex[:4]}"
    dv = DatasetBuilderService.build_dataset_version(
        db=db,
        version_tag=v_tag,
        school_id=school.id,
        train_ratio=1.0,
        val_ratio=0.0,
        test_ratio=0.0,
    )

    # Corrupt score to trigger failure
    dv.frozen_split_payloads["train"][0]["target"]["score"] = -5.0
    db.flush()

    with pytest.raises(
        TrainingPreflightError, match="Training pre-flight gate rejected DatasetVersion"
    ):
        DatasetValidator.assert_training_ready(db, v_tag)


def test_dataset_loader_exact_unicode_hash_compatibility_with_a8(db: Session):
    attempt, questions, teacher, student, school, subj = setup_exam_environment(
        db, school_name="SMA Unicode Hash Test"
    )
    ExamService.submit_attempt(db, attempt.id)

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
        feedback="Uraian konsep: fotosintesis ✓ reaksi terang & gelap “Calvin Cycle” élan vital 中文.",
        teacher_account_id=teacher.id,
    )
    h = assessment_history_repository.get_current_by_evaluation(db, essay_eval.id)
    TrainingCandidateService.evaluate_and_ingest_history(db, h.id, created_by_user_id=teacher.id)

    v_tag = f"v_unicode_hash_{uuid.uuid4().hex[:4]}"
    dv = DatasetBuilderService.build_dataset_version(
        db=db,
        version_tag=v_tag,
        school_id=school.id,
        train_ratio=1.0,
        val_ratio=0.0,
        test_ratio=0.0,
    )

    # DatasetLoader MUST match A8's registered dataset_hash with 100% byte-for-byte exactness
    splits = DatasetLoader.load_from_database(db, v_tag, verify_hash=True)
    assert "train" in splits
    assert "Calvin Cycle" in splits["train"][0]["target"]["feedback"]


def test_strict_real_training_mode_raises_when_hf_unavailable():
    cfg = TokenizationConfig(
        model_name_or_path="nonexistent-model-organization/invalid-weights-repo-404",
        execution_mode="REAL_TRAINING",
    )
    with pytest.raises(
        RuntimeError,
        match="Real HuggingFace AutoTokenizer is strictly required in REAL_TRAINING mode",
    ):
        TokenizerService.encode_text("Sample text to encode", cfg)


def test_prompt_first_truncation_preserves_assistant_target():
    example = SftConversationExample(
        messages=[
            SftMessage(role="system", content="System instruction" * 5),
            SftMessage(role="user", content="Detailed question " * 20),
            SftMessage(role="assistant", content='{"score": 9.5, "feedback": "Teacher target"}'),
        ]
    )

    cfg = TokenizationConfig(
        max_seq_length=40,
        truncation_strategy="prompt_first",
        use_real_tokenizer=False,
    )

    sample = TokenizerService.tokenize_conversation(example, cfg)
    assert sample.is_truncated is True
    assert sample.target_is_truncated is False
    assert len(sample.input_ids) <= 40
    # Assistant target tokens must be present at the end of the input_ids
    assert sample.labels[-1] != -100


def test_temporal_split_allows_group_overlap_for_generalization(db: Session):
    attempt, questions, teacher, student, school, subj = setup_exam_environment(
        db, school_name="SMA Temporal Generalization Test"
    )
    ExamService.submit_attempt(db, attempt.id)

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
        feedback="Uraian konsep sangat baik.",
        teacher_account_id=teacher.id,
    )
    h = assessment_history_repository.get_current_by_evaluation(db, essay_eval.id)
    TrainingCandidateService.evaluate_and_ingest_history(db, h.id, created_by_user_id=teacher.id)

    v_tag = f"v_temporal_gen_{uuid.uuid4().hex[:4]}"
    dv = DatasetBuilderService.build_dataset_version(
        db=db,
        version_tag=v_tag,
        school_id=school.id,
        split_strategy="TEMPORAL_SPLIT",
        train_ratio=1.0,
        val_ratio=0.0,
        test_ratio=0.0,
    )

    # Intentionally insert duplicate question with separate candidate ID into test split
    dup_item = dict(dv.frozen_split_payloads["train"][0])
    dup_item["candidate_id"] = 888888
    dv.frozen_split_payloads["test"] = [dup_item]
    dv.split_manifest["test"] = [888888]

    import hashlib

    dv.dataset_hash = hashlib.sha256(
        json.dumps(dv.frozen_split_payloads, sort_keys=True).encode("utf-8")
    ).hexdigest()
    dv.manifest_hash = hashlib.sha256(
        json.dumps(dv.split_manifest, sort_keys=True).encode("utf-8")
    ).hexdigest()
    db.flush()

    # For TEMPORAL_SPLIT, group overlap across time is permitted and valid
    report = DatasetValidator.validate_dataset_version(db, v_tag)
    assert report.is_valid is True
    assert report.disjoint_check_passed is True
