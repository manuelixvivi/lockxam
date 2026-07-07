from app.models.activity_log import ActivityLog
from app.repositories.base_repository import BaseRepository


class ActivityRepository(BaseRepository[ActivityLog]):

    def __init__(self):
        super().__init__(ActivityLog)


activity_repository = ActivityRepository()
