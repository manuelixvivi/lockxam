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

    def find_by_owner_content_type(
        self,
        db: Session,
        teacher_account_id: int,
        content_normalized: str,
        q_type: str,
    ) -> Question | None:
        """Best-effort duplicate check for import: owner + normalized content + type.
        No DB UNIQUE constraint is added or required — this is application-level dedup only."""
        from sqlalchemy import func

        stmt = (
            select(Question)
            .where(Question.owner_teacher_account_id == teacher_account_id)
            .where(Question.type == q_type)
            .where(func.lower(func.trim(Question.content)) == content_normalized.lower().strip())
        )
        return db.scalars(stmt).first()


question_repository = QuestionRepository()
