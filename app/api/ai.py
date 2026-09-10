from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import require_academic_staff
from app.models.academic.grading_run import GradingRun
from app.models.security.enums import UserRole
from app.schemas.ai.training_governance import (
    BuildDatasetVersionRequest,
    DatasetVersionResponse,
    TrainingCandidateResponse,
)
from app.services.ai.governance.dataset_builder_service import DatasetBuilderService
from app.services.ai.governance.training_candidate_service import TrainingCandidateService
from app.services.ai.grading.batch_grading_schema import (
    BatchGradingQuestionRequest,
    BatchGradingQuestionResponse,
    PostExamGradingStartRequest,
    PostExamGradingStatusResponse,
)
from app.services.ai.grading.batch_grading_service import BatchGradingService
from app.services.ai.grading.grading_schema import (
    GradingEvaluateRequest,
    GradingEvaluateResponse,
)
from app.services.ai.grading.grading_service import GradingService
from app.services.ai.rubric.rubric_schema import (
    RubricGenerateRequest,
    RubricGenerateResponse,
)
from app.services.ai.rubric.rubric_service import RubricService
from app.services.ai.shared.llm_client import LlmClient
from app.services.ai.validation.validation_schema import (
    RubricValidateRequest,
    RubricValidateResponse,
)
from app.services.ai.validation.validation_service import ValidationService

router = APIRouter(prefix="/api/v1/ai", tags=["AI Engine"])


@router.get("/health", summary="AI Engine Health Check")
def get_ai_health() -> Dict[str, Any]:
    """Returns AI capability status and configured LLM models."""
    return LlmClient.check_health()


@router.post(
    "/rubric/generate",
    response_model=RubricGenerateResponse,
    summary="Generate Assessment Rubric",
)
def generate_rubric(
    payload: RubricGenerateRequest,
    current_user: dict = Depends(require_academic_staff()),
) -> RubricGenerateResponse:
    """
    Capability 1: Rubric Generation AI.
    Generates structured assessment rubrics from question text and answer key.
    Does NOT grade student answers and does NOT compute scores.
    """
    try:
        return RubricService.generate_rubric(payload)
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal generate rubrik AI: {e}")


@router.post(
    "/rubric/validate",
    response_model=RubricValidateResponse,
    summary="Validate Rubric and Answer Key Consistency",
)
def validate_rubric(
    payload: RubricValidateRequest,
    current_user: dict = Depends(require_academic_staff()),
) -> RubricValidateResponse:
    """
    Capability 2: Rubric & Answer Key Validation AI.
    Performs AI-assisted consistency checks between Question, Answer Key, and Rubric.
    Provides review signals (VALID, SUSPICIOUS, INVALID) without overriding teacher authority.
    """
    try:
        return ValidationService.validate_rubric_and_key(payload)
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal validasi rubrik AI: {e}")


@router.post(
    "/grading/evaluate",
    response_model=GradingEvaluateResponse,
    summary="Evaluate Single Student Answer",
)
def evaluate_grading(
    payload: GradingEvaluateRequest,
    current_user: dict = Depends(require_academic_staff()),
    db: Session = Depends(get_db),
) -> GradingEvaluateResponse:
    """
    Capability 3: Grading AI (with optional RAG).
    Evaluates student answers against official question and rubrics.
    Produces scaled scores, percentage scores, and pedagogical feedback.
    """
    try:
        return GradingService.evaluate(payload=payload, db=db)
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal evaluasi penilaian AI: {e}")


