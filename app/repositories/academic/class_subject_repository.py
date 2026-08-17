from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.academic.class_subject import ClassSubject
from app.repositories.base_repository import BaseRepository


class ClassSubjectRepository(BaseRepository[ClassSubject]):
    def __init__(self):
        super().__init__(ClassSubject)

    def get_by_public_id(self, db: Session, public_id: UUID) -> ClassSubject | None:
        return db.scalar(
            select(ClassSubject).where(ClassSubject.public_id == public_id)
        )

    def get_by_class_and_subject(
        self, db: Session, class_id: int, subject_id: int
    ) -> ClassSubject | None:
        return db.scalar(
            select(ClassSubject).where(
                ClassSubject.class_id == class_id,
                ClassSubject.subject_id == subject_id,
            )
        )

    def list_by_class(self, db: Session, class_id: int) -> list[ClassSubject]:
        return list(
            db.scalars(
                select(ClassSubject).where(ClassSubject.class_id == class_id)
            ).all()
        )

    def assign(
        self, db: Session, school_id: int, class_id: int, subject_id: int
    ) -> ClassSubject:
        existing = self.get_by_class_and_subject(db, class_id, subject_id)
        if existing:
            return existing
        cs = ClassSubject(
            school_id=school_id,
            class_id=class_id,
            subject_id=subject_id,
        )
        db.add(cs)
        db.flush()
        return cs

    def unassign(self, db: Session, class_id: int, subject_id: int) -> bool:
        existing = self.get_by_class_and_subject(db, class_id, subject_id)
        if existing:
            db.delete(existing)
            db.flush()
            return True
        return False


class_subject_repository = ClassSubjectRepository()
