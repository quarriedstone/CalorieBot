"""Таблица ``meals``."""

from __future__ import annotations

from sqlalchemy import REAL, ForeignKey, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from bot.infrastructure.models.base import Base


class Meal(Base):
    """Блюдо внутри дня (записи КБЖУ)."""

    __tablename__ = "meals"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(primary_key=True)
    day_id: Mapped[int] = mapped_column(ForeignKey("days.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text())
    calories: Mapped[float] = mapped_column(REAL(), server_default=text("0"))
    protein: Mapped[float] = mapped_column(REAL(), server_default=text("0"))
    fat: Mapped[float] = mapped_column(REAL(), server_default=text("0"))
    carbs: Mapped[float] = mapped_column(REAL(), server_default=text("0"))
    created_at: Mapped[str] = mapped_column(
        Text(), server_default=text("(datetime('now'))")
    )


__all__ = ["Meal"]
