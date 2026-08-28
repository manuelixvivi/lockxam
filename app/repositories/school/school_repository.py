from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.school.school import School
from app.repositories.base_repository import BaseRepository


class SchoolRepository(BaseRepository[School]):

    def __init__(self):
        super().__init__(School)

    def get_by_npsn(self, db: Session, npsn: str) -> School | None:
        return db.scalar(select(School).where(School.npsn == npsn, School.deleted_at.is_(None)))

    def get_by_domain(self, db: Session, domain: str) -> School | None:
        return db.scalar(
            select(School).where(School.domain == domain.strip(), School.deleted_at.is_(None))
        )

    def get_by_public_id(self, db: Session, public_id: UUID) -> School | None:
        return db.scalar(
            select(School).where(School.public_id == public_id, School.deleted_at.is_(None))
        )

    def get_by_code(self, db: Session, code: str) -> School | None:
        return db.scalar(
            select(School).where(School.code == code.strip(), School.deleted_at.is_(None))
        )

    def get_all_active(self, db: Session) -> list[School]:
        return list(db.scalars(select(School).where(School.deleted_at.is_(None))).all())


school_repository = SchoolRepository()
