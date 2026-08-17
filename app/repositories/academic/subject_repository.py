from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.academic.subject import Subject
from app.repositories.base_repository import BaseRepository


class SubjectRepository(BaseRepository[Subject]):
    def __init__(self):
        super().__init__(Subject)

    def get_by_public_id(self, db: Session, public_id: UUID) -> Subject | None:
        return db.scalar(select(Subject).where(Subject.public_id == public_id))

    def get_by_code(self, db: Session, school_id: int, code: str) -> Subject | None:
        return db.scalar(
            select(Subject).where(
                Subject.school_id == school_id,
                Subject.code == code.strip(),
            )
        )

    def list_by_school(
        self, db: Session, school_id: int, is_active: bool | None = None
    ) -> list[Subject]:
        query = select(Subject).where(Subject.school_id == school_id)
        if is_active is not None:
            query = query.where(Subject.is_active == is_active)
        query = query.order_by(Subject.name.asc())
        return list(db.scalars(query).all())


subject_repository = SubjectRepository()
