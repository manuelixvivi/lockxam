from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.teacher.package_item import QuestionPackageItem
from app.models.teacher.question import Question
from app.models.teacher.question_package import QuestionPackage
from app.repositories.base_repository import BaseRepository


class QuestionPackageRepository(BaseRepository[QuestionPackage]):

    def __init__(self):
        super().__init__(QuestionPackage)

    def get_by_id_with_items_and_questions(
        self, db: Session, package_id: int
    ) -> QuestionPackage | None:
        from sqlalchemy.orm import selectinload
        stmt = (
            select(QuestionPackage)
            .where(QuestionPackage.id == package_id)
            .options(
                selectinload(QuestionPackage.items).selectinload(QuestionPackageItem.question)
            )
        )
        return db.scalar(stmt)

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

    def get_item(
        self, db: Session, package_id: int, question_id: int
    ) -> QuestionPackageItem | None:
        stmt = select(QuestionPackageItem).where(
            QuestionPackageItem.package_id == package_id,
            QuestionPackageItem.question_id == question_id,
        )
        return db.scalar(stmt)

    def list_items(self, db: Session, package_id: int) -> list[QuestionPackageItem]:
        stmt = (
            select(QuestionPackageItem)
            .where(QuestionPackageItem.package_id == package_id)
            .order_by(QuestionPackageItem.canonical_order.asc())
        )
        return list(db.scalars(stmt).all())

    def delete_item(self, db: Session, item: QuestionPackageItem) -> None:
        db.delete(item)

    def delete_by_owner(self, db: Session, owner_teacher_id: int) -> None:
        pkgs = (
            self.get_by_owner_and_tenant(db, owner_teacher_id, school_id=None)
            if hasattr(self, "get_by_owner")
            else list(
                db.scalars(
                    select(QuestionPackage).where(
                        QuestionPackage.owner_teacher_account_id == owner_teacher_id
                    )
                ).all()
            )
        )
        for p in pkgs:
            items = self.list_items(db, p.id)
            for it in items:
                db.delete(it)
            db.delete(p)


question_package_repository = QuestionPackageRepository()
