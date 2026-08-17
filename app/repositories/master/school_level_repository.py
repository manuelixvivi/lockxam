from app.models.master.school_level import SchoolLevel
from app.repositories.base_repository import BaseRepository


class SchoolLevelRepository(BaseRepository[SchoolLevel]):

    def __init__(self):
        super().__init__(SchoolLevel)


school_level_repository = SchoolLevelRepository()
