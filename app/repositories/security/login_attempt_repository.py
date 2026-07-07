from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.security.login_attempt import LoginAttempt
from app.repositories.base_repository import BaseRepository


class LoginAttemptRepository(BaseRepository[LoginAttempt]):

    def __init__(self):
        super().__init__(LoginAttempt)

    def get_attempt(self, db: Session, ip_address: str, username: str) -> LoginAttempt | None:
        return db.scalar(
            select(LoginAttempt).where(
                LoginAttempt.ip_address == ip_address, LoginAttempt.username == username
            )
        )


login_attempt_repository = LoginAttemptRepository()
