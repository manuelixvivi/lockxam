from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.services.ai.ai_grading_service import AiGradingService
from app.services.ai.grading.grading_schema import (
    GradingEvaluateRequest,
    GradingEvaluateResponse,
)
from app.services.ai.grading.grading_service import GradingService
from main import app

client = TestClient(app)


def test_grading_essay_rag_off():
    mock_llm_data = {
        "feedback": "Penjelasan sangat baik dan mencakup seluruh aspek rubrik.",
        "rubric_scores": [
            {"ku_id": "C1", "achieved": 100},
            {"ku_id": "C2", "achieved": 80},
        ],
    }

    with patch(
        "app.services.ai.shared.llm_client.LlmClient.call_chat_completion",
        return_value={"status": "success", "data": mock_llm_data, "model": "openai/gpt-oss-120b"},
    ):
        req = GradingEvaluateRequest(
            question="Jelaskan mekanisme transpor aktif pada membran sel!",
            answer_key="Transpor aktif membutuhkan energi ATP untuk memindahkan molekul melawan gradien konsentrasi.",
            student_answer="Transpor aktif adalah perpindahan zat melintasi membran sel yang melawan gradien konsentrasi dan memerlukan energi berupa ATP.",
            rubrics=[
                {"ku_id": "C1", "text": "Menyebutkan kebutuhan energi ATP", "weight": 50.0},
                {
                    "ku_id": "C2",
                    "text": "Menjelaskan arah melawan gradien konsentrasi",
                    "weight": 50.0,
                },
            ],
            rag_enabled=False,
            max_score=10.0,
        )
        res = GradingService.evaluate(req)

        assert isinstance(res, GradingEvaluateResponse)
        assert res.status == "success"
        assert res.final_score == 90.0  # (100*0.5 + 80*0.5)
        assert res.score == 9.0  # 90% of max_score 10.0
        assert res.rag_enabled is False
        assert len(res.retrieved_cases) == 0


def test_grading_essay_rag_on_with_context():
    mock_llm_data = {
        "feedback": "Jawaban terstruktur rapi sesuai standar penilaian guru terdahulu.",
        "rubric_scores": [
            {"ku_id": "C1", "achieved": 100},
        ],
    }

    mock_rag_payload = MagicMock()
    mock_rag_payload.formatted_context_block = (
        "<REFERENCE_CASES><CASE id='1'>Contoh jawaban lama</CASE></REFERENCE_CASES>"
    )
    mock_rag_payload.metadata = {"retrieved_count": 1, "included_count": 1}
    case_mock = MagicMock()
    case_mock.assessment_history_id = 101
    case_mock.similarity_score = 0.942
    case_mock.question_text = "Jelaskan siklus Krebs!"
    case_mock.student_answer = "Contoh jawaban lama"
    mock_rag_payload.reference_cases = [case_mock]
    mock_rag_payload.total_tokens_consumed = 120

    with (
        patch(
            "app.services.ai.rag_context_service.RagContextService.assemble_rag_context",
            return_value=mock_rag_payload,
        ),
        patch(
            "app.services.ai.shared.llm_client.LlmClient.call_chat_completion",
            return_value={
                "status": "success",
                "data": mock_llm_data,
                "model": "openai/gpt-oss-120b",
            },
        ),
    ):
        req = GradingEvaluateRequest(
            question="Jelaskan siklus Krebs!",
            answer_key="Tahapan respirasi aerob di matriks mitokondria yang menghasilkan NADH, FADH2, dan ATP.",
            student_answer="Siklus krebs terjadi di mitokondria menghasilkan NADH dan FADH2.",
            rubrics=[{"ku_id": "C1", "text": "Menjelaskan siklus krebs", "weight": 100.0}],
            rag_enabled=True,
            school_id=1,
            subject_id=2,
            academic_year_id=3,
            max_score=20.0,
        )
        mock_db = MagicMock()
        res = GradingService.evaluate(req, db=mock_db)

        assert res.rag_enabled is True
        assert res.final_score == 100.0
        assert res.score == 20.0
        assert len(res.retrieved_cases) == 1
        assert res.retrieved_cases[0]["case_id"] == 101


