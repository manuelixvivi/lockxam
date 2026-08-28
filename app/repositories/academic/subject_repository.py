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

    def is_subject_in_use(self, db: Session, subject_id: int) -> bool:
        from app.models.academic.class_subject import ClassSubject
        from app.models.academic.exam_schedule import ExamSchedule
        from app.models.academic.teacher_subject import TeacherSubject

        has_teacher = db.scalar(
            select(TeacherSubject).where(TeacherSubject.subject_id == subject_id)
        )
        has_class = db.scalar(select(ClassSubject).where(ClassSubject.subject_id == subject_id))
        has_schedule = db.scalar(select(ExamSchedule).where(ExamSchedule.subject_id == subject_id))
        return bool(has_teacher or has_class or has_schedule)

    def get_by_code_or_name(self, db: Session, school_id: int, raw_str: str) -> Subject | None:
        from sqlalchemy import func, or_

        s = raw_str.strip()
        stmt = select(Subject).where(
            Subject.school_id == school_id,
            or_(func.lower(Subject.code) == s.lower(), func.lower(Subject.name) == s.lower()),
        )
        return db.scalar(stmt)


subject_repository = SubjectRepository()
