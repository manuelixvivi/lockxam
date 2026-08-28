from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.license.school_license import SchoolLicense
from app.repositories.base_repository import BaseRepository


class SchoolLicenseRepository(BaseRepository[SchoolLicense]):
    def __init__(self):
        super().__init__(SchoolLicense)

    def get_active_license(self, db: Session, school_id: int) -> SchoolLicense | None:
        return db.scalar(
            select(SchoolLicense)
            .where(SchoolLicense.school_id == school_id, SchoolLicense.status == "ACTIVE")
            .order_by(SchoolLicense.end_date.desc())
        )

    def get_latest_license(self, db: Session, school_id: int) -> SchoolLicense | None:
        return db.scalar(
            select(SchoolLicense)
            .where(SchoolLicense.school_id == school_id)
            .order_by(SchoolLicense.created_at.desc())
        )

    def get_by_public_id(self, db: Session, public_id: UUID) -> SchoolLicense | None:
        return db.scalar(select(SchoolLicense).where(SchoolLicense.public_id == public_id))

    def get_licenses_by_school(self, db: Session, school_id: int) -> list[SchoolLicense]:
        return list(
            db.scalars(
                select(SchoolLicense)
                .where(SchoolLicense.school_id == school_id)
                .order_by(SchoolLicense.created_at.desc())
            ).all()
        )


school_license_repository = SchoolLicenseRepository()
