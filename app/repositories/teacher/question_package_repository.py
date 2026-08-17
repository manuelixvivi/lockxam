from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.teacher.package_item import QuestionPackageItem
from app.models.teacher.question import Question
from app.models.teacher.question_package import QuestionPackage
from app.repositories.base_repository import BaseRepository


class QuestionPackageRepository(BaseRepository[QuestionPackage]):

    def __init__(self):
        super().__init__(QuestionPackage)

    def get_by_owner_and_tenant(
        self, db: Session, teacher_account_id: int, school_id: int
    ) -> list[QuestionPackage]:
        """Tenant Isolation: Query wajib memfilter school_id dan owner_teacher_account_id."""
        stmt = (
            select(QuestionPackage)
            .where(QuestionPackage.school_id == school_id)
            .where(QuestionPackage.owner_teacher_account_id == teacher_account_id)
        )
        return list(db.scalars(stmt).all())

    def get_with_question_count_by_type(self, db: Session, package_id: int) -> dict[str, int]:
        """Menghitung jumlah riil butir soal terikat per jenis di database."""
        stmt = (
            select(Question.type, func.count(Question.id))
            .join(QuestionPackageItem, QuestionPackageItem.question_id == Question.id)
            .where(QuestionPackageItem.package_id == package_id)
            .group_by(Question.type)
        )
        results = db.execute(stmt).all()
        return {row[0]: row[1] for row in results}

    def get_max_canonical_order(self, db: Session, package_id: int) -> int:
        """Mendapatkan nomor urutan canonical terakhir di dalam paket."""
        stmt = select(func.max(QuestionPackageItem.canonical_order)).where(
            QuestionPackageItem.package_id == package_id
        )
        return db.execute(stmt).scalar() or 0


question_package_repository = QuestionPackageRepository()
