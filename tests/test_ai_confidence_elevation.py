from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest

from app.services.ai.grading.grading_schema import (
    GradingEvaluateRequest,
    GradingEvaluateResponse,
)
from app.services.ai.grading.batch_grading_schema import (
    BatchStudentGradingResult,
)
from app.services.ai.grading.grading_service import GradingService
from app.api.teacher import (
    EssayGradingEvaluationResponse,
    _derive_ai_evaluation_metadata,
)
from app.models.exam.enums import GradingStatus, GradingSource


class TestAiConfidenceElevationSchemas:
    def test_grading_evaluate_response_root_fields(self):
        """Ensure GradingEvaluateResponse contains root-level confidence attributes."""
        res = GradingEvaluateResponse(
            status="success",
            score=9.5,
            final_score=95.0,
            max_score=10.0,
            feedback="Sangat komprehensif.",
            decision={"status": "EVALUATED", "quality_indicator": 0.95},
            confidence=0.95,
            confidence_level="HIGH",
            review_required=False,
            academic_rationale="Kesesuaian konsep memenuhi standar.",
        )
        assert res.confidence == 0.95
        assert res.confidence_level == "HIGH"
        assert res.review_required is False
        assert res.academic_rationale == "Kesesuaian konsep memenuhi standar."

    def test_grading_evaluate_response_model_validator_derivation(self):
        """Ensure model validator derives root confidence if not explicitly passed."""
        res = GradingEvaluateResponse(
            status="success",
            score=7.0,
            final_score=70.0,
            max_score=10.0,
            feedback="Cukup baik.",
            decision={"status": "PARTIAL_EVALUATED", "quality_indicator": 0.65},
        )
        assert res.confidence == 0.65
        assert res.confidence_level == "LOW"
        assert res.review_required is True
        assert res.academic_rationale is not None

    def test_batch_student_grading_result_root_fields(self):
        """Ensure BatchStudentGradingResult has root-level confidence attributes."""
        result = BatchStudentGradingResult(
            student_id=101,
            score=8.5,
            final_score=85.0,
            feedback="Pemahaman baik.",
            quality_indicator=0.85,
        )
        assert result.confidence == 0.85
        assert result.confidence_level == "MEDIUM"
        assert result.review_required is True
        assert result.academic_rationale == "Pemahaman baik."

    def test_batch_student_grading_result_high_confidence(self):
        result = BatchStudentGradingResult(
            student_id=102,
            score=10.0,
            final_score=100.0,
            feedback="Sempurna.",
            quality_indicator=0.95,
        )
        assert result.confidence == 0.95
        assert result.confidence_level == "HIGH"
        assert result.review_required is False


class TestGradingServiceConfidenceElevation:
    def test_evaluate_high_confidence(self):
        """GradingService produces HIGH confidence (>= 0.90) and review_required == False."""
        mock_llm_data = {
            "feedback": "Penjelasan sangat lengkap.",
            "rubric_scores": [
                {"ku_id": "C1", "achieved": 100},
                {"ku_id": "C2", "achieved": 100},
            ],
            "academic_rationale": "Seluruh konsep transpor aktif dijelaskan dengan tepat.",
        }

        with patch(
            "app.services.ai.shared.llm_client.LlmClient.call_chat_completion",
            return_value={"status": "success", "data": mock_llm_data, "model": "openai/gpt-oss-120b"},
        ):
            req = GradingEvaluateRequest(
                question="Jelaskan mekanisme transpor aktif!",
                answer_key="Membutuhkan ATP melawan gradien.",
                student_answer="Transpor aktif membutuhkan energi ATP untuk melawan gradien konsentrasi.",
                rubrics=[
                    {"ku_id": "C1", "text": "ATP", "weight": 50.0},
                    {"ku_id": "C2", "text": "Gradien", "weight": 50.0},
                ],
                concepts=["ATP", "gradien"],
                rag_enabled=False,
                max_score=10.0,
            )
            res = GradingService.evaluate(req)

            assert isinstance(res, GradingEvaluateResponse)
            assert res.confidence >= 0.90
            assert res.confidence_level == "HIGH"
            assert res.review_required is False
            assert "Seluruh konsep" in (res.academic_rationale or "")
            assert res.decision["confidence_level"] == "HIGH"
            assert res.decision["review_required"] is False

    def test_evaluate_medium_confidence(self):
        """GradingService produces MEDIUM confidence (0.75 - 0.89) when completeness is lower."""
        mock_llm_data = {
            "feedback": "Sebagian besar kriteria terjawab.",
            "rubric_scores": [
                {"ku_id": "C1", "achieved": 80},
                {"ku_id": "C2", "achieved": 80},
                {"ku_id": "C3", "achieved": 80},
            ],
        }

        with patch(
            "app.services.ai.shared.llm_client.LlmClient.call_chat_completion",
            return_value={"status": "success", "data": mock_llm_data, "model": "openai/gpt-oss-120b"},
        ):
            req = GradingEvaluateRequest(
                question="Jelaskan tahapan respirasi seluler!",
                answer_key="Glikolisis, dekarboksilasi, siklus krebs, transpor elektron.",
                student_answer="Respirasi seluler terdiri dari glikolisis dan siklus krebs di mitokondria.",
                rubrics=[
                    {"ku_id": "C1", "text": "Glikolisis", "weight": 25.0},
                    {"ku_id": "C2", "text": "Dekarboksilasi", "weight": 25.0},
                    {"ku_id": "C3", "text": "Krebs", "weight": 25.0},
                    {"ku_id": "C4", "text": "Transpor elektron", "weight": 25.0},
                ],
                concepts=["glikolisis", "krebs"],
                rag_enabled=False,
                max_score=10.0,
            )
            res = GradingService.evaluate(req)

            assert 0.0 <= res.confidence <= 1.0
            assert res.confidence_level in ("MEDIUM", "LOW")
            assert res.review_required is True
            assert res.academic_rationale is not None

    def test_evaluate_empty_student_answer(self):
        """Empty student answer deterministically yields confidence=1.0, HIGH, review_required=False."""
        req = GradingEvaluateRequest(
            question="Jelaskan teori atom Bohr!",
            answer_key="Elektron mengelilingi inti pada lintasan tertentu.",
            student_answer="",
            rubrics=[{"ku_id": "C1", "text": "Lintasan stasioner", "weight": 100.0}],
            rag_enabled=False,
            max_score=10.0,
        )
        res = GradingService.evaluate(req)

        assert res.score == 0.0
        assert res.confidence == 1.0
        assert res.confidence_level == "HIGH"
        assert res.review_required is False
        assert "kosong" in res.feedback.lower()
        assert res.academic_rationale is not None


