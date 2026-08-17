from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from fastapi import HTTPException
from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session

from app.core.database import Base

ModelType = TypeVar("ModelType", bound=Base)
T = TypeVar("T")


@dataclass
class PageResult(Generic[T]):
    items: list[T]
    total: int
    page: int
    per_page: int
    pages: int


class BaseRepository(Generic[ModelType]):

    def __init__(self, model: type[ModelType]):
        self.model = model

    def get_by_id(self, db: Session, obj_id: Any) -> ModelType | None:
        return db.scalar(select(self.model).where(self.model.id == obj_id))  # type: ignore[attr-defined]

    def get_by_public_id(self, db: Session, public_id: Any) -> ModelType | None:
        if hasattr(self.model, "public_id"):
            return db.scalar(select(self.model).where(self.model.public_id == public_id))  # type: ignore[attr-defined]
        return None

    def get_all(self, db: Session) -> list[ModelType]:
        return list(db.scalars(select(self.model)).all())

    def create(self, db: Session, obj: ModelType) -> ModelType:
        db.add(obj)
        db.flush()
        return obj

    def create_many(self, db: Session, objs: list[ModelType]) -> list[ModelType]:
        db.add_all(objs)
        db.flush()
        return objs

    def update(self, db: Session, obj: ModelType) -> ModelType:
        db.add(obj)
        db.flush()
        return obj

    def update_many(self, db: Session, objs: list[ModelType]) -> list[ModelType]:
        db.add_all(objs)
        db.flush()
        return objs

    def delete(self, db: Session, obj: ModelType) -> None:
        db.delete(obj)
        db.flush()

    def soft_delete(self, db: Session, obj: ModelType) -> ModelType:
        if hasattr(obj, "deleted_at"):
            obj.deleted_at = datetime.now(timezone.utc)
        elif hasattr(obj, "is_deleted"):
            obj.is_deleted = True
        elif hasattr(obj, "is_active"):
            obj.is_active = False
        else:
            raise AttributeError(
                f"Model '{self.model.__name__}' does not support soft delete "
                "(missing 'deleted_at', 'is_deleted', or 'is_active' attributes)."
            )
        db.add(obj)
        db.flush()
        return obj

    def exists(self, db: Session, obj_id: Any) -> bool:
        return (
            db.scalar(select(self.model.id).where(self.model.id == obj_id))  # type: ignore[attr-defined]
            is not None
        )

    def count(self, db: Session, *criterion: Any, **filters: Any) -> int:
        stmt = select(func.count()).select_from(self.model)
        if criterion:
            stmt = stmt.where(*criterion)
        for col_name, val in filters.items():
            if hasattr(self.model, col_name):
                stmt = stmt.where(getattr(self.model, col_name) == val)
        return db.scalar(stmt) or 0

    def paginate(
        self,
        db: Session,
        page: int = 1,
        per_page: int = 10,
        *criterion: Any,
        order_by: Any = None,
        **filters: Any,
    ) -> PageResult[ModelType]:
        stmt = select(self.model)
        if criterion:
            stmt = stmt.where(*criterion)
        for col_name, val in filters.items():
            if hasattr(self.model, col_name):
                stmt = stmt.where(getattr(self.model, col_name) == val)

        # Count total matching items using a subquery
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = db.scalar(count_stmt) or 0

        # Apply ordering
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        elif hasattr(self.model, "id"):
            stmt = stmt.order_by(self.model.id)  # type: ignore[attr-defined]

        # Apply limit and offset
        offset = (page - 1) * per_page
        stmt = stmt.offset(offset).limit(per_page)

        items = list(db.scalars(stmt).all())
        pages = (total + per_page - 1) // per_page if per_page > 0 else 0

        return PageResult(items=items, total=total, page=page, per_page=per_page, pages=pages)

    def find_one(self, db: Session, *criterion: Any, **filters: Any) -> ModelType | None:
        stmt = select(self.model)
        if criterion:
            stmt = stmt.where(*criterion)
        for col_name, val in filters.items():
            if hasattr(self.model, col_name):
                stmt = stmt.where(getattr(self.model, col_name) == val)
        return db.scalar(stmt.limit(1))

    def find_all(self, db: Session, *criterion: Any, **filters: Any) -> list[ModelType]:
        stmt = select(self.model)
        if criterion:
            stmt = stmt.where(*criterion)
        for col_name, val in filters.items():
            if hasattr(self.model, col_name):
                stmt = stmt.where(getattr(self.model, col_name) == val)
        return list(db.scalars(stmt).all())

    def get_or_404(self, db: Session, obj_id: int) -> ModelType:
        obj = self.get_by_id(db, obj_id)
        if not obj:
            raise HTTPException(
                status_code=404, detail=f"{self.model.__name__} with id {obj_id} not found"
            )
        return obj

    def bulk_insert(self, db: Session, mappings: list[dict]) -> None:
        if mappings:
            db.execute(insert(self.model), mappings)

    def bulk_update(self, db: Session, mappings: list[dict]) -> None:
        if mappings:
            db.execute(update(self.model), mappings)

    def flush(self, db: Session) -> None:
        db.flush()
