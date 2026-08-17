from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.license.renewal_request import RenewalRequest
from app.repositories.base_repository import BaseRepository


class RenewalRequestRepository(BaseRepository[RenewalRequest]):
    def __init__(self):
        super().__init__(RenewalRequest)

    def get_by_request_number(self, db: Session, request_number: str) -> RenewalRequest | None:
        return db.scalar(
            select(RenewalRequest).where(RenewalRequest.request_number == request_number)
        )

    def get_by_public_id(self, db: Session, public_id: UUID) -> RenewalRequest | None:
        return db.scalar(select(RenewalRequest).where(RenewalRequest.public_id == public_id))

    def get_requests_by_school(self, db: Session, school_id: int) -> list[RenewalRequest]:
        return list(
            db.scalars(
                select(RenewalRequest)
                .where(RenewalRequest.school_id == school_id)
                .order_by(RenewalRequest.created_at.desc())
            ).all()
        )

    def get_latest_request_for_year(self, db: Session, year: int) -> RenewalRequest | None:
        prefix = f"RR-{year}-"
        return db.scalar(
            select(RenewalRequest)
            .where(RenewalRequest.request_number.like(f"{prefix}%"))
            .order_by(RenewalRequest.request_number.desc())
            .limit(1)
        )


renewal_request_repository = RenewalRequestRepository()
