import os
import time
from typing import Any, Dict, Optional


class AiConfig:
    """Central configuration for EquiGrade AI Services."""

    EQUIGRADE_AI_URL: str = os.environ.get("EQUIGRADE_AI_URL", "http://localhost:5000")
    GROQ_API_KEY: str = os.environ.get("GROQ_API_KEY", "")
    GROQ_BASE_URL: str = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    MODEL_NAME: str = os.environ.get(
        "GROQ_MODEL", os.environ.get("MODEL_NAME", "openai/gpt-oss-120b")
    )
    EVAL_MODEL_NAME: str = os.environ.get(
        "GROQ_MODEL", os.environ.get("EVAL_MODEL_NAME", "openai/gpt-oss-120b")
    )
    VALIDATION_MODEL_NAME: str = os.environ.get("VALIDATION_MODEL_NAME", "openai/gpt-oss-120b")
    GROQ_FALLBACK_MODEL: str = os.environ.get("GROQ_FALLBACK_MODEL", "openai/gpt-oss-20b")
    FAST_EVAL_MODEL_NAME: str = os.environ.get("FAST_EVAL_MODEL_NAME", "groq/compound-mini")
    BATCH_GRADING_SIZE: int = int(os.environ.get("BATCH_GRADING_SIZE", "50"))

    # RAG Feature Flag (Default: False for security & predictable cost)
    RAG_ENABLED_DEFAULT: bool = False
    MAX_RAG_CONTEXT_TOKENS: int = 1500

    # Strict Transformer Mode for Embedding
    STRICT_TRANSFORMER: bool = os.environ.get("STRICT_TRANSFORMER", "false").lower() in (
        "true",
        "1",
        "yes",
    )

    # Runtime in-process cache for DB settings (TTL 15 seconds)
    _db_cache: Dict[str, Any] = {"config": None, "last_fetched": 0.0, "ttl": 15.0}

    @classmethod
    def get_runtime_db_config(cls, db: Optional[Any] = None) -> Dict[str, Any]:
        """Resolves runtime AI configuration from persistent AiSystemSetting table (serverless-safe)."""
        now = time.time()
        if cls._db_cache["config"] is not None and (now - cls._db_cache["last_fetched"]) < cls._db_cache["ttl"]:
            return cls._db_cache["config"]

        if db is None:
            from app.core.database import SessionLocal
            try:
                with SessionLocal() as session:
                    return cls._fetch_db_config(session)
            except Exception:
                return {}
        return cls._fetch_db_config(db)

    @classmethod
    def _fetch_db_config(cls, session: Any) -> Dict[str, Any]:
        try:
            from app.models.ai.ai_system_setting import AiSystemSetting
            from app.core.security.crypto import decrypt_secret
            setting = session.query(AiSystemSetting).filter(AiSystemSetting.key == "ai_provider_config").first()
            if not setting:
                return {}
            val = dict(setting.value_json or {})
            if setting.encrypted_secret:
                decrypted = decrypt_secret(setting.encrypted_secret)
                if decrypted:
                    val["api_key"] = decrypted
            cls._db_cache["config"] = val
            cls._db_cache["last_fetched"] = time.time()
            return val
        except Exception:
            return {}

    @classmethod
    def is_rag_enabled(cls, override: Optional[bool] = None) -> bool:
        if override is not None:
            return override
        return os.environ.get("RAG_ENABLED", "false").lower() in ("true", "1", "yes")

    @classmethod
    def get_effective_api_key(cls, explicit_key: Optional[str] = None, db: Optional[Any] = None) -> str:
        """Strict server-side GROQ_API_KEY security boundary with persistent DB priority."""
        if explicit_key and explicit_key.strip():
            return explicit_key.strip()
        db_cfg = cls.get_runtime_db_config(db)
        if db_cfg.get("api_key"):
            return db_cfg["api_key"]
        return cls.GROQ_API_KEY or ""

    @classmethod
    def get_effective_model(cls, explicit_model: Optional[str] = None, db: Optional[Any] = None) -> str:
        """Returns active model with persistent DB priority."""
        if explicit_model and explicit_model.strip():
            return explicit_model.strip()
        db_cfg = cls.get_runtime_db_config(db)
        if db_cfg.get("model_name"):
            return db_cfg["model_name"]
        return cls.MODEL_NAME
