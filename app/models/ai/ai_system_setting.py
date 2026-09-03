from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class AiSystemSetting(Base):
    """
    Persisted runtime system configuration for AI providers, models, and system parameters.
    Allows SuperAdmin to update AI models and API credentials without modifying code.
    """

    __tablename__ = "ai_system_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value_json = Column(JSON, nullable=False, default=dict)
    encrypted_secret = Column(Text, nullable=True)  # Securely stored credentials
    updated_by_id = Column(Integer, ForeignKey("auth_accounts.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_by = relationship("AuthAccount", foreign_keys=[updated_by_id], lazy="select")


class AiConfigHistory(Base):
    """
    Immutable audit trail recording every configuration mutation of AI providers,
    models, and system parameters made by SuperAdmin.
    """

    __tablename__ = "ai_config_histories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    changed_by_id = Column(Integer, ForeignKey("auth_accounts.id", ondelete="SET NULL"), nullable=True)
    changed_by_name = Column(String(255), nullable=True)
    change_summary = Column(Text, nullable=False)
    provider = Column(String(100), nullable=False, default="Groq")
    model_name = Column(String(255), nullable=False)
    temperature = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    changed_by = relationship("AuthAccount", foreign_keys=[changed_by_id], lazy="select")
