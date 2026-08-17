from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.security.auth_account import AuthAccount
from app.models.teacher.question import Question
from app.repositories.base_repository import BaseRepository


class QuestionRepository(BaseRepository[Question]):

    def __init__(self):
        super().__init__(Question)

    def get_owned_question_in_school(
        self, db: Session, question_id: int, teacher_account_id: int, school_id: int
    ) -> Question | None:
        """Kunci Invarian Tenant: Mengambil soal dan memvalidasi kepemilikan sekolah (school_id) secara langsung di DB."""
        stmt = (
            select(Question)
            .join(AuthAccount, AuthAccount.id == Question.owner_teacher_account_id)
            .where(Question.id == question_id)
            .where(Question.owner_teacher_account_id == teacher_account_id)
            .where(AuthAccount.school_id == school_id)
        )
        return db.scalars(stmt).first()


question_repository = QuestionRepository()