@router.post(
    "/grading/batch-question",
    response_model=BatchGradingQuestionResponse,
    summary="Batch Grade Student Submissions for a Single Question",
)
def batch_grade_question(
    payload: BatchGradingQuestionRequest,
    current_user: dict = Depends(require_academic_staff()),
    db: Session = Depends(get_db),
) -> BatchGradingQuestionResponse:
    """
    Production Batch Grading: Evaluates multiple student essay answers for a single question.
    Performs RAG retrieval once for the question and grades answers in parallel chunks.
    """
    user_role = current_user.get("role")
    user_school_id = current_user.get("school_id")

    if user_role not in ("SUPERADMIN", UserRole.SUPERADMIN):
        if user_school_id and payload.school_id and payload.school_id != user_school_id:
            raise HTTPException(
                status_code=403, detail="Akses ditolak: Soal bukan milik sekolah Anda."
            )

    if payload.question_id:
        from app.models.teacher.question import Question

        q = db.query(Question).filter(Question.id == payload.question_id).first()
        if q and user_role not in ("SUPERADMIN", UserRole.SUPERADMIN):
            if user_school_id and q.school_id and q.school_id != user_school_id:
                raise HTTPException(
                    status_code=403, detail="Akses ditolak: Soal bukan milik sekolah Anda."
                )

    try:
        return BatchGradingService.grade_question_batch(payload=payload, db=db)
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal batch grading soal AI: {e}")


