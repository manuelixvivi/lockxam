from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PartialCreditRule(BaseModel):
    condition: str = Field(..., description="Condition describing partial fulfillment")
    score: float = Field(..., description="Maximum score for this condition (0-100)")


class RubricCriterionItem(BaseModel):
    ku_id: str = Field(..., description="Unique criterion identifier, e.g. 'C1', 'ku_1'")
    text: str = Field(..., description="Learning outcome criterion statement")
    weight: float = Field(..., description="Criterion weight percentage (0-100)")
    bloom_level: Optional[str] = Field("C2", description="Bloom taxonomy level (C1-C6)")
    required_concepts: Optional[List[str]] = Field(default_factory=list)
    acceptable_variations: Optional[List[str]] = Field(default_factory=list)
    partial_credit_rules: Optional[List[PartialCreditRule]] = Field(default_factory=list)


class RubricGenerateRequest(BaseModel):
    question: Optional[str] = Field(None, description="The exam question text")
    question_text: Optional[str] = Field(None, description="Alternative field for question text")
    answer_key: Optional[str] = Field("", description="Teacher's official answer key")
    question_type: Optional[str] = Field(
        "essay", description="Question type: 'essay' or 'short_answer'"
    )
    subject: Optional[str] = Field("Umum", description="Subject name")
    grade_level: Optional[str] = Field("SMA", description="Target education level (SD, SMP, SMA)")
    education_level: Optional[str] = Field("SMA", description="Alternative field for grade level")
    education_class: Optional[str] = Field("Kelas 11", description="Class level, e.g. 'Kelas 11'")
    additional_context: Optional[str] = Field(
        None, description="Optional curriculum or reference context"
    )

    def get_effective_question(self) -> str:
        return (self.question or self.question_text or "").strip()

    def get_effective_grade_level(self) -> str:
        return self.grade_level or self.education_level or "SMA"


class RubricGenerateResponse(BaseModel):
    status: str = Field("success", description="Generation status")
    question_type: str = Field("PROSEDURAL", description="Detected question classification")
    bloom_level: str = Field("C2", description="Assessed cognitive Bloom level")
    complexity_score: int = Field(50, description="Complexity index (0-100)")
    concepts: List[str] = Field(default_factory=list, description="Key concepts extracted")
    rubric: List[Dict[str, Any]] = Field(
        default_factory=list, description="Generated structured criteria"
    )
    learning_outcomes: List[str] = Field(default_factory=list, description="Summary descriptions")
    model: str = Field("openai/gpt-oss-120b", description="Model used for generation")
    prompt_version: str = Field("rubric_v2.0", description="Rubric prompt version")
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    execution_time_seconds: float = Field(0.0, description="Generation latency in seconds")
