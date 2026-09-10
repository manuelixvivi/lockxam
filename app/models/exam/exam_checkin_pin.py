from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ExamCheckinPin(Base):
    __tablename__ = "exam_checkin_pins"

    pin_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    schedule_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_ts: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
