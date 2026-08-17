from sqlalchemy.orm import Session

from app.models.master.license_type import LicenseType
from app.models.master.school_level import SchoolLevel
from app.repositories.master.license_type_repository import (
    license_type_repository,
)
from app.repositories.master.school_level_repository import (
    school_level_repository,
)


class MasterDataService:

    @staticmethod
    def get_all_school_levels(db: Session) -> list[SchoolLevel]:
        return school_level_repository.get_all(db)

    @staticmethod
    def get_all_license_types(db: Session) -> list[LicenseType]:
        return license_type_repository.get_all(db)
