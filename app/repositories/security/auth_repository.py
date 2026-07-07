from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.security.auth_account import AuthAccount
from app.repositories.base_repository import BaseRepository


class AuthRepository(BaseRepository[AuthAccount]):

    def __init__(self):
        super().__init__(AuthAccount)

    def get_by_username(self, db: Session, username: str) -> AuthAccount | None:
        return db.scalar(select(AuthAccount).where(AuthAccount.username == username))

    def update_last_login(self, db: Session, account: AuthAccount) -> AuthAccount:
        return self.update(db, account)


auth_repository = AuthRepository()
