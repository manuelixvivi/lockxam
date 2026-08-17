from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.school.school_setting import SchoolSetting
from app.repositories.base_repository import BaseRepository


class SchoolSettingRepository(BaseRepository[SchoolSetting]):

    def __init__(self):
        super().__init__(SchoolSetting)

    def get_by_school_id(self, db: Session, school_id: int) -> SchoolSetting | None:
        return db.scalar(select(SchoolSetting).where(SchoolSetting.school_id == school_id))


school_setting_repository = SchoolSettingRepository()
