from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class AiProviderConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider: str = "Groq"
    api_key_masked: str = ""
    is_api_key_configured: bool = False
    model_name: str = "openai/gpt-oss-120b"
    eval_model_name: str = "openai/gpt-oss-120b"
    fallback_model: str = "openai/gpt-oss-20b"
    temperature: float = 0.2
    max_output_tokens: int = 4096
    rag_enabled: bool = False
    strict_transformer: bool = False
    embedding_model: str = "intfloat/multilingual-e5-large"
    rag_top_k: int = 3
    rag_similarity_threshold: float = 0.70
    max_rag_tokens: int = 1500
    last_tested_at: Optional[datetime] = None
    last_test_status: Optional[str] = None
    last_test_latency_ms: Optional[float] = None
    updated_at: Optional[datetime] = None
    updated_by_name: Optional[str] = None


class AiProviderConfigUpdateRequest(BaseModel):
    provider: str = Field(
        default="Groq", description="AI Provider identifier (Groq / OpenAI / Custom)"
    )
    api_key: Optional[str] = Field(
        default=None, description="Optional new plain API key. If omitted, retains existing secret."
    )
    model_name: str = Field(..., description="Target model name identifier")
    eval_model_name: Optional[str] = Field(
        default=None, description="Model for essay and rubric evaluation"
    )
    fallback_model: Optional[str] = Field(
        default="openai/gpt-oss-20b", description="Secondary fallback model"
    )
    temperature: float = Field(default=0.2, ge=0.0, le=2.0, description="Sampling temperature")
    max_output_tokens: int = Field(
        default=4096, ge=128, le=16384, description="Maximum completion tokens"
    )
    rag_enabled: Optional[bool] = Field(
        default=None, description="Toggle RAG retrieval augmentation"
    )
    strict_transformer: Optional[bool] = Field(
        default=None,
        description="Enforce strict neural transformer execution without falling back to mock",
    )
    embedding_model: Optional[str] = Field(
        default=None, description="Embedding model identifier for RAG semantic search"
    )
    rag_top_k: Optional[int] = Field(
        default=None, ge=1, le=20, description="Number of top retrieved reference cases"
    )
    rag_similarity_threshold: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity threshold for RAG retrieval",
    )
    max_rag_tokens: Optional[int] = Field(
        default=None, ge=128, le=8192, description="Maximum token budget for assembled RAG context"
    )


class AiTestConnectionRequest(BaseModel):
    provider: str = "Groq"
    api_key: Optional[str] = None
    model_name: Optional[str] = None


class AiTestConnectionResponse(BaseModel):
    success: bool
    latency_ms: Optional[float] = None
    provider: str = "Groq"
    model_name: str = "openai/gpt-oss-120b"
    message: str
    error_detail: Optional[str] = None


class AiConfigHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    changed_by_id: Optional[int] = None
    changed_by_name: Optional[str] = None
    change_summary: str
    provider: str
    model_name: str
    temperature: Optional[float] = None
    created_at: datetime


class AvailableModelItem(BaseModel):
    id: str
    name: str
    provider: str = "Groq"
    context_window: int = 8192
    is_recommended: bool = False
    description: Optional[str] = None


class ProductionModelSummary(BaseModel):
    version_tag: str
    status: str
    base_model_name: str
    adapter_type: str
    dataset_version: Optional[str] = None
    trained_at: Optional[datetime] = None
    artifact_verified: bool = True
    manifest_hash: Optional[str] = None


class EvaluationMetricSummary(BaseModel):
    metric_name: str
    base_value: float
    fine_tuned_value: float
    improvement_pct: float
    unit: str = ""
    is_higher_better: bool = False


class EvaluationReportResponse(BaseModel):
    model_name: str
    version_tag: str
    base_model_name: str
    test_sample_count: int
    evaluated_at: datetime
    metrics: List[EvaluationMetricSummary]
    summary_verdict: str


class AiSystemOverviewResponse(BaseModel):
    production_model: Optional[ProductionModelSummary] = None
    rag_enabled: bool
    strict_transformer: bool
    database_status: str = "HEALTHY"
    database_stats: Dict[str, Any]
    ai_provider_status: Dict[str, Any]
    ai_safety_status: Dict[str, Any] = Field(default_factory=dict)
    counts: Dict[str, int]
    training_stats: Dict[str, int]
    latest_evaluation: Optional[Dict[str, Any]] = None