@router.post(
    "/grading/post-exam/start",
    response_model=PostExamGradingStatusResponse,
    summary="Start Post-Exam Batch Grading Workflow",
)
def start_post_exam_grading(
    payload: PostExamGradingStartRequest,
    current_user: dict = Depends(require_academic_staff()),
    db: Session = Depends(get_db),
) -> PostExamGradingStatusResponse:
    """
    Initiates post-exam batch grading workflow for a locked exam schedule.
    Creates a new GradingRun with a unique tracking UUID and executes batch grading.
    """
    from app.models.academic.exam_schedule import ExamSchedule

    schedule = (
        db.query(ExamSchedule).filter(ExamSchedule.id == payload.exam_schedule_id).first()
    )
    if not schedule:
        raise HTTPException(status_code=404, detail="Jadwal ujian tidak ditemukan.")

    user_role = current_user.get("role")
    user_school_id = current_user.get("school_id")
    user_id = int(current_user["sub"])

    if user_role not in ("SUPERADMIN", UserRole.SUPERADMIN):
        if user_school_id and schedule.school_id != user_school_id:
            raise HTTPException(
                status_code=403, detail="Akses ditolak: Jadwal ujian bukan milik sekolah Anda."
            )
        if user_role not in ("SCHOOL_ADMIN", "ADMIN", UserRole.ADMIN):
            if schedule.teacher_id != user_id and schedule.proctor_id != user_id:
                raise HTTPException(
                    status_code=403,
                    detail="Akses ditolak: Anda bukan guru pengampu atau pengawas untuk jadwal ujian ini.",
                )

    try:
        run = BatchGradingService.start_post_exam_grading(
            db=db,
            schedule_id=payload.exam_schedule_id,
            rag_enabled=payload.rag_enabled,
            batch_size=payload.batch_size or 50,
        )
        return PostExamGradingStatusResponse(
            grading_run_id=str(run.id),
            exam_schedule_id=run.exam_schedule_id,
            status=run.status,
            total_questions=run.total_questions,
            total_submissions=run.total_submissions,
            processed_batches=run.processed_batches,
            total_batches=run.total_batches,
            model_used=run.model_used,
            error_message=run.error_message,
            started_at=run.started_at.isoformat() if run.started_at else None,
            completed_at=run.completed_at.isoformat() if run.completed_at else None,
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal memulai post-exam grading: {e}")


@router.get(
    "/grading/post-exam/{schedule_id}/status",
    response_model=PostExamGradingStatusResponse,
    summary="Get Post-Exam Grading Status",
)
def get_post_exam_grading_status(
    schedule_id: int,
    current_user: dict = Depends(require_academic_staff()),
    db: Session = Depends(get_db),
) -> PostExamGradingStatusResponse:
    """Returns the latest GradingRun status for the specified exam schedule."""
    from app.models.academic.exam_schedule import ExamSchedule

    schedule = db.query(ExamSchedule).filter(ExamSchedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Jadwal ujian tidak ditemukan.")

    user_role = current_user.get("role")
    user_school_id = current_user.get("school_id")
    user_id = int(current_user["sub"])

    if user_role not in ("SUPERADMIN", UserRole.SUPERADMIN):
        if user_school_id and schedule.school_id != user_school_id:
            raise HTTPException(
                status_code=403, detail="Akses ditolak: Jadwal ujian bukan milik sekolah Anda."
            )
        if user_role not in ("SCHOOL_ADMIN", "ADMIN", UserRole.ADMIN):
            if schedule.teacher_id != user_id and schedule.proctor_id != user_id:
                raise HTTPException(
                    status_code=403,
                    detail="Akses ditolak: Anda bukan guru pengampu atau pengawas untuk jadwal ujian ini.",
                )

    run = (
        db.query(GradingRun)
        .filter(GradingRun.exam_schedule_id == schedule_id)
        .order_by(GradingRun.created_at.desc())
        .first()
    )
    if not run:
        raise HTTPException(
            status_code=404,
            detail=f"Grading run tidak ditemukan untuk exam_schedule_id {schedule_id}",
        )

    return PostExamGradingStatusResponse(
        grading_run_id=str(run.id),
        exam_schedule_id=run.exam_schedule_id,
        status=run.status,
        total_questions=run.total_questions,
        total_submissions=run.total_submissions,
        processed_batches=run.processed_batches,
        total_batches=run.total_batches,
        model_used=run.model_used,
        error_message=run.error_message,
        started_at=run.started_at.isoformat() if run.started_at else None,
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
    )


# ==============================================================================
from app.core.rbac import require_any_role
from app.repositories.ai.assessment_history_repository import assessment_history_repository
from app.repositories.ai.dataset_version_repository import dataset_version_repository

# ==============================================================================
# MILESTONE A8: TRAINING DATA GOVERNANCE & DATASET MANAGEMENT
# ==============================================================================


@router.post(
    "/governance/candidates/ingest/{history_id}",
    response_model=TrainingCandidateResponse,
    summary="Ingest and Curate Assessment History into Training Candidate",
)
def ingest_training_candidate(
    history_id: int,
    current_user: dict = Depends(
        require_any_role("SUPERADMIN", "ADMIN", "SCHOOL_ADMIN", "TEACHER")
    ),
    db: Session = Depends(get_db),
) -> TrainingCandidateResponse:
    """
    Milestone A8: Processes an AssessmentHistory record through the Quality Gate
    and PII Sanitization Engine, formatting it as a standardized training candidate.
    Enforces strict multi-tenant authorization boundary.
    """
    history = assessment_history_repository.get_by_id(db, history_id)
    if not history:
        raise HTTPException(
            status_code=404,
            detail=f"AssessmentHistory record with ID {history_id} was not found.",
        )

    # Multi-tenant boundary check
    user_role = current_user.get("role")
    user_school_id = current_user.get("school_id")
    if user_role != "SUPERADMIN" and history.school_id != user_school_id:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Cannot curate assessment history belonging to another school tenant.",
        )

    user_id = int(current_user["sub"]) if "sub" in current_user else None
    candidate = TrainingCandidateService.evaluate_and_ingest_history(
        db, history_id, created_by_user_id=user_id
    )
    if not candidate:
        raise HTTPException(
            status_code=500,
            detail="Failed to ingest candidate from assessment history.",
        )

    return TrainingCandidateResponse(
        id=candidate.id,
        assessment_history_id=candidate.assessment_history_id,
        history_version=candidate.history_version,
        quality_status=candidate.quality_status,
        quality_score=candidate.quality_score,
        rejection_reasons=candidate.rejection_reasons or [],
        pii_status=candidate.pii_status,
        pii_entities_detected=candidate.pii_entities_detected or [],
        sanitized_student_answer=candidate.sanitized_student_answer,
        sanitized_teacher_feedback=candidate.sanitized_teacher_feedback,
        question_group_key=candidate.question_group_key,
        school_id=candidate.school_id,
        academic_year_id=candidate.academic_year_id,
        created_by_user_id=candidate.created_by_user_id,
        subject_name=candidate.subject_name,
        class_level=candidate.class_level,
    )


@router.post(
    "/governance/datasets/build",
    response_model=DatasetVersionResponse,
    summary="Build Versioned Training Dataset with Leakage-Free Group Split",
)
def build_dataset_version(
    payload: BuildDatasetVersionRequest,
    current_user: dict = Depends(require_any_role("SUPERADMIN", "ADMIN", "SCHOOL_ADMIN")),
    db: Session = Depends(get_db),
) -> DatasetVersionResponse:
    """
    Milestone A8: Builds an immutable training dataset release from eligible candidates.
    Guarantees strict question-group partitioning with zero data leakage and authenticated lineage actor.
    """
    try:
        user_role = current_user.get("role")
        user_school_id = current_user.get("school_id")
        user_id = int(current_user["sub"]) if "sub" in current_user else None

        # Resolve authoritative school_id boundary
        if user_role == "SUPERADMIN":
            target_school_id = payload.school_id
        else:
            if payload.school_id is not None and payload.school_id != user_school_id:
                raise HTTPException(
                    status_code=403,
                    detail="Forbidden: Cannot build dataset for a different school tenant.",
                )
            target_school_id = user_school_id

        dv = DatasetBuilderService.build_dataset_version(
            db=db,
            version_tag=payload.version_tag,
            min_quality_score=payload.min_quality_score,
            train_ratio=payload.train_ratio,
            val_ratio=payload.val_ratio,
            test_ratio=payload.test_ratio,
            split_strategy=payload.split_strategy,
            subject_id=payload.subject_id,
            school_id=target_school_id,
            academic_year_id=payload.academic_year_id,
            created_by_user_id=user_id,
            random_seed=payload.random_seed,
        )
        return DatasetVersionResponse(
            id=dv.id,
            version_tag=dv.version_tag,
            task_type=dv.task_type,
            split_strategy=dv.split_strategy,
            dataset_hash=dv.dataset_hash,
            manifest_hash=dv.manifest_hash,
            total_samples=dv.total_samples,
            train_count=dv.train_count,
            val_count=dv.val_count,
            test_count=dv.test_count,
            quality_threshold_applied=dv.quality_threshold_applied,
            split_manifest=dv.split_manifest,
            school_id=dv.school_id,
            academic_year_id=dv.academic_year_id,
            created_by_user_id=dv.created_by_user_id,
            metadata_json=dv.metadata_json,
        )
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal membangun dataset training: {e}")


@router.get(
    "/governance/datasets/{version_tag}/export",
    summary="Export SFT Training JSONL for Dataset Split",
)
def export_dataset_split(
    version_tag: str,
    split: str = "train",
    current_user: dict = Depends(
        require_any_role("SUPERADMIN", "ADMIN", "SCHOOL_ADMIN", "TEACHER")
    ),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Milestone A8: Exports formatted SFT payload objects for fine-tuning.
    Enforces tenant access boundary.
    """
    try:
        dv = dataset_version_repository.get_by_version_tag(db, version_tag)
        if not dv:
            raise HTTPException(
                status_code=404,
                detail=f"DatasetVersion '{version_tag}' was not found.",
            )

        # Multi-tenant boundary check
        user_role = current_user.get("role")
        user_school_id = current_user.get("school_id")
        if (
            user_role != "SUPERADMIN"
            and dv.school_id is not None
            and dv.school_id != user_school_id
        ):
            raise HTTPException(
                status_code=403,
                detail="Forbidden: Cannot export dataset belonging to another school tenant.",
            )

        items = DatasetBuilderService.export_dataset_split(
            db=db, version_tag=version_tag, split_name=split
        )
        return {
            "version_tag": version_tag,
            "split": split,
            "dataset_hash": dv.dataset_hash,
            "total_items": len(items),
            "data": items,
        }
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal export dataset split: {e}")
