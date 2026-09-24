"""Таблица ``days``."""

from __future__ import annotations

from sqlalchemy import Text, text
from sqlalchemy.orm import Mapped, mapped_column

from bot.infrastructure.models.base import Base


class Day(Base):
    """День (в интерфейсе — заметка): дата, название и владелец."""

    __tablename__ = "days"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column()
    day: Mapped[str] = mapped_column(Text())
    label: Mapped[str] = mapped_column(Text())
    created_at: Mapped[str] = mapped_column(
        Text(), server_default=text("(datetime('now'))")
    )


__all__ = ["Day"]
