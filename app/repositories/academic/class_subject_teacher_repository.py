from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.academic.class_subject_teacher import ClassSubjectTeacher
from app.repositories.base_repository import BaseRepository


class ClassSubjectTeacherRepository(BaseRepository[ClassSubjectTeacher]):
    def __init__(self):
        super().__init__(ClassSubjectTeacher)

    def get_by_public_id(
        self, db: Session, public_id: UUID
    ) -> ClassSubjectTeacher | None:
        return db.scalar(
            select(ClassSubjectTeacher).where(
                ClassSubjectTeacher.public_id == public_id
            )
        )

    def get_by_class_and_subject(
        self, db: Session, class_id: int, subject_id: int
    ) -> ClassSubjectTeacher | None:
        return db.scalar(
            select(ClassSubjectTeacher).where(
                ClassSubjectTeacher.class_id == class_id,
                ClassSubjectTeacher.subject_id == subject_id,
            )
        )

    def list_by_class(
        self, db: Session, class_id: int
    ) -> list[ClassSubjectTeacher]:
        return list(
            db.scalars(
                select(ClassSubjectTeacher).where(
                    ClassSubjectTeacher.class_id == class_id
                )
            ).all()
        )

    def list_by_teacher(
        self, db: Session, teacher_id: int
    ) -> list[ClassSubjectTeacher]:
        return list(
            db.scalars(
                select(ClassSubjectTeacher).where(
                    ClassSubjectTeacher.teacher_id == teacher_id
                )
            ).all()
        )

    def assign_or_update(
        self, db: Session, school_id: int, class_id: int, subject_id: int, teacher_id: int
    ) -> ClassSubjectTeacher:
        existing = self.get_by_class_and_subject(db, class_id, subject_id)
        if existing:
            existing.teacher_id = teacher_id
            db.flush()
            return existing
        cst = ClassSubjectTeacher(
            school_id=school_id,
            class_id=class_id,
            subject_id=subject_id,
            teacher_id=teacher_id,
        )
        db.add(cst)
        db.flush()
        return cst

    def unassign(self, db: Session, class_id: int, subject_id: int) -> bool:
        existing = self.get_by_class_and_subject(db, class_id, subject_id)
        if existing:
            db.delete(existing)
            db.flush()
            return True
        return False


class_subject_teacher_repository = ClassSubjectTeacherRepository()
