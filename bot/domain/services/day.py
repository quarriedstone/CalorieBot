"""Сервис дней: создание, история, выбор активного дня, сводка и удаление."""

from __future__ import annotations

from bot.domain.models import DayInfo, DaySummary, DeleteMealResult
from bot.domain.services.common import today
from bot.domain.services.interfaces import DatabaseInterface
from bot.domain.services.user import UserService

__all__ = ["DayService"]


class DayService:
    """Дни, история, выбор активного дня и сводка."""

    def __init__(self, db: DatabaseInterface, users: UserService) -> None:
        self._db = db
        self._users = users

    async def start_new_day(self, user_id: int) -> DayInfo:
        day = await self._db.create_day(user_id, today())
        await self._db.set_active_day(user_id, day.id)
        return day

    async def get_current_day(self, user_id: int) -> DayInfo:
        return await self._db.get_target_day(user_id, today())

    async def select_day(self, user_id: int, day_id: int) -> DayInfo | None:
        day = await self._db.get_day(day_id)
        if day is None or day.user_id != user_id:
            return None
        await self._db.set_active_day(user_id, day_id)
        return day

    async def get_selected_day(self, user_id: int) -> DayInfo | None:
        """Активный день пользователя или None, если он не выбран."""
        user = await self._db.get_user(user_id)
        if user is None or user.active_day_id is None:
            return None
        day = await self._db.get_day(user.active_day_id)
        if day is None or day.user_id != user_id:
            return None
        return day

    async def get_history(self, user_id: int, limit: int = 5) -> list[DayInfo]:
        return await self._db.get_last_days(user_id, limit)

    async def delete_day(self, user_id: int, day_id: int) -> DayInfo | None:
        """Удалить день пользователя вместе с записями.

        Возвращает None, если дня нет или он чужой. Если день был активным,
        выбор активного дня сбрасывается.
        """
        day = await self._db.get_day(day_id)
        if day is None or day.user_id != user_id:
            return None
        user = await self._db.get_user(user_id)
        if user is not None and user.active_day_id == day_id:
            await self._db.clear_active_day(user_id)
        await self._db.delete_day(day_id)
        return day

    async def get_summary(self, day_id: int) -> DaySummary | None:
        day = await self._db.get_day(day_id)
        if day is None:
            return None
        return DaySummary(
            day=day,
            meals=await self._db.get_meals(day_id),
            totals=await self._db.get_day_totals(day_id),
            goal=await self._users.get_goal(day.user_id),
            is_latest=(await self._db.get_latest_day_id(day.user_id)) == day_id,
        )

    async def get_summary_for_user(
        self, user_id: int, day_id: int
    ) -> DaySummary | None:
        """Сводка дня, если день принадлежит пользователю."""
        day = await self._db.get_day(day_id)
        if day is None or day.user_id != user_id:
            return None
        return await self.get_summary(day_id)

    async def delete_meal(self, user_id: int, meal_id: int) -> DeleteMealResult | None:
        """Удалить блюдо пользователя и вернуть обновлённую сводку дня.

        Возвращает None, если блюда нет или оно принадлежит чужому дню.
        """
        meal = await self._db.get_meal(meal_id)
        if meal is None:
            return None
        day = await self._db.get_day(meal.day_id)
        if day is None or day.user_id != user_id:
            return None
        await self._db.delete_meal(meal_id)
        summary = await self.get_summary(meal.day_id)
        if summary is None:
            return None
        return DeleteMealResult(food=meal, summary=summary)
