"""Таблица ``notes``."""

from __future__ import annotations

from sqlalchemy import Text, text
from sqlalchemy.orm import Mapped, mapped_column

from bot.infrastructure.models.base import Base


class Note(Base):
    """Заметка: дата, название и владелец.

    Атрибуты названы как поля доменной модели
    :class:`bot.domain.models.NoteInfo`, поэтому строка БД превращается в неё
    без ручного маппинга.
    """

    __tablename__ = "notes"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column()
    date: Mapped[str] = mapped_column(Text())
    label: Mapped[str] = mapped_column(Text())
    created_at: Mapped[str] = mapped_column(
        Text(), server_default=text("(datetime('now'))")
    )


__all__ = ["Note"]
