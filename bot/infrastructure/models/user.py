"""Таблица ``users``."""

from __future__ import annotations

from sqlalchemy import REAL, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from bot.domain.models import Macros
from bot.infrastructure.models.base import Base


class User(Base):
    """Пользователь: имя, цель КБЖУ и выбранная заметка.

    Атрибуты названы как поля доменной модели, поэтому строка БД превращается
    в :class:`bot.domain.models.User` без ручного маппинга.

    ``active_note_id`` — без внешнего ключа: в схеме это обычная колонка,
    а ссылка на заметку проверяется в доменных сервисах.
    ``paid_until`` — ISO-время окончания подписки (UTC) или ``NULL``.
    ``notes_day`` / ``notes_created`` — сколько заметок создано в эту дату
    (удаление счётчик не уменьшает).
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column("user_id", primary_key=True)
    username: Mapped[str | None] = mapped_column(Text())
    goal_calories: Mapped[float | None] = mapped_column(REAL())
    goal_protein: Mapped[float | None] = mapped_column(REAL())
    goal_fat: Mapped[float | None] = mapped_column(REAL())
    goal_carbs: Mapped[float | None] = mapped_column(REAL())
    active_note_id: Mapped[int | None] = mapped_column()
    paid_until: Mapped[str | None] = mapped_column(Text())
    notes_day: Mapped[str | None] = mapped_column(Text())
    notes_created: Mapped[int] = mapped_column(Integer(), server_default=text("0"))
    created_at: Mapped[str] = mapped_column(
        Text(), server_default=text("(datetime('now'))")
    )

    @property
    def goal(self) -> Macros | None:
        """Цель КБЖУ, собранная из четырёх колонок (``None`` — цель не задана)."""
        if self.goal_calories is None:
            return None
        return Macros(
            calories=self.goal_calories,
            protein=self.goal_protein or 0,
            fat=self.goal_fat or 0,
            carbs=self.goal_carbs or 0,
        )
