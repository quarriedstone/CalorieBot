"""Сервис пользователя: регистрация и цель КБЖУ."""

from __future__ import annotations

import re

from bot.domain.models import Macros
from bot.domain.services.interfaces import DatabaseInterface

__all__ = ["UserService"]


class UserService:
    """Работа с пользователем и его целью КБЖУ."""

    def __init__(self, db: DatabaseInterface) -> None:
        self._db = db

    async def register(self, user_id: int, username: str | None) -> None:
        await self._db.upsert_user(user_id, username)

    async def get_goal(self, user_id: int) -> Macros | None:
        user = await self._db.get_user(user_id)
        return None if user is None else user.goal

    async def set_goal(self, user_id: int, goal: Macros) -> None:
        await self._db.set_goal(user_id, goal)

    def parse_goal(self, text: str) -> Macros | None:
        """Разобрать цель вида «Б/Ж/У», например «120/60/220».

        Возвращает Macros либо None. Калории считаются по формуле
        Б×4 + Ж×9 + У×4.
        """
        text = text.strip()
        # «120/60/220», «120 60 220» — запятая внутри числа = разделитель дробей
        values = self._goal_numbers(text, r"[\s/|;]+")
        if values is None:
            # «120,60,220» — запятая как разделитель
            values = self._goal_numbers(text, r"\s*,\s*")
        if values is None or any(v < 0 for v in values):
            return None
        protein, fat, carbs = values
        return Macros.from_nutrients(protein, fat, carbs)

    # ---------- внутренние методы ----------
    @staticmethod
    def _goal_numbers(text: str, separators: str) -> list[float] | None:
        parts = [p for p in re.split(separators, text) if p]
        if len(parts) != 3:
            return None
        try:
            return [float(p.replace(",", ".")) for p in parts]
        except ValueError:
            return None
