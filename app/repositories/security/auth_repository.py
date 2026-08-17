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

    def list_teachers_by_school(self, db: Session, school_id: int) -> list[AuthAccount]:
        from app.models.security.enums import UserRole
        return list(
            db.scalars(
                select(AuthAccount).where(
                    AuthAccount.school_id == school_id,
                    AuthAccount.role.in_([UserRole.TEACHER, "TEACHER"]),
                )
            ).all()
        )


auth_repository = AuthRepository()
