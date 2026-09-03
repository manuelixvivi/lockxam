import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.ai.model_version import ModelVersion, ModelVersionStatus

logger = logging.getLogger(__name__)


class ModelVersionRepository:
    """
    Milestone A9.4.1: Model Version Repository.
    Manages immutable ModelVersion records, sequential version counter generation,
    lifecycle state transitions, and promotion audit logging.
    """

    def get_next_version_number(self, db: Session, model_id: int) -> int:
        """
        Computes next sequential integer version number for the given model_id.
        """
        max_num = (
            db.query(func.max(ModelVersion.version_number))
            .filter(ModelVersion.model_id == model_id)
            .scalar()
        )
        return (max_num or 0) + 1

    def create(self, db: Session, model_version: ModelVersion) -> ModelVersion:
        """
        Persists a new immutable ModelVersion with strict tenant boundary verification.
        """
        from app.models.ai.registered_model import RegisteredModel

        parent_model = (
            db.query(RegisteredModel).filter(RegisteredModel.id == model_version.model_id).first()
        )
        if parent_model and parent_model.school_id != model_version.school_id:
            raise PermissionError(
                f"Tenant isolation violation: ModelVersion school_id ({model_version.school_id}) does not match RegisteredModel school_id ({parent_model.school_id})."
            )

        if not model_version.promotion_history:
            model_version.promotion_history = [
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "from_status": None,
                    "to_status": model_version.status,
                    "user_id": model_version.created_by_user_id,
                    "reason": "Initial version registration",
                }
            ]
        db.add(model_version)
        db.flush()
        db.refresh(model_version)
        return model_version

    def get_by_id(
        self, db: Session, version_id: int, school_id: Optional[int] = None
    ) -> Optional[ModelVersion]:
        query = db.query(ModelVersion).filter(ModelVersion.id == version_id)
        if school_id is not None:
            query = query.filter(
                (ModelVersion.school_id == school_id) | (ModelVersion.school_id.is_(None))
            )
        return query.first()

    def get_by_model_and_version(
        self, db: Session, model_id: int, version: str, school_id: Optional[int] = None
    ) -> Optional[ModelVersion]:
        query = db.query(ModelVersion).filter(
            ModelVersion.model_id == model_id,
            ModelVersion.version == version,
        )
        if school_id is not None:
            query = query.filter(
                (ModelVersion.school_id == school_id) | (ModelVersion.school_id.is_(None))
            )
        return query.first()

    def list_by_model(
        self,
        db: Session,
        model_id: int,
        school_id: Optional[int] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ModelVersion]:
        query = db.query(ModelVersion).filter(ModelVersion.model_id == model_id)
        if school_id is not None:
            query = query.filter(
                (ModelVersion.school_id == school_id) | (ModelVersion.school_id.is_(None))
            )
        if status is not None:
            query = query.filter(ModelVersion.status == status)
        return query.order_by(ModelVersion.version_number.desc()).offset(skip).limit(limit).all()

    def update_status(
        self,
        db: Session,
        version_id: int,
        new_status: ModelVersionStatus,
        reason: str = "Status transition",
        user_id: Optional[int] = None,
        validation_report: Optional[Dict[str, Any]] = None,
        school_id: Optional[int] = None,
    ) -> Optional[ModelVersion]:
        version = self.get_by_id(db, version_id, school_id=school_id)
        if not version:
            return None

        prev_status = version.status
        version.status = (
            new_status.value if isinstance(new_status, ModelVersionStatus) else new_status
        )

        now = datetime.now(timezone.utc)
        if new_status in (ModelVersionStatus.PRODUCTION, ModelVersionStatus.PRODUCTION.value):
            version.promoted_at = now
        elif new_status in (ModelVersionStatus.ARCHIVED, ModelVersionStatus.ARCHIVED.value):
            version.archived_at = now

        if validation_report is not None:
            version.validation_report_payload = validation_report

        # Append promotion event to history
        history = list(version.promotion_history or [])
        history.append(
            {
                "timestamp": now.isoformat(),
                "from_status": prev_status,
                "to_status": version.status,
                "user_id": user_id,
                "reason": reason,
            }
        )
        version.promotion_history = history

        db.flush()
        db.refresh(version)
        return version


model_version_repository = ModelVersionRepository()
