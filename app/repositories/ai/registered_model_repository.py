import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.ai.registered_model import RegisteredModel

logger = logging.getLogger(__name__)


class RegisteredModelRepository:
    """
    Milestone A9.4.1: Registered Model Repository.
    Manages top-level canonical model entities and multi-tenant isolation.
    """

    def create(
        self,
        db: Session,
        name: str,
        display_name: str,
        description: Optional[str] = None,
        task_type: str = "essay_grading",
        school_id: Optional[int] = None,
        created_by_user_id: Optional[int] = None,
    ) -> RegisteredModel:
        model = RegisteredModel(
            name=name,
            display_name=display_name,
            description=description,
            task_type=task_type,
            school_id=school_id,
            created_by_user_id=created_by_user_id,
        )
        db.add(model)
        db.flush()
        db.refresh(model)
        return model

    def get_by_id(
        self, db: Session, model_id: int, school_id: Optional[int] = None
    ) -> Optional[RegisteredModel]:
        query = db.query(RegisteredModel).filter(RegisteredModel.id == model_id)
        if school_id is not None:
            query = query.filter(
                (RegisteredModel.school_id == school_id) | (RegisteredModel.school_id.is_(None))
            )
        return query.first()

    def get_by_name(
        self, db: Session, name: str, school_id: Optional[int] = None
    ) -> Optional[RegisteredModel]:
        query = db.query(RegisteredModel).filter(RegisteredModel.name == name)
        if school_id is not None:
            query = query.filter(
                (RegisteredModel.school_id == school_id) | (RegisteredModel.school_id.is_(None))
            )
        else:
            query = query.filter(RegisteredModel.school_id.is_(None))
        return query.first()

    def list_models(
        self,
        db: Session,
        school_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[RegisteredModel]:
        query = db.query(RegisteredModel)
        if school_id is not None:
            query = query.filter(
                (RegisteredModel.school_id == school_id) | (RegisteredModel.school_id.is_(None))
            )
        return query.order_by(RegisteredModel.created_at.desc()).offset(skip).limit(limit).all()

    def update_pointers(
        self,
        db: Session,
        model_id: int,
        active_production_version_id: Optional[int] = None,
        active_staged_version_id: Optional[int] = None,
        update_production: bool = False,
        update_staged: bool = False,
        school_id: Optional[int] = None,
    ) -> Optional[RegisteredModel]:
        model = self.get_by_id(db, model_id, school_id=school_id)
        if not model:
            return None

        if update_production:
            model.active_production_version_id = active_production_version_id
        if update_staged:
            model.active_staged_version_id = active_staged_version_id

        model.updated_at = datetime.now(timezone.utc)
        db.flush()
        db.refresh(model)
        return model


registered_model_repository = RegisteredModelRepository()
