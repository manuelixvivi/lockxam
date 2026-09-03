from unittest.mock import patch

from fastapi.testclient import TestClient

from app.services.ai.validation.validation_schema import (
    RubricValidateRequest,
    RubricValidateResponse,
    ValidationStatus,
)
from app.services.ai.validation.validation_service import ValidationService
from main import app

client = TestClient(app)


def test_validation_consistent_valid():
    mock_llm_data = {
        "status": "VALID",
        "confidence": 0.98,
        "reason": "Kunci jawaban dan rubrik sangat konsisten dan tepat menjawab fungsi mitokondria.",
        "issues": [],
        "suggested_review": False,
    }

    with patch(
        "app.services.ai.shared.llm_client.LlmClient.call_chat_completion",
        return_value={"status": "success", "data": mock_llm_data, "model": "openai/gpt-oss-120b"},
    ):
        req = RubricValidateRequest(
            question="Jelaskan fungsi utama organel mitokondria dalam sel!",
            answer_key="Mitokondria berfungsi sebagai tempat respirasi seluler untuk menghasilkan energi dalam bentuk ATP.",
            rubric=[
                {"ku_id": "C1", "text": "Menjelaskan respirasi sel dan produksi ATP", "weight": 100}
            ],
            subject="Biologi",
            grade_level="SMA",
        )
        res = ValidationService.validate_rubric_and_key(req)

        assert isinstance(res, RubricValidateResponse)
        assert res.status == ValidationStatus.VALID
        assert res.confidence >= 0.90
        assert res.suggested_review is False
        assert len(res.issues) == 0


def test_validation_equivalent_concept_valid():
    mock_llm_data = {
        "status": "VALID",
        "confidence": 0.92,
        "reason": "Konsep 'pembangkit tenaga sel' dan 'sintesis energi' setara dengan fungsi respirasi seluler mitokondria.",
        "issues": [],
        "suggested_review": False,
    }

    with patch(
        "app.services.ai.shared.llm_client.LlmClient.call_chat_completion",
        return_value={"status": "success", "data": mock_llm_data, "model": "openai/gpt-oss-120b"},
    ):
        req = RubricValidateRequest(
            question="Jelaskan fungsi mitokondria!",
            answer_key="Organel yang bertindak sebagai powerhouse sel dalam memproduksi energi.",
            subject="Biologi",
        )
        res = ValidationService.validate_rubric_and_key(req)

        assert res.status == ValidationStatus.VALID
        assert res.suggested_review is False


def test_validation_ambiguous_suspicious():
    mock_llm_data = {
        "status": "SUSPICIOUS",
        "confidence": 0.75,
        "reason": "Kunci jawaban menyebutkan 'proses sel' tanpa merinci organel atau mekanisme spesifik yang diminta soal.",
        "issues": [
            {
                "severity": "WARNING",
                "category": "AMBIGUITY",
                "description": "Kunci jawaban terlalu singkat dan multitafsir.",
                "suggestion": "Perjelas mekanisme pembentukan ATP pada kunci jawaban.",
            }
        ],
        "suggested_review": True,
    }

    with patch(
        "app.services.ai.shared.llm_client.LlmClient.call_chat_completion",
        return_value={"status": "success", "data": mock_llm_data, "model": "openai/gpt-oss-120b"},
    ):
        req = RubricValidateRequest(
            question="Jelaskan secara mendalam proses pembentukan ATP di mitokondria!",
            answer_key="Proses sel.",
            subject="Biologi",
        )
        res = ValidationService.validate_rubric_and_key(req)

        assert res.status == ValidationStatus.SUSPICIOUS
        assert res.suggested_review is True
        assert len(res.issues) == 1


def test_validation_contradiction_invalid():
    mock_llm_data = {
        "status": "INVALID",
        "confidence": 0.99,
        "reason": "Kontradiksi fatal: Soal menanyakan fungsi mitokondria tetapi kunci jawaban dan rubrik menjelaskan fotosintesis pada kloroplas.",
        "issues": [
            {
                "severity": "ERROR",
                "category": "CONTRADICTION",
                "description": "Topik kunci jawaban sama sekali tidak sesuai dengan pertanyaan.",
                "suggestion": "Ganti kunci jawaban dengan materi respirasi seluler mitokondria.",
            }
        ],
        "suggested_review": True,
    }

    with patch(
        "app.services.ai.shared.llm_client.LlmClient.call_chat_completion",
        return_value={"status": "success", "data": mock_llm_data, "model": "openai/gpt-oss-120b"},
    ):
        req = RubricValidateRequest(
            question="Jelaskan fungsi mitokondria!",
            answer_key="Menyerap sinar matahari untuk melakukan fotosintesis dan menghasilkan glukosa melalui kloroplas.",
            subject="Biologi",
        )
        res = ValidationService.validate_rubric_and_key(req)

        assert res.status == ValidationStatus.INVALID
        assert res.suggested_review is True
        assert len(res.issues) == 1
        assert res.issues[0].severity == "ERROR"


def test_api_rubric_validate_endpoint():
    mock_llm_data = {
        "status": "VALID",
        "confidence": 0.96,
        "reason": "Kunci jawaban matematika konsisten.",
        "issues": [],
        "suggested_review": False,
    }

    with patch(
        "app.services.ai.shared.llm_client.LlmClient.call_chat_completion",
        return_value={"status": "success", "data": mock_llm_data, "model": "openai/gpt-oss-120b"},
    ):
        response = client.post(
            "/api/v1/ai/rubric/validate",
            json={
                "question": "Berapa hasil dari 2 + 2?",
                "answer_key": "4",
                "subject": "Matematika",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "VALID"
        assert data["confidence"] == 0.96
        assert data["suggested_review"] is False