def test_grading_failsafe_fallback_on_rag_error():
    mock_llm_data = {
        "feedback": "Penilaian standar non-RAG berhasil.",
        "rubric_scores": [{"ku_id": "C1", "achieved": 75}],
    }

    with (
        patch(
            "app.services.ai.rag_context_service.RagContextService.assemble_rag_context",
            side_effect=RuntimeError("Database connection lost"),
        ),
        patch(
            "app.services.ai.shared.llm_client.LlmClient.call_chat_completion",
            return_value={
                "status": "success",
                "data": mock_llm_data,
                "model": "openai/gpt-oss-120b",
            },
        ),
    ):
        req = GradingEvaluateRequest(
            question="Jelaskan pembelahan mitosis!",
            student_answer="Mitosis menghasilkan dua sel anakan yang identik secara genetik.",
            rubrics=[{"ku_id": "C1", "text": "Karakteristik sel anakan", "weight": 100.0}],
            rag_enabled=True,
            school_id=1,
            subject_id=2,
            academic_year_id=3,
        )
        mock_db = MagicMock()
        res = GradingService.evaluate(req, db=mock_db)

        assert res.status == "success"
        assert res.final_score == 75.0
        assert res.rag_metadata.get("fallback_used") is True


def test_grading_empty_student_answer():
    req = GradingEvaluateRequest(
        question="Pertanyaan esai",
        student_answer="   ",
        max_score=15.0,
    )
    res = GradingService.evaluate(req)

    assert res.score == 0.0
    assert res.final_score == 0.0
    assert "kosong" in res.feedback.lower()


def test_grading_short_answer_question():
    mock_llm_data = {
        "matched_items": ["Sentrosom", "Lisosom"],
        "feedback": "Bagus, berhasil menyebutkan 2 organel khas sel hewan.",
    }

    with patch(
        "app.services.ai.shared.llm_client.LlmClient.call_chat_completion",
        return_value={"status": "success", "data": mock_llm_data, "model": "openai/gpt-oss-120b"},
    ):
        req = GradingEvaluateRequest(
            question="Sebutkan 2 organel yang hanya terdapat pada sel hewan!",
            answer_key="Sentrosom, Lisosom",
            student_answer="Sentrosom dan lisosom",
            question_type="short_answer",
            concepts=["Sentrosom", "Lisosom"],
            max_score=10.0,
        )
        res = GradingService.evaluate(req)

        assert res.status == "success"
        assert res.matched_items == ["Sentrosom", "Lisosom"]
        assert res.final_score == 100.0


def test_backward_compatibility_facade():
    mock_llm_data = {
        "feedback": "Penilaian esai via facade berhasil.",
        "rubric_scores": [{"ku_id": "C1", "achieved": 85}],
    }

    with patch(
        "app.services.ai.shared.llm_client.LlmClient.call_chat_completion",
        return_value={"status": "success", "data": mock_llm_data, "model": "openai/gpt-oss-120b"},
    ):
        legacy_res = AiGradingService.grade_essay(
            question_text="Jelaskan fotosintesis!",
            answer_key="Klorofil menyerap cahaya.",
            student_answer="Klorofil mengubah cahaya.",
            rubrics=[{"ku_id": "C1", "text": "Klorofil", "weight": 100}],
            max_score=10.0,
        )

        assert isinstance(legacy_res, dict)
        assert legacy_res["status"] == "success"
        assert legacy_res["final_score"] == 85.0
        assert legacy_res["score"] == 8.5
        assert "facade" in legacy_res["feedback"]


def test_api_grading_evaluate_endpoint():
    from app.core.dependencies import get_current_user

    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "1",
        "role": "TEACHER",
        "school_id": 1,
    }
    mock_llm_data = {
        "feedback": "Jawaban sangat tepat.",
        "rubric_scores": [{"ku_id": "C1", "achieved": 100}],
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
                "/api/v1/ai/grading/evaluate",
                json={
                    "question": "Jelaskan definisi Hukum Newton I!",
                    "answer_key": "Benda diam tetap diam jika gaya total nol.",
                    "student_answer": "Benda akan tetap diam jika tidak ada gaya luar yang bekerja.",
                    "rubrics": [{"ku_id": "C1", "text": "Kelembaman benda", "weight": 100.0}],
                    "max_score": 10.0,
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["final_score"] == 100.0
            assert data["score"] == 10.0
    finally:
        app.dependency_overrides.pop(get_current_user, None)
