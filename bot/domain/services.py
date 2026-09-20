from __future__ import annotations

from datetime import date

from bot.domain.models import (
    AddFoodResult,
    DayInfo,
    DaySummary,
    DeleteMealResult,
    Food,
    Macros,
    Meal,
)
from bot.domain.parsing import (
    display_name,
    parse_structured,
    totals_from_per100,
)
from bot.infrastructure.db import Database
from bot.infrastructure.deepseek import DeepSeekParser


def _today() -> str:
    return date.today().isoformat()


def _day_from_row(row) -> DayInfo:
    return DayInfo(
        id=int(row["id"]),
        user_id=int(row["user_id"]),
        date=str(row["day"]),
        label=str(row["label"]),
    )


def _meal_from_row(row) -> Meal:
    return Meal(
        id=int(row["id"]),
        name=str(row["name"]),
        calories=float(row["calories"]),
        protein=float(row["protein"]),
        fat=float(row["fat"]),
        carbs=float(row["carbs"]),
    )


class UserService:
    """Работа с пользователем и его целью КБЖУ."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def register(self, user_id: int, username: str | None) -> None:
        await self._db.upsert_user(user_id, username)

    async def get_goal(self, user_id: int) -> Macros | None:
        user = await self._db.get_user(user_id)
        if user is None or user["goal_calories"] is None:
            return None
        return Macros(
            calories=float(user["goal_calories"] or 0),
            protein=float(user["goal_protein"] or 0),
            fat=float(user["goal_fat"] or 0),
            carbs=float(user["goal_carbs"] or 0),
        )

    async def set_goal(self, user_id: int, goal: Macros) -> None:
        await self._db.set_goal(
            user_id,
            calories=goal.calories,
            protein=goal.protein,
            fat=goal.fat,
            carbs=goal.carbs,
        )


class DayService:
    """Дни, история, выбор активного дня и сводка."""

    def __init__(self, db: Database, users: UserService) -> None:
        self._db = db
        self._users = users

    async def start_new_day(self, user_id: int) -> DayInfo:
        day_id = await self._db.create_day(user_id, _today())
        await self._db.set_active_day(user_id, day_id)
        return _day_from_row(await self._db.get_day(day_id))

    async def get_current_day(self, user_id: int) -> DayInfo:
        day_id = await self._db.get_target_day(user_id, _today())
        return _day_from_row(await self._db.get_day(day_id))

    async def select_day(self, user_id: int, day_id: int) -> DayInfo | None:
        day = await self._db.get_day(day_id)
        if day is None or int(day["user_id"]) != user_id:
            return None
        await self._db.set_active_day(user_id, day_id)
        return _day_from_row(day)

    async def back_to_today(self, user_id: int) -> DayInfo:
        await self._db.clear_active_day(user_id)
        return await self.get_current_day(user_id)

    async def get_history(self, user_id: int, limit: int = 5) -> list[DayInfo]:
        rows = await self._db.get_last_days(user_id, limit)
        return [_day_from_row(r) for r in rows]

    async def get_summary(self, day_id: int) -> DaySummary | None:
        day = await self._db.get_day(day_id)
        if day is None:
            return None
        user_id = int(day["user_id"])
        meals = [_meal_from_row(m) for m in await self._db.get_meals(day_id)]
        totals_row = await self._db.get_day_totals(day_id)
        totals = Macros(
            calories=float(totals_row["calories"]),
            protein=float(totals_row["protein"]),
            fat=float(totals_row["fat"]),
            carbs=float(totals_row["carbs"]),
        )
        return DaySummary(
            day=_day_from_row(day),
            meals=meals,
            totals=totals,
            goal=await self._users.get_goal(user_id),
            is_latest=(await self._db.get_latest_day_id(user_id)) == day_id,
        )

    async def get_summary_for_user(
        self, user_id: int, day_id: int
    ) -> DaySummary | None:
        """Сводка дня, если день принадлежит пользователю."""
        day = await self._db.get_day(day_id)
        if day is None or int(day["user_id"]) != user_id:
            return None
        return await self.get_summary(day_id)

    async def delete_meal(self, user_id: int, meal_id: int) -> DeleteMealResult | None:
        """Удалить блюдо пользователя и вернуть обновлённую сводку дня.

        Возвращает None, если блюда нет или оно принадлежит чужому дню.
        """
        row = await self._db.get_meal(meal_id)
        if row is None:
            return None
        day = await self._db.get_day(int(row["day_id"]))
        if day is None or int(day["user_id"]) != user_id:
            return None
        removed = _meal_from_row(row)
        await self._db.delete_meal(meal_id)
        summary = await self.get_summary(int(day["id"]))
        if summary is None:
            return None
        return DeleteMealResult(food=removed, summary=summary)


class FoodService:
    """Добавление блюда: точный расчёт по БЖУ или оценка через DeepSeek."""

    def __init__(self, db: Database, deepseek: DeepSeekParser) -> None:
        self._db = db
        self._deepseek = deepseek

    async def try_add_exact(self, user_id: int, text: str) -> AddFoodResult | None:
        """Точный расчёт «название вес Б,Ж,У» без обращения к API.

        Возвращает None, если текст не в этом формате.
        """
        structured = parse_structured(text)
        if structured is None or not structured.has_macros:
            return None
        macros = totals_from_per100(
            structured.weight,
            structured.protein_100,
            structured.fat_100,
            structured.carbs_100,
        )
        food = Food(
            name=display_name(structured.name, structured.weight),
            calories=macros.calories,
            protein=macros.protein,
            fat=macros.fat,
            carbs=macros.carbs,
        )
        return await self._store(user_id, food)

    async def add_via_ai(self, user_id: int, text: str) -> AddFoodResult:
        """Распознать свободное описание или «название вес» через DeepSeek."""
        structured = parse_structured(text)
        weight_hint = structured.weight if structured is not None else None
        parsed = await self._deepseek.parse_food(text, weight_hint=weight_hint)
        if structured is not None:
            name = display_name(structured.name, structured.weight)
        else:
            name = str(parsed["name"])
        food = Food(
            name=name,
            calories=float(parsed["calories"]),
            protein=float(parsed["protein"]),
            fat=float(parsed["fat"]),
            carbs=float(parsed["carbs"]),
        )
        return await self._store(user_id, food)

    async def _store(self, user_id: int, food: Food) -> AddFoodResult:
        day_id = await self._db.get_target_day(user_id, _today())
        await self._db.add_meal(
            day_id,
            name=food.name,
            calories=food.calories,
            protein=food.protein,
            fat=food.fat,
            carbs=food.carbs,
        )
        day = await self._db.get_day(day_id)
        return AddFoodResult(
            food=food,
            day=_day_from_row(day),
            is_latest=(await self._db.get_latest_day_id(user_id)) == day_id,
        )
