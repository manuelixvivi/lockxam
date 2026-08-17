from app.models.master.license_type import LicenseType
from app.repositories.base_repository import BaseRepository


class LicenseTypeRepository(BaseRepository[LicenseType]):

    def __init__(self):
        super().__init__(LicenseType)


license_type_repository = LicenseTypeRepository()