class TestTeacherEvaluationMetadataDerivation:
    def test_derive_ai_evaluation_metadata_high_score(self):
        mock_ev = MagicMock()
        mock_ev.score = 9.5
        mock_ev.max_score = 10.0
        mock_ev.grading_status = GradingStatus.AI_DRAFT
        mock_ev.feedback = "Jawaban sangat memuaskan."

        mock_q = MagicMock()
        mock_q.rubrics = [
            {"ku_id": "C1", "text": "Analisis", "weight": 50.0},
            {"ku_id": "C2", "text": "Sintesis", "weight": 50.0},
        ]

        meta = _derive_ai_evaluation_metadata(mock_ev, mock_q, "Ini jawaban lengkap.")
        assert meta["confidence"] >= 0.90
        assert meta["confidence_level"] == "HIGH"
        assert meta["review_required"] is False
        assert len(meta["rubric_scores"]) == 2
        assert meta["rubric_scores"][0]["ku_id"] == "C1"
        assert meta["academic_rationale"] == "Jawaban sangat memuaskan."

    def test_derive_ai_evaluation_metadata_medium_score(self):
        mock_ev = MagicMock()
        mock_ev.score = 8.0
        mock_ev.max_score = 10.0
        mock_ev.grading_status = GradingStatus.AI_DRAFT
        mock_ev.feedback = None

        mock_q = MagicMock()
        mock_q.rubrics = []

        meta = _derive_ai_evaluation_metadata(mock_ev, mock_q, "Ini jawaban separuh benar.")
        assert 0.75 <= meta["confidence"] < 0.90
        assert meta["confidence_level"] == "MEDIUM"
        assert meta["review_required"] is True
        assert len(meta["rubric_scores"]) == 2
        assert "Evaluasi berbasis" in meta["academic_rationale"]

    def test_derive_ai_evaluation_metadata_low_score(self):
        mock_ev = MagicMock()
        mock_ev.score = 3.0
        mock_ev.max_score = 10.0
        mock_ev.grading_status = GradingStatus.AI_DRAFT
        mock_ev.feedback = None

        meta = _derive_ai_evaluation_metadata(mock_ev, None, "Jawaban kurang relevan.")
        assert meta["confidence"] < 0.75
        assert meta["confidence_level"] == "LOW"
        assert meta["review_required"] is True

    def test_derive_ai_evaluation_metadata_finalized(self):
        mock_ev = MagicMock()
        mock_ev.score = 7.0
        mock_ev.max_score = 10.0
        mock_ev.grading_status = GradingStatus.FINALIZED
        mock_ev.feedback = "Telah dikoreksi oleh guru."

        meta = _derive_ai_evaluation_metadata(mock_ev, None, "Jawaban.")
        assert meta["confidence"] == 1.0
        assert meta["confidence_level"] == "HIGH"
        assert meta["review_required"] is False

    def test_essay_grading_evaluation_response_schema(self):
        """Ensure EssayGradingEvaluationResponse supports root confidence attributes."""
        resp = EssayGradingEvaluationResponse(
            evaluation_id=1,
            attempt_id=10,
            schedule_id=5,
            student_name="Budi",
            exam_title="Ujian Biologi",
            class_name="XI MIPA 1",
            question_id=20,
            question_content="Jelaskan osmosis!",
            student_answer="Perpindahan pelarut.",
            ai_score=8.5,
            ai_feedback="Bagus.",
            grading_status="AI_DRAFT",
            final_score=None,
            confidence=0.88,
            confidence_level="MEDIUM",
            review_required=True,
            academic_rationale="Sebagian konsep tercakup.",
        )
        assert resp.confidence == 0.88
        assert resp.confidence_level == "MEDIUM"
        assert resp.review_required is True
        assert resp.academic_rationale == "Sebagian konsep tercakup."
