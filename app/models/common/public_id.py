import uuid
from uuid import UUID

from sqlalchemy.orm import Mapped, mapped_column


class PublicIdMixin:
    public_id: Mapped[UUID] = mapped_column(default=uuid.uuid4)
