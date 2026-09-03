from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.academic.teacher_subject import TeacherSubject
from app.repositories.base_repository import BaseRepository


class TeacherSubjectRepository(BaseRepository[TeacherSubject]):
    def __init__(self):
        super().__init__(TeacherSubject)

    def get_by_teacher_and_subject(
        self, db: Session, teacher_id: int, subject_id: int
    ) -> TeacherSubject | None:
        return db.scalar(
            select(TeacherSubject).where(
                TeacherSubject.teacher_id == teacher_id,
                TeacherSubject.subject_id == subject_id,
            )
        )

    def list_by_teacher(self, db: Session, teacher_id: int) -> list[TeacherSubject]:
        return list(
            db.scalars(
                select(TeacherSubject).where(TeacherSubject.teacher_id == teacher_id)
            ).all()
        )

    def list_by_teachers(
        self, db: Session, teacher_ids: list[int]
    ) -> list[TeacherSubject]:
        if not teacher_ids:
            return []
        return list(
            db.scalars(
                select(TeacherSubject).where(TeacherSubject.teacher_id.in_(teacher_ids))
            ).all()
        )

    def list_by_subject(
        self, db: Session, school_id: int, subject_id: int
    ) -> list[TeacherSubject]:
        return list(
            db.scalars(
                select(TeacherSubject).where(
                    TeacherSubject.school_id == school_id,
                    TeacherSubject.subject_id == subject_id,
                )
            ).all()
        )

    def list_teacher_ids_by_subject(
        self, db: Session, school_id: int, subject_id: int
    ) -> list[int]:
        stmt = select(TeacherSubject.teacher_id).where(
            TeacherSubject.school_id == school_id,
            TeacherSubject.subject_id == subject_id,
        )
        return list(db.scalars(stmt).all())

    def assign(
        self, db: Session, school_id: int, teacher_id: int, subject_id: int
    ) -> TeacherSubject:
        existing = self.get_by_teacher_and_subject(db, teacher_id, subject_id)
        if existing:
            return existing
        ts = TeacherSubject(
            school_id=school_id,
            teacher_id=teacher_id,
            subject_id=subject_id,
        )
        db.add(ts)
        db.flush()
        return ts

    def unassign(self, db: Session, teacher_id: int, subject_id: int) -> bool:
        existing = self.get_by_teacher_and_subject(db, teacher_id, subject_id)
        if existing:
            db.delete(existing)
            db.flush()
            return True
        return False

    def unassign_all_for_teacher(self, db: Session, teacher_id: int) -> int:
        stmt = delete(TeacherSubject).where(TeacherSubject.teacher_id == teacher_id)
        res = db.execute(stmt)
        db.flush()
        return res.rowcount or 0


teacher_subject_repository = TeacherSubjectRepository()
