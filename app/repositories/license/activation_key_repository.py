from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.license.activation_key import ActivationKey
from app.repositories.base_repository import BaseRepository


class ActivationKeyRepository(BaseRepository[ActivationKey]):
    def __init__(self):
        super().__init__(ActivationKey)

    def get_by_key(self, db: Session, key_hash: str) -> ActivationKey | None:
        return db.scalar(select(ActivationKey).where(ActivationKey.key == key_hash))

    def get_by_public_id(self, db: Session, public_id: UUID) -> ActivationKey | None:
        return db.scalar(select(ActivationKey).where(ActivationKey.public_id == public_id))

    def get_all_ordered_by_created_at_desc(self, db: Session) -> list[ActivationKey]:
        return list(
            db.scalars(select(ActivationKey).order_by(ActivationKey.created_at.desc())).all()
        )


activation_key_repository = ActivationKeyRepository()
