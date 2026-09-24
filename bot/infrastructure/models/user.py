"""Таблица ``users``."""

from __future__ import annotations

from sqlalchemy import REAL, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from bot.domain.models import Macros
from bot.infrastructure.models.base import Base


class User(Base):
    """Пользователь: имя, цель КБЖУ и выбранный день.

    Атрибуты названы как поля доменной модели, поэтому строка БД превращается
    в :class:`bot.domain.models.User` без ручного маппинга.

    ``active_day_id`` — без внешнего ключа: в схеме это обычная колонка,
    а ссылка на день проверяется в доменных сервисах.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column("user_id", primary_key=True)
    username: Mapped[str | None] = mapped_column(Text())
    goal_calories: Mapped[float | None] = mapped_column(REAL())
    goal_protein: Mapped[float | None] = mapped_column(REAL())
    goal_fat: Mapped[float | None] = mapped_column(REAL())
    goal_carbs: Mapped[float | None] = mapped_column(REAL())
    active_day_id: Mapped[int | None] = mapped_column()
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
