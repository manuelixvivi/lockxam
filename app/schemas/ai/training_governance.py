from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class QualityEvaluationResponse(BaseModel):
    is_eligible: bool
    quality_score: float
    quality_status: str
    rejection_reasons: List[str]
    quality_breakdown: Dict[str, float]


class DetectedPiiMetadata(BaseModel):
    type: str
    field: str
    char_length: int
    detection_method: str


class TrainingCandidateResponse(BaseModel):
    id: int
    assessment_history_id: int
    history_version: int
    quality_status: str
    quality_score: float
    rejection_reasons: List[str]
    pii_status: str
    pii_entities_detected: List[Dict[str, Any]]
    sanitized_student_answer: str
    sanitized_teacher_feedback: Optional[str]
    question_group_key: str
    school_id: int
    academic_year_id: int
    created_by_user_id: Optional[int] = None
    subject_name: str
    class_level: str


class BuildDatasetVersionRequest(BaseModel):
    version_tag: str = Field(..., description="Unique dataset release tag, e.g. 'v1.0.0'")
    min_quality_score: float = Field(0.70, description="Minimum quality score threshold")
    train_ratio: float = Field(0.80, description="Train split ratio")
    val_ratio: float = Field(0.10, description="Validation split ratio")
    test_ratio: float = Field(0.10, description="Test split ratio")
    split_strategy: str = Field(
        "QUESTION_GROUP_SPLIT", description="Split strategy: QUESTION_GROUP_SPLIT or TEMPORAL_SPLIT"
    )
    subject_id: Optional[int] = Field(None, description="Optional subject ID filter")
    school_id: Optional[int] = Field(None, description="Optional school tenant filter")
    academic_year_id: Optional[int] = Field(None, description="Optional academic year scope filter")
    random_seed: int = Field(42, description="Random seed for group split determinism")

    @model_validator(mode="after")
    def validate_ratios_and_strategy(self) -> "BuildDatasetVersionRequest":
        if self.split_strategy not in {"QUESTION_GROUP_SPLIT", "TEMPORAL_SPLIT"}:
            raise ValueError(
                f"Invalid split_strategy '{self.split_strategy}'. Allowed: ['QUESTION_GROUP_SPLIT', 'TEMPORAL_SPLIT']."
            )

        if not (
            0.0 < self.train_ratio <= 1.0
            and 0.0 <= self.val_ratio < 1.0
            and 0.0 <= self.test_ratio < 1.0
        ):
            raise ValueError("All split ratios must be >= 0 and train_ratio must be > 0.")

        total = self.train_ratio + self.val_ratio + self.test_ratio
        if abs(total - 1.0) > 1e-4:
            raise ValueError(
                f"Sum of train_ratio, val_ratio, and test_ratio must equal 1.0 (received: {total:.4f})."
            )

        return self


class DatasetVersionResponse(BaseModel):
    id: int
    version_tag: str
    task_type: str
    split_strategy: str
    dataset_hash: str
    manifest_hash: str
    total_samples: int
    train_count: int
    val_count: int
    test_count: int
    quality_threshold_applied: float
    split_manifest: Dict[str, List[int]]
    school_id: Optional[int] = None
    academic_year_id: Optional[int] = None
    created_by_user_id: Optional[int] = None
    metadata_json: Optional[Dict[str, Any]] = None
