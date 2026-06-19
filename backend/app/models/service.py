"""Service model for model provider configuration."""

from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Text, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Service(Base):
    """Model service provider configuration.

    Stores connection info for LLM/image/TTS service providers.
    Supports both preset (built-in) and custom (user-added) services.
    """
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    group: Mapped[str] = mapped_column(String(20))  # overseas, china, aggregator, custom
    base_url: Mapped[str] = mapped_column(String(500))
    api_key_encrypted: Mapped[str] = mapped_column(Text)
    api_format: Mapped[str] = mapped_column(String(30), default="openai_chat")  # openai_chat, openai_responses, anthropic
    stream: Mapped[bool] = mapped_column(Boolean, default=True)
    models_json: Mapped[str] = mapped_column(Text, default="[]")  # JSON array of model IDs
    config_json: Mapped[str] = mapped_column(Text, default="{}")  # temperature, etc.
    is_preset: Mapped[bool] = mapped_column(Boolean, default=False)  # True for built-in presets
    probed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
