from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.academic.class_entity import ClassEntity
from app.repositories.base_repository import BaseRepository


class ClassRepository(BaseRepository[ClassEntity]):
    def __init__(self):
        super().__init__(ClassEntity)

    def get_by_public_id(self, db: Session, public_id: UUID) -> ClassEntity | None:
        return db.scalar(select(ClassEntity).where(ClassEntity.public_id == public_id))

    def get_by_name(
        self, db: Session, school_id: int, academic_year_id: int, name: str
    ) -> ClassEntity | None:
        return db.scalar(
            select(ClassEntity).where(
                ClassEntity.school_id == school_id,
                ClassEntity.academic_year_id == academic_year_id,
                ClassEntity.name == name.strip(),
            )
        )

    def list_by_academic_year(
        self,
        db: Session,
        school_id: int,
        academic_year_id: int,
        is_active: bool | None = None,
    ) -> list[ClassEntity]:
        query = select(ClassEntity).where(
            ClassEntity.school_id == school_id,
            ClassEntity.academic_year_id == academic_year_id,
        )
        if is_active is not None:
            query = query.where(ClassEntity.is_active == is_active)
        query = query.order_by(ClassEntity.name.asc())
        return list(db.scalars(query).all())

    def list_by_school(self, db: Session, school_id: int) -> list[ClassEntity]:
        return list(
            db.scalars(
                select(ClassEntity)
                .where(ClassEntity.school_id == school_id)
                .order_by(ClassEntity.name.asc())
            ).all()
        )


class_repository = ClassRepository()
