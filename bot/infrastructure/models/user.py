"""Таблица ``users``."""

from __future__ import annotations

from sqlalchemy import REAL, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from bot.infrastructure.models.base import Base


class User(Base):
    """Пользователь: имя, цель КБЖУ и выбранный день.

    ``active_day_id`` — без внешнего ключа: в схеме это обычная колонка,
    а ссылка на день проверяется в доменных сервисах.
    """

    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str | None] = mapped_column(Text())
    goal_calories: Mapped[float | None] = mapped_column(REAL())
    goal_protein: Mapped[float | None] = mapped_column(REAL())
    goal_fat: Mapped[float | None] = mapped_column(REAL())
    goal_carbs: Mapped[float | None] = mapped_column(REAL())
    active_day_id: Mapped[int | None] = mapped_column()
    created_at: Mapped[str] = mapped_column(
        Text(), server_default=text("(datetime('now'))")
    )
