from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, model_validator


class BatchSubmissionItem(BaseModel):
    student_id: Union[int, str] = Field(..., description="Unique student ID or identifier")
    student_name: Optional[str] = Field(None, description="Optional student name for display")
    student_answer: str = Field(..., description="Student essay response text")
    attempt_id: Optional[int] = Field(None, description="Linked exam attempt ID")


class BatchGradingQuestionRequest(BaseModel):
    question_id: int = Field(..., description="The unique ID of the essay question")
    question_text: str = Field(..., description="Official question prompt text")
    answer_key: str = Field(..., description="Authoritative teacher answer key")
    rubric: List[Dict[str, Any]] = Field(
        ..., description="Authoritative rubric criteria with weights"
    )
    concepts: Optional[List[str]] = Field(
        default_factory=list, description="Core expected concepts"
    )
    max_score: float = Field(10.0, description="Max question score")
    subject: Optional[str] = Field("Umum", description="Subject name")
    grade_level: Optional[str] = Field("SMA", description="Target grade level")
    education_class: Optional[str] = Field("Kelas 11", description="Class name")

    # Multi-tenant RAG parameters (retrieval is performed ONCE per question batch)
    school_id: Optional[int] = Field(None, description="Tenant school ID")
    subject_id: Optional[int] = Field(None, description="Subject ID")
    academic_year_id: Optional[int] = Field(None, description="Academic year ID")
    class_level: Optional[str] = Field(None, description="Class level filter")
    rag_enabled: Optional[bool] = Field(None, description="Explicit RAG override")
    batch_size: int = Field(50, description="Submissions chunk size per LLM inference call")

    submissions: List[BatchSubmissionItem] = Field(
        ..., description="List of student submissions for this specific question"
    )


class BatchStudentGradingResult(BaseModel):
    student_id: Union[int, str] = Field(..., description="Target student ID")
    attempt_id: Optional[int] = Field(None, description="Exam attempt ID")
    score: float = Field(..., description="Scaled score based on max_score")
    final_score: float = Field(..., description="Score on 0-100 percentage scale")
    feedback: str = Field(..., description="Pedagogical feedback specific to this student")
    rubric_scores: List[Dict[str, Any]] = Field(
        default_factory=list, description="Scores achieved per rubric criterion"
    )
    status: str = Field("success", description="Grading outcome status ('success' or 'error')")
    quality_indicator: float = Field(
        1.0, description="Evaluation quality and completeness metric (0.0 - 1.0)"
    )
    confidence: float = Field(
        0.85,
        ge=0.0,
        le=1.0,
        description="Root-level grading confidence score (0.0 to 1.0)",
    )
    confidence_level: str = Field(
        ...,
        description="Categorical confidence: HIGH, MEDIUM, or LOW",
    )
    review_required: bool = Field(
        ...,
        description="Whether teacher review is required",
    )
    academic_rationale: Optional[str] = Field(
        None,
        description="Pedagogical academic rationale explaining the awarded points",
    )

    @model_validator(mode="before")
    @classmethod
    def populate_root_confidence(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "confidence" not in data or data["confidence"] is None:
                conf = data.get("quality_indicator", 1.0)
                data["confidence"] = round(max(0.0, min(1.0, float(conf))), 2)

            conf_val = float(data["confidence"])
            if "confidence_level" not in data or not data["confidence_level"]:
                if conf_val >= 0.90:
                    data["confidence_level"] = "HIGH"
                elif conf_val >= 0.75:
                    data["confidence_level"] = "MEDIUM"
                else:
                    data["confidence_level"] = "LOW"

            if "review_required" not in data or data["review_required"] is None:
                data["review_required"] = conf_val < 0.90

            if "academic_rationale" not in data or not data["academic_rationale"]:
                data["academic_rationale"] = data.get("feedback")
        return data


class BatchGradingQuestionResponse(BaseModel):
    question_id: int = Field(..., description="Question ID evaluated")
    status: str = Field("success", description="Batch evaluation status")
    total_submissions: int = Field(..., description="Total student submissions received")
    total_evaluated: int = Field(
        ..., description="Total student submissions successfully evaluated"
    )
    missing_students: List[Union[int, str]] = Field(
        default_factory=list, description="Students omitted by LLM output (requiring retry)"
    )
    results: List[BatchStudentGradingResult] = Field(
        default_factory=list, description="Grading results for every student in the batch"
    )
    model: str = Field("openai/gpt-oss-120b", description="LLM model used")
    prompt_version: str = Field("batch_grading_v2.0", description="Batch prompt version")
    rag_enabled: bool = Field(False, description="Whether RAG was used for this batch")
    retrieved_cases: List[Dict[str, Any]] = Field(
        default_factory=list, description="Reference cases retrieved once for this question"
    )
    latency_ms: float = Field(0.0, description="Execution time in milliseconds")
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class PostExamGradingStartRequest(BaseModel):
    exam_schedule_id: int = Field(..., description="The locked exam schedule ID")
    batch_size: Optional[int] = Field(50, description="Answers chunk size per LLM call")
    rag_enabled: Optional[bool] = Field(None, description="Override RAG usage")


class PostExamGradingStatusResponse(BaseModel):
    grading_run_id: str = Field(..., description="UUID of the grading run")
    exam_schedule_id: int = Field(..., description="Exam schedule ID")
    status: str = Field(
        ..., description="Grading run status (QUEUED, PROCESSING, COMPLETED, CANCELLED, FAILED)"
    )
    total_questions: int = Field(0, description="Total essay questions in exam")
    total_submissions: int = Field(0, description="Total essay answers to grade")
    processed_batches: int = Field(0, description="Number of batches completed")
    total_batches: int = Field(0, description="Total batches calculated")
    model_used: str = Field("openai/gpt-oss-120b", description="Configured LLM model")
    error_message: Optional[str] = Field(None, description="Error message if run failed")
    started_at: Optional[str] = Field(None, description="Run start timestamp")
    completed_at: Optional[str] = Field(None, description="Run completion timestamp")
