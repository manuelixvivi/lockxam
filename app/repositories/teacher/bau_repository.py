from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.teacher.bau_document import BAUDocument
from app.repositories.base_repository import BaseRepository


class BAURepository(BaseRepository[BAUDocument]):

    def __init__(self):
        super().__init__(BAUDocument)

    def get_by_assignment(self, db: Session, assignment_id: int) -> BAUDocument | None:
        stmt = select(BAUDocument).where(BAUDocument.proctor_assignment_id == assignment_id)
        return db.scalar(stmt)


bau_repository = BAURepository()
