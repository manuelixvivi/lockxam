from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.master.license_type import LicenseType
from app.repositories.base_repository import BaseRepository


class LicenseTypeRepository(BaseRepository[LicenseType]):

    def __init__(self):
        super().__init__(LicenseType)

    def get_by_code(self, db: Session, code: str) -> LicenseType | None:
        return db.scalar(select(LicenseType).where(LicenseType.code == code.strip()))


license_type_repository = LicenseTypeRepository()
