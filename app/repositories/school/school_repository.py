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

    def list_paginated(
        self,
        db: Session,
        limit: int = 20,
        skip: int = 0,
        search: str | None = None,
    ) -> tuple[list[School], int]:
        from sqlalchemy import func, or_

        query = select(School).where(School.deleted_at.is_(None))
        count_query = select(func.count(School.id)).where(School.deleted_at.is_(None))

        if search and search.strip():
            term = f"%{search.strip()}%"
            filter_condition = or_(
                School.name.ilike(term),
                School.code.ilike(term),
                School.npsn.ilike(term),
                School.domain.ilike(term),
            )
            query = query.where(filter_condition)
            count_query = count_query.where(filter_condition)

        total = db.scalar(count_query) or 0
        items = list(
            db.scalars(
                query.order_by(School.created_at.desc()).offset(skip).limit(limit)
            ).all()
        )
        return items, total


school_repository = SchoolRepository()

