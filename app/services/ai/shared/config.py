import os
from typing import Optional


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

    @classmethod
    def is_rag_enabled(cls, override: Optional[bool] = None) -> bool:
        if override is not None:
            return override
        return os.environ.get("RAG_ENABLED", "false").lower() in ("true", "1", "yes")

    @classmethod
    def get_effective_api_key(cls, explicit_key: Optional[str] = None) -> str:
        """Strict server-side GROQ_API_KEY security boundary."""
        return cls.GROQ_API_KEY or explicit_key or ""
