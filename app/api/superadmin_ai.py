from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import require_superadmin
from app.models.ai.registered_model import RegisteredModel
from app.models.ai.training_job import TrainingJob
from app.schemas.ai.ai_management import (
    AiConfigHistoryResponse,
    AiProviderConfigResponse,
    AiProviderConfigUpdateRequest,
    AiSystemOverviewResponse,
    AiTestConnectionRequest,
    AiTestConnectionResponse,
    AvailableModelItem,
    EvaluationReportResponse,
)
from app.services.ai.ai_management_service import AiManagementService
from app.services.security.activity_service import ActivityService

router = APIRouter(
    prefix="/api/v1/superadmin/ai-system",
    tags=["SuperAdmin — AI & System Management"],
    dependencies=[Depends(require_superadmin())],
)


@router.get(
    "/overview", response_model=AiSystemOverviewResponse, summary="Get AI & System Overview"
)
def get_overview(db: Session = Depends(get_db)) -> AiSystemOverviewResponse:
    """Returns top-level overview of AI models, providers, system health, and entity statistics."""
    return AiManagementService.get_overview(db)


@router.get(
    "/config",
    response_model=AiProviderConfigResponse,
    summary="Get Active AI Provider Configuration",
)
def get_ai_config(db: Session = Depends(get_db)) -> AiProviderConfigResponse:
    """Returns active AI provider parameters with masked credentials."""
    return AiManagementService.get_active_config(db)


@router.put(
    "/config", response_model=AiProviderConfigResponse, summary="Update AI Provider Configuration"
)
def update_ai_config(
    payload: AiProviderConfigUpdateRequest,
    request: Request,
    current_user: dict = Depends(require_superadmin()),
    db: Session = Depends(get_db),
) -> AiProviderConfigResponse:
    """
    Updates AI provider credentials, model selection, temperature, and RAG status.
    Synchronizes runtime AiConfig and appends an audit history entry.
    """
    user_id = int(current_user["sub"])
    updated = AiManagementService.update_config(db=db, user_id=user_id, payload=payload)

    # Activity Logging
    ActivityService.log_activity(
        db=db,
        auth_account_id=user_id,
        action_type="SYSTEM",
        action_name="UPDATE_AI_CONFIG",
        school_id=None,
        endpoint=str(request.url.path),
        method=request.method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"provider": payload.provider, "model_name": payload.model_name},
    )
    db.commit()

    return updated


@router.post(
    "/test-connection",
    response_model=AiTestConnectionResponse,
    summary="Test AI Provider Connection",
)
def test_ai_connection(
    payload: AiTestConnectionRequest,
    db: Session = Depends(get_db),
) -> AiTestConnectionResponse:
    """Performs live connectivity verification and measures round-trip latency to the target AI provider."""
    return AiManagementService.test_connection(db=db, payload=payload)


@router.get(
    "/available-models", response_model=List[AvailableModelItem], summary="List Available AI Models"
)
def get_available_models(db: Session = Depends(get_db)) -> List[AvailableModelItem]:
    """Returns curated list of available models for selection in the SuperAdmin UI."""
    return AiManagementService.list_available_models(db)


@router.get(
    "/config/history",
    response_model=List[AiConfigHistoryResponse],
    summary="Get AI Configuration History",
)
def get_config_history(
    limit: int = 50, db: Session = Depends(get_db)
) -> List[AiConfigHistoryResponse]:
    """Returns immutable chronological audit logs of AI configuration updates."""
    return AiManagementService.get_config_history(db, limit=limit)


@router.get("/model-registry", summary="List Registered Models & Versions (A9.4)")
def list_model_registry(
    limit: int = 50, skip: int = 0, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Returns model registry items from A9.4 with version status and Merkle artifact verifications."""
    effective_limit = min(max(1, limit), 100)
    registered_models = (
        db.query(RegisteredModel)
        .order_by(RegisteredModel.created_at.desc())
        .offset(skip)
        .limit(effective_limit)
        .all()
    )

    models_data = []
    for rm in registered_models:
        versions = [
            {
                "id": mv.id,
                "version_number": mv.version_number,
                "version_tag": f"v{mv.version_number}",
                "status": mv.status.value if hasattr(mv.status, "value") else str(mv.status),
                "base_model_name": mv.base_model_name,
                "adapter_type": mv.adapter_type or "LoRA",
                "dataset_version": getattr(mv, "dataset_version_tag", None),
                "manifest_hash": getattr(mv, "artifact_manifest_hash", None),
                "artifact_hash": getattr(mv, "artifact_manifest_hash", None),
                "created_at": mv.created_at.isoformat() if mv.created_at else None,
            }
            for mv in rm.versions
        ]
        models_data.append(
            {
                "id": rm.id,
                "name": rm.name,
                "display_name": rm.display_name,
                "task_type": rm.task_type,
                "description": rm.description,
                "current_production_version_id": rm.active_production_version_id,
                "current_staged_version_id": rm.active_staged_version_id,
                "versions": versions,
            }
        )

    return {"models": models_data, "total": len(models_data)}


@router.get("/training-jobs", summary="List Training Jobs (A9.3)")
def list_training_jobs(
    limit: int = 50, skip: int = 0, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Returns training jobs from A9.3 with live execution status and metrics."""
    effective_limit = min(max(1, limit), 100)
    jobs = (
        db.query(TrainingJob)
        .order_by(TrainingJob.created_at.desc())
        .offset(skip)
        .limit(effective_limit)
        .all()
    )

    jobs_data = []
    for j in jobs:
        jobs_data.append(
            {
                "id": j.id,
                "job_id": j.job_id,
                "task_type": getattr(j, "execution_mode", "SFT_LORA"),
                "status": j.status if isinstance(j.status, str) else str(j.status),
                "base_model_name": j.base_model_name,
                "dataset_version_id": j.dataset_version_id,
                "dataset_version_tag": j.dataset_version_tag,
                "training_config": getattr(j, "job_config_payload", {}),
                "training_metrics": getattr(j, "metrics_payload", {}),
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "started_at": (
                    st.isoformat()
                    if (st := getattr(j, "started_at", None)) is not None
                    and hasattr(st, "isoformat")
                    else None
                ),
                "completed_at": (
                    ct.isoformat()
                    if (ct := getattr(j, "completed_at", None)) is not None
                    and hasattr(ct, "isoformat")
                    else None
                ),
            }
        )

    return {"jobs": jobs_data, "total": len(jobs_data)}


@router.get(
    "/evaluation",
    response_model=EvaluationReportResponse,
    summary="Get Model Evaluation Benchmarks (A7/A9)",
)
def get_evaluation_report(db: Session = Depends(get_db)) -> EvaluationReportResponse:
    """Returns quantitative academic evaluation metrics comparing Base Model vs Fine-Tuned Model."""
    return AiManagementService.get_evaluation_report(db)
