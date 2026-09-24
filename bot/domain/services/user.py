"""Сервис пользователя: регистрация и цель КБЖУ."""

from __future__ import annotations

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
