from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.academic.exam_snapshot import ExamSnapshot
from app.repositories.base_repository import BaseRepository


class ExamSnapshotRepository(BaseRepository[ExamSnapshot]):
    def __init__(self):
        super().__init__(ExamSnapshot)

    def get_by_public_id(self, db: Session, public_id: UUID) -> ExamSnapshot | None:
        return db.scalar(
            select(ExamSnapshot).where(ExamSnapshot.public_id == public_id)
        )

    def get_by_schedule_id(
        self, db: Session, exam_schedule_id: int
    ) -> ExamSnapshot | None:
        return db.scalar(
            select(ExamSnapshot).where(
                ExamSnapshot.exam_schedule_id == exam_schedule_id
            )
        )


exam_snapshot_repository = ExamSnapshotRepository()
