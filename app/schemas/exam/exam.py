from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class QuestionSnapshotPayload(BaseModel):
    id: int
    type: str  # PG, IS, ES
    content: str
    options: list[str] | None = None
    answer_key: str | list[str]
    rubrics: list[dict] | None = None
    max_score: float
    canonical_order: int


class ExamPackageSnapshotPayload(BaseModel):
    source_package_id: int
    school_id: int
    owner_teacher_account_id: int
    snapshot_version: int = Field(1, ge=1)
    questions: list[QuestionSnapshotPayload]


class ProctorCommandRequest(BaseModel):
    attempt_id: int
    student_id: int | None = None
    proctor_assignment_id: int
    actor_teacher_id: int | None = None
    exam_session_id: int
    reason: str | None = Field(None, max_length=500)


class AICallbackRequest(BaseModel):
    event_id: UUID
    attempt_id: int
    question_id: int
    score: float = Field(..., ge=0.0)
    feedback_text: str
    grading_version: int = Field(..., ge=1)


# ────────────────────────────────────────────────────
# Response Schemas
# ────────────────────────────────────────────────────


class ExamSessionResponse(BaseModel):
    id: int
    schedule_id: int
    package_id: int
    status: str

    model_config = {"from_attributes": True}


class StudentQuestionOptionResponse(BaseModel):
    key: str
    text: str


class StudentQuestionItemResponse(BaseModel):
    question_id: int
    question_type: str
    content: str
    options: list[StudentQuestionOptionResponse] | list[dict] | None = None
    score_weight: float = 5.0


class ExamAttemptResponse(BaseModel):
    id: int
    exam_session_id: int
    student_id: int
    status: str
    started_at: datetime | str | None = None
    deadline_at: datetime | str | None = None
    remaining_seconds: int | None = None
    final_score: float | None = None
    randomized_order: list[int] | None = None
    questions: list[StudentQuestionItemResponse] | None = None
    answers: dict[int, dict] | list[Any] | None = None
    device_session_token: str | None = None

    model_config = {"from_attributes": True}


class StudentAnswerResponse(BaseModel):
    id: int
    exam_attempt_id: int
    question_id: int
    selected_option: str | None = None
    text_answer: str | None = None

    model_config = {"from_attributes": True}


class ExamAnswerEvaluationResponse(BaseModel):
    id: int
    exam_attempt_id: int
    question_id: int
    score: float
    max_score: float
    grading_status: str
    grading_source: str
    feedback: str | None = None

    model_config = {"from_attributes": True}
