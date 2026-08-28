from sqlalchemy import select, func
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

    def get_by_ids(self, db: Session, account_ids: list[int]) -> list[AuthAccount]:
        if not account_ids:
            return []
        return list(db.scalars(select(AuthAccount).where(AuthAccount.id.in_(account_ids))).all())

    def get_superadmin(self, db: Session) -> AuthAccount | None:
        from app.models.security.enums import UserRole
        return db.scalar(
            select(AuthAccount).where(AuthAccount.role.in_([UserRole.SUPERADMIN, "SUPERADMIN"]))
        )

    def get_school_admin(self, db: Session, school_id: int) -> AuthAccount | None:
        from app.models.security.enums import UserRole
        return db.scalar(
            select(AuthAccount).where(
                AuthAccount.school_id == school_id,
                AuthAccount.role.in_([UserRole.ADMIN, "SCHOOL_ADMIN", "ADMIN"]),
            )
        )

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

    def list_students_by_school(self, db: Session, school_id: int) -> list[AuthAccount]:
        from app.models.security.enums import UserRole
        return list(
            db.scalars(
                select(AuthAccount).where(
                    AuthAccount.school_id == school_id,
                    AuthAccount.role.in_([UserRole.STUDENT, "STUDENT"]),
                )
            ).all()
        )

    def count_students_by_school(self, db: Session, school_id: int) -> int:
        from app.models.security.enums import UserRole
        stmt = select(func.count(AuthAccount.id)).where(
            AuthAccount.school_id == school_id,
            AuthAccount.role.in_([UserRole.STUDENT, "STUDENT"]),
        )
        return db.scalar(stmt) or 0

    def get_by_public_id_and_school(self, db: Session, school_id: int, public_id: any, role: str | None = None) -> AuthAccount | None:
        from uuid import UUID
        pid = UUID(str(public_id)) if isinstance(public_id, str) else public_id
        stmt = select(AuthAccount).where(AuthAccount.school_id == school_id, AuthAccount.public_id == pid)
        if role:
            stmt = stmt.where(AuthAccount.role.in_([role, role.upper()]))
        return db.scalar(stmt)

    def get_teacher_by_code(self, db: Session, school_id: int, teacher_code: str) -> AuthAccount | None:
        from app.models.security.enums import UserRole
        return db.scalar(
            select(AuthAccount).where(
                AuthAccount.school_id == school_id,
                AuthAccount.role.in_([UserRole.TEACHER, "TEACHER"]),
                func.lower(AuthAccount.teacher_code) == teacher_code.strip().lower(),
            )
        )

    def get_by_nip(self, db: Session, school_id: int, nip: str) -> AuthAccount | None:
        return db.scalar(
            select(AuthAccount).where(
                AuthAccount.school_id == school_id,
                AuthAccount.nip == nip.strip(),
            )
        )

    def get_by_nisn(self, db: Session, school_id: int, nisn: str) -> AuthAccount | None:
        return db.scalar(
            select(AuthAccount).where(
                AuthAccount.school_id == school_id,
                AuthAccount.nisn == nisn.strip(),
            )
        )

    def get_by_nis(self, db: Session, school_id: int, nis: str) -> AuthAccount | None:
        return db.scalar(
            select(AuthAccount).where(
                AuthAccount.school_id == school_id,
                AuthAccount.nis == nis.strip(),
            )
        )



auth_repository = AuthRepository()
