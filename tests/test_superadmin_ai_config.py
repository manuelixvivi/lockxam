import os

from app.services.ai.ai_management_service import AiManagementService
from app.services.ai.shared.config import AiConfig


def _get_superadmin_auth_headers(client, test_superadmin):
    res = client.post(
        "/api/v1/auth/login",
        json={
            "username": test_superadmin["username"],
            "password": test_superadmin["password"],
        },
    )
    assert res.status_code == 200, f"Login failed: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _get_teacher_auth_headers(client, test_teacher):
    res = client.post(
        "/api/v1/auth/login",
        json={
            "username": test_teacher["username"],
            "password": test_teacher["password"],
        },
    )
    assert res.status_code == 200, f"Teacher login failed: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_get_active_ai_config_includes_all_m3_fields(client, test_superadmin):
    """Verifies that GET /config returns eval_model_name, strict_transformer, and all RAG tuning parameters."""
    headers = _get_superadmin_auth_headers(client, test_superadmin)
    res = client.get("/api/v1/superadmin/ai-system/config", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()

    # Core AI model & evaluation parameters
    assert "eval_model_name" in data
    assert isinstance(data["eval_model_name"], str)
    assert "strict_transformer" in data
    assert isinstance(data["strict_transformer"], bool)

    # RAG Tuning Parameters
    assert "embedding_model" in data
    assert isinstance(data["embedding_model"], str)
    assert "rag_top_k" in data
    assert isinstance(data["rag_top_k"], int)
    assert "rag_similarity_threshold" in data
    assert isinstance(data["rag_similarity_threshold"], (int, float))
    assert "max_rag_tokens" in data
    assert isinstance(data["max_rag_tokens"], int)


def test_update_ai_config_persists_m3_fields(client, test_superadmin):
    """Verifies that PUT /config persists evaluation model, strict_transformer, and RAG tuning."""
    headers = _get_superadmin_auth_headers(client, test_superadmin)

    payload = {
        "provider": "Groq",
        "model_name": "llama-3.3-70b-versatile",
        "eval_model_name": "llama-3.3-70b-versatile",
        "fallback_model": "openai/gpt-oss-20b",
        "temperature": 0.35,
        "max_output_tokens": 2048,
        "rag_enabled": True,
        "strict_transformer": True,
        "embedding_model": "intfloat/multilingual-e5-large",
        "rag_top_k": 5,
        "rag_similarity_threshold": 0.85,
        "max_rag_tokens": 2048,
    }

    # 1. Update config
    put_res = client.put("/api/v1/superadmin/ai-system/config", json=payload, headers=headers)
    assert put_res.status_code == 200, put_res.text
    updated = put_res.json()

    assert updated["model_name"] == "llama-3.3-70b-versatile"
    assert updated["eval_model_name"] == "llama-3.3-70b-versatile"
    assert updated["strict_transformer"] is True
    assert updated["embedding_model"] == "intfloat/multilingual-e5-large"
    assert updated["rag_top_k"] == 5
    assert updated["rag_similarity_threshold"] == 0.85
    assert updated["max_rag_tokens"] == 2048
    assert updated["rag_enabled"] is True

    # 2. Re-read via GET to confirm database persistence
    get_res = client.get("/api/v1/superadmin/ai-system/config", headers=headers)
    assert get_res.status_code == 200
    persisted = get_res.json()

    assert persisted["eval_model_name"] == "llama-3.3-70b-versatile"
    assert persisted["strict_transformer"] is True
    assert persisted["embedding_model"] == "intfloat/multilingual-e5-large"
    assert persisted["rag_top_k"] == 5
    assert persisted["rag_similarity_threshold"] == 0.85
    assert persisted["max_rag_tokens"] == 2048

    # 3. Confirm runtime AiConfig synchronized
    assert AiConfig.EVAL_MODEL_NAME == "llama-3.3-70b-versatile"
    assert AiConfig.STRICT_TRANSFORMER is True
    assert AiConfig.MAX_RAG_CONTEXT_TOKENS == 2048


def test_get_overview_includes_ai_safety_status(client, test_superadmin):
    """Verifies that GET /overview exposes ai_safety_status with HMAC and replay indicators."""
    headers = _get_superadmin_auth_headers(client, test_superadmin)
    res = client.get("/api/v1/superadmin/ai-system/overview", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()

    assert "ai_safety_status" in data
    safety = data["ai_safety_status"]
    assert "hmac_callback_configured" in safety
    assert "webhook_secret_set" in safety
    assert "replay_protection_active" in safety

    assert isinstance(safety["hmac_callback_configured"], bool)
    assert isinstance(safety["webhook_secret_set"], bool)
    assert safety["replay_protection_active"] is True


def test_ai_safety_status_reacts_to_webhook_secret_env(db):
    """Verifies that get_overview accurately reflects the status of AI_WEBHOOK_SECRET."""
    original_secret = os.environ.get("AI_WEBHOOK_SECRET")

    try:
        # Scenario A: Secret is configured
        os.environ["AI_WEBHOOK_SECRET"] = "super-secret-hmac-key-v10"
        overview_configured = AiManagementService.get_overview(db)
        assert overview_configured.ai_safety_status["webhook_secret_set"] is True
        assert overview_configured.ai_safety_status["hmac_callback_configured"] is True
        assert overview_configured.ai_safety_status["replay_protection_active"] is True

        # Scenario B: Secret is missing or empty
        os.environ["AI_WEBHOOK_SECRET"] = ""
        overview_unconfigured = AiManagementService.get_overview(db)
        assert overview_unconfigured.ai_safety_status["webhook_secret_set"] is False
        assert overview_unconfigured.ai_safety_status["hmac_callback_configured"] is False
        assert overview_unconfigured.ai_safety_status["replay_protection_active"] is True
    finally:
        if original_secret is not None:
            os.environ["AI_WEBHOOK_SECRET"] = original_secret
        else:
            os.environ.pop("AI_WEBHOOK_SECRET", None)


def test_ai_config_history_records_m3_changes(client, test_superadmin):
    """Verifies that updating M3 parameters generates descriptive audit logs in AiConfigHistory."""
    headers = _get_superadmin_auth_headers(client, test_superadmin)

    # Perform an update with distinct parameters
    payload = {
        "provider": "Groq",
        "model_name": "mixtral-8x7b-32768",
        "eval_model_name": "llama-3.1-8b-instant",
        "fallback_model": "openai/gpt-oss-20b",
        "temperature": 0.45,
        "max_output_tokens": 1024,
        "rag_enabled": True,
        "strict_transformer": True,
        "embedding_model": "custom/bert-indonesian",
        "rag_top_k": 7,
        "rag_similarity_threshold": 0.75,
        "max_rag_tokens": 1024,
    }
    put_res = client.put("/api/v1/superadmin/ai-system/config", json=payload, headers=headers)
    assert put_res.status_code == 200

    # Fetch history
    hist_res = client.get("/api/v1/superadmin/ai-system/config/history", headers=headers)
    assert hist_res.status_code == 200
    histories = hist_res.json()
    assert len(histories) > 0

    latest_entry = histories[0]
    assert latest_entry["provider"] == "Groq"
    assert latest_entry["model_name"] == "mixtral-8x7b-32768"
    assert (
        "Evaluation model" in latest_entry["change_summary"]
        or "Konfigurasi" in latest_entry["change_summary"]
    )


def test_non_superadmin_cannot_access_or_modify_ai_config(client, test_teacher):
    """Enforces strict RBAC: Non-superadmins (teachers/students) must receive 403 Forbidden."""
    headers = _get_teacher_auth_headers(client, test_teacher)

    # Attempt GET /config
    get_res = client.get("/api/v1/superadmin/ai-system/config", headers=headers)
    assert get_res.status_code == 403, f"Expected 403, got {get_res.status_code}"

    # Attempt PUT /config
    put_res = client.put(
        "/api/v1/superadmin/ai-system/config",
        json={
            "provider": "Groq",
            "model_name": "malicious-model",
            "temperature": 0.5,
            "max_output_tokens": 1000,
        },
        headers=headers,
    )
    assert put_res.status_code == 403, f"Expected 403, got {put_res.status_code}"

    # Attempt GET /overview
    overview_res = client.get("/api/v1/superadmin/ai-system/overview", headers=headers)
    assert overview_res.status_code == 403, f"Expected 403, got {overview_res.status_code}"


def test_unauthenticated_request_rejected(client):
    """Verifies that requests without authentication token are strictly rejected with 401 Unauthorized."""
    res = client.get("/api/v1/superadmin/ai-system/config")
    assert res.status_code in (401, 403)


def test_get_available_models_live_and_fallback(client, test_superadmin, monkeypatch):
    """Verifies that GET /available-models dynamically incorporates Groq models via requests."""
    headers = _get_superadmin_auth_headers(client, test_superadmin)

    # 1. Test fallback when no live query or mock returns preset
    res = client.get("/api/v1/superadmin/ai-system/available-models", headers=headers)
    assert res.status_code == 200
    models = res.json()
    assert len(models) >= 2
    model_ids = [m["id"] for m in models]
    assert "llama-3.3-70b-versatile" in model_ids
    assert "llama-3.1-8b-instant" in model_ids

    # 2. Test live query integration with mocked requests.get
    class MockResponse:
        status_code = 200

        def json(self):
            return {
                "object": "list",
                "data": [
                    {
                        "id": "llama-3.3-70b-versatile",
                        "object": "model",
                        "active": True,
                        "context_window": 128000,
                        "owned_by": "meta",
                    },
                    {
                        "id": "qwen-2.5-coder-32b",
                        "object": "model",
                        "active": True,
                        "context_window": 32768,
                        "owned_by": "alibaba",
                    },
                    {
                        "id": "whisper-large-v3",
                        "object": "model",
                        "active": True,
                        "context_window": 448,
                        "owned_by": "openai",
                    },
                ],
            }

    import requests

    monkeypatch.setattr(requests, "get", lambda url, headers=None, timeout=None: MockResponse())

    res_live = client.get(
        "/api/v1/superadmin/ai-system/available-models?api_key=gsk_test_key_live_mock",
        headers=headers,
    )
    assert res_live.status_code == 200
    live_models = res_live.json()
    live_ids = [m["id"] for m in live_models]

    assert "llama-3.3-70b-versatile" in live_ids
    assert "qwen-2.5-coder-32b" in live_ids
    # whisper must be filtered out from CBT text grading
    assert "whisper-large-v3" not in live_ids
