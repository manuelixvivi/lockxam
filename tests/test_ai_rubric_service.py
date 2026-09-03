from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.services.ai.rubric.rubric_schema import (
    RubricGenerateRequest,
    RubricGenerateResponse,
)
from app.services.ai.rubric.rubric_service import RubricService
from main import app

client = TestClient(app)


def test_rubric_generation_success():
    mock_llm_data = {
        "question_type": "PROSEDURAL",
        "bloom_level": "C3",
        "complexity_score": 65,
        "concepts": ["fotosintesis", "klorofil", "glukosa"],
        "rubric": [
            {
                "ku_id": "C1",
                "text": "Menjelaskan peran klorofil dalam menyerap energi cahaya",
                "weight": 50,
                "bloom_level": "C3",
                "required_concepts": ["klorofil", "cahaya"],
                "acceptable_variations": ["pigmen hijau"],
                "partial_credit_rules": [],
            },
            {
                "ku_id": "C2",
                "text": "Menjelaskan pembentukan glukosa dan oksigen dari CO2 dan air",
                "weight": 50,
                "bloom_level": "C3",
                "required_concepts": ["glukosa", "oksigen"],
                "acceptable_variations": [],
                "partial_credit_rules": [],
            },
        ],
    }

    with patch(
        "app.services.ai.shared.llm_client.LlmClient.call_chat_completion",
        return_value={"status": "success", "data": mock_llm_data, "model": "openai/gpt-oss-120b"},
    ):
        req = RubricGenerateRequest(
            question="Jelaskan proses fotosintesis pada tumbuhan hijau secara detail!",
            answer_key="Klorofil menyerap cahaya untuk mengubah air dan CO2 menjadi glukosa dan O2.",
            subject="Biologi",
            grade_level="SMA",
            education_class="Kelas 11",
        )
        res = RubricService.generate_rubric(req)

        assert isinstance(res, RubricGenerateResponse)
        assert res.status == "success"
        assert res.question_type == "PROSEDURAL"
        assert len(res.rubric) == 2
        assert sum(r["weight"] for r in res.rubric) == pytest.approx(100.0, 0.01)
        assert "fotosintesis" in res.concepts


def test_rubric_generation_empty_input_raises_error():
    req = RubricGenerateRequest(
        question="",
        question_text="",
        answer_key="",
    )
    with pytest.raises(ValueError, match="Either 'question' or 'answer_key' must be provided"):
        RubricService.generate_rubric(req)


def test_rubric_weight_normalization_and_deduplication():
    raw_rubrics = [
        {"ku_id": "C1", "text": "Menjelaskan konsep A", "weight": 30.0},
        {"ku_id": "C2", "text": "Menjelaskan konsep B", "weight": 30.0},
        {"ku_id": "C3", "text": "Menjelaskan konsep A", "weight": 10.0},  # Duplicate text
    ]
    normalized = RubricService._normalize_and_validate_rubrics(raw_rubrics)
    assert len(normalized) == 2
    assert sum(r["weight"] for r in normalized) == pytest.approx(100.0, 0.01)


def test_api_rubric_generate_endpoint():
    mock_llm_data = {
        "question_type": "PROSEDURAL",
        "bloom_level": "C4",
        "complexity_score": 70,
        "concepts": ["hukum ohm", "tegangan", "arus", "hambatan"],
        "rubric": [
            {
                "ku_id": "C1",
                "text": "Menuliskan rumus dan hubungan V = I x R secara tepat",
                "weight": 100,
                "bloom_level": "C4",
            }
        ],
    }

    with patch(
        "app.services.ai.shared.llm_client.LlmClient.call_chat_completion",
        return_value={"status": "success", "data": mock_llm_data, "model": "openai/gpt-oss-120b"},
    ):
        response = client.post(
            "/api/v1/ai/rubric/generate",
            json={
                "question": "Jelaskan bunyi Hukum Ohm dan tuliskan persamaan matematisnya!",
                "answer_key": "Hukum Ohm menyatakan bahwa arus berbanding lurus dengan tegangan: V = I x R.",
                "subject": "Fisika",
                "grade_level": "SMA",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert len(data["rubric"]) == 1
        assert data["rubric"][0]["weight"] == 100.0
