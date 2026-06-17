"""Scene model."""

from typing import Optional
from sqlalchemy import String, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Scene(Base):
    __tablename__ = "scenes"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255))
    text: Mapped[str] = mapped_column(Text)
    shot_type: Mapped[str] = mapped_column(String(20))
    narration: Mapped[str] = mapped_column(Text)
    edit_prompt: Mapped[str] = mapped_column(Text)
    instruction: Mapped[str] = mapped_column(Text, default="")
    character: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    project: Mapped["Project"] = relationship(back_populates="scenes")
