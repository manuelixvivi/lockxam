from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.exam.enums import ExamAttemptStatus
from app.models.exam.exam_attempt import ExamAttempt
from app.repositories.base_repository import BaseRepository


class AttemptRepository(BaseRepository[ExamAttempt]):
    def __init__(self):
        super().__init__(ExamAttempt)

    def get_with_lock(self, db: Session, attempt_id: int) -> ExamAttempt | None:
        stmt = select(ExamAttempt).where(ExamAttempt.id == attempt_id).with_for_update()
        return db.scalar(stmt)

    def get_by_session_id(self, db: Session, session_id: int) -> list[ExamAttempt]:
        stmt = select(ExamAttempt).where(ExamAttempt.exam_session_id == session_id)
        return list(db.scalars(stmt).all())

    def get_by_session_and_student(
        self, db: Session, session_id: int, student_id: int
    ) -> ExamAttempt | None:
        stmt = (
            select(ExamAttempt)
            .where(ExamAttempt.exam_session_id == session_id)
            .where(ExamAttempt.student_id == student_id)
        )
        return db.scalar(stmt)

    def get_by_id_and_student(
        self, db: Session, attempt_id: int, student_id: int
    ) -> ExamAttempt | None:
        stmt = (
            select(ExamAttempt)
            .where(ExamAttempt.id == attempt_id)
            .where(ExamAttempt.student_id == student_id)
        )
        return db.scalar(stmt)

    def get_active_or_paused(self, db: Session, student_id: int | None = None) -> list[ExamAttempt]:
        stmt = select(ExamAttempt).where(
            ExamAttempt.status.in_(
                [ExamAttemptStatus.IN_PROGRESS, ExamAttemptStatus.PAUSED, "IN_PROGRESS", "PAUSED"]
            )
        )
        if student_id:
            stmt = stmt.where(ExamAttempt.student_id == student_id)
        return list(db.scalars(stmt).all())

    def has_active_or_paused(self, db: Session, student_id: int) -> bool:
        stmt = (
            select(1)
            .where(
                ExamAttempt.student_id == student_id,
                ExamAttempt.status.in_(
                    [ExamAttemptStatus.IN_PROGRESS, ExamAttemptStatus.PAUSED, "IN_PROGRESS", "PAUSED"]
                ),
            )
            .limit(1)
        )
        return db.scalar(stmt) is not None

    def get_by_student(self, db: Session, student_id: int) -> list[ExamAttempt]:
        stmt = select(ExamAttempt).where(ExamAttempt.student_id == student_id)
        return list(db.scalars(stmt).all())

    def get_class_leaderboard(self, db: Session, student_ids: list[int]):
        if not student_ids:
            return []
        stmt = (
            select(
                ExamAttempt.student_id,
                func.avg(ExamAttempt.final_score).label("avg_score"),
                func.count(ExamAttempt.id).label("total_exams"),
            )
            .where(
                ExamAttempt.student_id.in_(student_ids),
                ExamAttempt.status.in_(
                    [ExamAttemptStatus.GRADED, ExamAttemptStatus.SUBMITTED, "GRADED", "SUBMITTED"]
                ),
                ExamAttempt.final_score.isnot(None),
            )
            .group_by(ExamAttempt.student_id)
            .order_by(func.avg(ExamAttempt.final_score).desc())
        )
        return db.execute(stmt).all()


attempt_repository = AttemptRepository()
