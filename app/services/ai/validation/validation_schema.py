from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class ValidationStatus(str, Enum):
    VALID = "VALID"
    SUSPICIOUS = "SUSPICIOUS"
    INVALID = "INVALID"


class ValidationIssue(BaseModel):
    severity: str = Field("WARNING", description="Issue severity: 'INFO', 'WARNING', or 'ERROR'")
    category: str = Field(
        ...,
        description="Issue type: 'CONTRADICTION', 'MISSING_REQUIREMENT', 'IRRELEVANT_CRITERIA', 'AMBIGUITY', 'FACTUAL_INCONSISTENCY'",
    )
    description: str = Field(..., description="Detailed explanation of the detected discrepancy")
    suggestion: Optional[str] = Field(None, description="Actionable suggestion for teacher review")


class RubricValidateRequest(BaseModel):
    question: Optional[str] = Field(None, description="The exam question text")
    question_text: Optional[str] = Field(None, description="Alternative field for question text")
    answer_key: Optional[str] = Field("", description="Teacher-provided answer key")
    rubric: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = Field(
        None, description="Teacher-provided rubric criteria"
    )
    question_type: Optional[str] = Field(
        "essay", description="Question type: 'essay' or 'short_answer'"
    )
    subject: Optional[str] = Field("Umum", description="Subject name")
    grade_level: Optional[str] = Field("SMA", description="Target education level (SD, SMP, SMA)")
    education_level: Optional[str] = Field("SMA", description="Alternative field for grade level")
    education_class: Optional[str] = Field("Kelas 11", description="Class level, e.g. 'Kelas 11'")
    additional_context: Optional[str] = Field(None, description="Optional curriculum context")

    def get_effective_question(self) -> str:
        return (self.question or self.question_text or "").strip()

    def get_effective_grade_level(self) -> str:
        return self.grade_level or self.education_level or "SMA"


class RubricValidateResponse(BaseModel):
    status: ValidationStatus = Field(
        ..., description="Validation outcome: VALID, SUSPICIOUS, or INVALID"
    )
    confidence: float = Field(
        ..., description="Confidence score of the validation verdict (0.0 - 1.0)"
    )
    reason: str = Field(
        ..., description="Comprehensive reasoning explaining the consistency analysis"
    )
    issues: List[ValidationIssue] = Field(
        default_factory=list, description="List of detected issues or flagged items"
    )
    suggested_review: bool = Field(
        False, description="True if teacher manual review is recommended"
    )
    model: str = Field("openai/gpt-oss-120b", description="Model used for validation")
    prompt_version: str = Field("validation_v1.0", description="Validation prompt version")
    validated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    execution_time_seconds: float = Field(0.0, description="Latency in seconds")
