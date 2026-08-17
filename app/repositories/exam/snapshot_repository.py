from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.exam.package_snapshot import ExamPackageSnapshot
from app.repositories.base_repository import BaseRepository


class SnapshotRepository(BaseRepository[ExamPackageSnapshot]):
    def __init__(self):
        super().__init__(ExamPackageSnapshot)

    def get_by_session(self, db: Session, session_id: int) -> ExamPackageSnapshot | None:
        stmt = select(ExamPackageSnapshot).where(
            ExamPackageSnapshot.exam_session_id == session_id
        )
        return db.scalar(stmt)


snapshot_repository = SnapshotRepository()
