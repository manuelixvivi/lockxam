from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class GradingRubricItem(BaseModel):
    ku_id: str = Field(..., description="Rubric criterion ID, e.g. 'C1', 'ku_1'")
    text: str = Field(..., description="Criterion description")
    weight: float = Field(100.0, description="Weight percentage (0-100)")
    achieved: float = Field(0.0, description="Percentage of this criterion achieved (0-100)")


class GradingEvaluateRequest(BaseModel):
    question: Optional[str] = Field(None, description="The exam question text")
    question_text: Optional[str] = Field(None, description="Alternative field for question text")
    student_answer: str = Field(..., description="The student's submitted response")
    answer_key: Optional[str] = Field("", description="Official teacher answer key")
    rubric: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = Field(
        None, description="Official assessment rubric criteria"
    )
    rubrics: Optional[List[Dict[str, Any]]] = Field(
        None, description="Alternative field for rubric criteria list"
    )
    concepts: Optional[List[str]] = Field(
        default_factory=list, description="Key concepts for verification"
    )
    question_type: Optional[str] = Field(
        "essay", description="Question type: 'essay' or 'short_answer'"
    )
    subject: Optional[str] = Field("Umum", description="Subject name")
    grade_level: Optional[str] = Field("SMA", description="Target grade level (SD, SMP, SMA)")
    education_level: Optional[str] = Field("SMA", description="Alternative field for grade level")
    education_class: Optional[str] = Field("Kelas 11", description="Class level")

    # Multi-tenant and RAG parameters
    school_id: Optional[int] = Field(None, description="Tenant school ID")
    subject_id: Optional[int] = Field(None, description="Subject ID")
    academic_year_id: Optional[int] = Field(None, description="Academic year ID")
    subject_name: Optional[str] = Field(None, description="Subject display name")
    class_level: Optional[str] = Field(None, description="Class level filter, e.g. 'XI'")
    rag_enabled: Optional[bool] = Field(None, description="Explicit override for RAG augmentation")
    rag_context: Optional[str] = Field(None, description="Pre-formatted RAG context block")
    max_score: float = Field(10.0, description="Maximum scale score for this question")
    top_k: Optional[int] = Field(None, description="Top-K exemplar count for RAG retrieval")
    similarity_threshold: Optional[float] = Field(
        None, description="Cosine similarity threshold for RAG"
    )

    def get_effective_question(self) -> str:
        return (self.question or self.question_text or "").strip()

    def get_effective_rubrics(self) -> List[Dict[str, Any]]:
        if self.rubric and isinstance(self.rubric, list):
            return self.rubric
        if self.rubrics and isinstance(self.rubrics, list):
            return self.rubrics
        return []

    def get_effective_grade_level(self) -> str:
        return self.grade_level or self.education_level or "SMA"


class GradingEvaluateResponse(BaseModel):
    status: str = Field("success", description="Grading outcome status")
    score: float = Field(..., description="Actual scaled score based on max_score")
    final_score: float = Field(..., description="Percentage score (0-100)")
    max_score: float = Field(10.0, description="Max possible score for question")
    feedback: str = Field(..., description="Constructive pedagogical feedback")
    decision: Dict[str, Any] = Field(
        default_factory=dict, description="Evaluation metadata decision"
    )
    metrics: Dict[str, Any] = Field(
        default_factory=dict, description="Concept and semantic metrics"
    )
    rubric_scores: List[Dict[str, Any]] = Field(
        default_factory=list, description="Scores per rubric criterion"
    )
    matched_items: Optional[List[str]] = Field(None, description="Matched items for short answer")
    model: str = Field("openai/gpt-oss-120b", description="LLM model used for grading")
    prompt_version: str = Field("grading_v2.0", description="Grading prompt version")
    rag_enabled: bool = Field(
        False, description="Whether RAG retrieval was enabled for this grading"
    )
    retrieved_cases: List[Dict[str, Any]] = Field(
        default_factory=list, description="Historical cases retrieved"
    )
    rag_context_tokens: int = Field(0, description="Token consumption of RAG context")
    rag_metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Detailed RAG provenance metadata"
    )
    latency_ms: float = Field(0.0, description="Total execution latency in milliseconds")
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
