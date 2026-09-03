from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.ai.dataset_version import DatasetVersion


class DatasetVersionRepository:
    """
    Repository for DatasetVersion persistence and queries.
    Provides data lineage tracking for fine-tuning releases.
    """

    def create(self, db: Session, dataset_version: DatasetVersion) -> DatasetVersion:
        db.add(dataset_version)
        db.flush()
        return dataset_version

    def get_by_id(self, db: Session, version_id: int) -> Optional[DatasetVersion]:
        return db.query(DatasetVersion).filter(DatasetVersion.id == version_id).first()

    def get_by_version_tag(self, db: Session, version_tag: str) -> Optional[DatasetVersion]:
        return db.query(DatasetVersion).filter(DatasetVersion.version_tag == version_tag).first()

    def list_all(self, db: Session) -> List[DatasetVersion]:
        return db.query(DatasetVersion).order_by(DatasetVersion.created_at.desc()).all()


dataset_version_repository = DatasetVersionRepository()
