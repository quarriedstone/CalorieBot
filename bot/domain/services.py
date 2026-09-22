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
    FoodInput,
    base_name,
    display_name,
    match_key,
    parse_food_input,
    totals_from_per100,
    weight_from_name,
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
    weight = row["weight"]
    return Meal(
        id=int(row["id"]),
        name=str(row["name"]),
        calories=float(row["calories"]),
        protein=float(row["protein"]),
        fat=float(row["fat"]),
        carbs=float(row["carbs"]),
        weight=float(weight) if weight is not None else None,
    )


def _meal_weight(meal: Meal) -> float | None:
    """Вес записи: из колонки или (для старых записей) из названия."""
    weight = meal.weight if meal.weight is not None else weight_from_name(meal.name)
    if weight is None or weight <= 0:
        return None
    return weight


def _scaled(macros: Macros, factor: float) -> Macros:
    """КБЖУ, умноженное на коэффициент (например, на рост веса порции)."""
    return Macros(
        calories=macros.calories * factor,
        protein=macros.protein * factor,
        fat=macros.fat * factor,
        carbs=macros.carbs * factor,
    )


def _sum(left: Macros, right: Macros) -> Macros:
    """Сумма КБЖУ двух записей."""
    return Macros(
        calories=left.calories + right.calories,
        protein=left.protein + right.protein,
        fat=left.fat + right.fat,
        carbs=left.carbs + right.carbs,
    )


class FoodNotFoundError(Exception):
    """DeepSeek не распознал продукт (found=false)."""

    def __init__(self, query: str) -> None:
        super().__init__(query)
        self.query = query


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

    async def get_selected_day(self, user_id: int) -> DayInfo | None:
        """Активный день пользователя или None, если он не выбран."""
        user = await self._db.get_user(user_id)
        if user is None or user["active_day_id"] is None:
            return None
        day = await self._db.get_day(int(user["active_day_id"]))
        if day is None or int(day["user_id"]) != user_id:
            return None
        return _day_from_row(day)

    async def get_history(self, user_id: int, limit: int = 5) -> list[DayInfo]:
        rows = await self._db.get_last_days(user_id, limit)
        return [_day_from_row(r) for r in rows]

    async def delete_day(self, user_id: int, day_id: int) -> DayInfo | None:
        """Удалить день пользователя вместе с записями.

        Возвращает None, если дня нет или он чужой. Если день был активным,
        выбор активного дня сбрасывается.
        """
        day = await self._db.get_day(day_id)
        if day is None or int(day["user_id"]) != user_id:
            return None
        user = await self._db.get_user(user_id)
        if user is not None and user["active_day_id"] == day_id:
            await self._db.clear_active_day(user_id)
        await self._db.delete_day(day_id)
        return _day_from_row(day)

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
    """Добавление блюда: повтор обновляет запись, иначе — расчёт по БЖУ или DeepSeek."""

    def __init__(self, db: Database, deepseek: DeepSeekParser) -> None:
        self._db = db
        self._deepseek = deepseek

    async def try_add_exact(self, user_id: int, text: str) -> AddFoodResult | None:
        """Добавить блюдо без обращения к модели, если это возможно.

        Сначала ищем в активной заметке блюдо с тем же названием: повтор
        обновляет существующую запись (суммарный вес или ещё одна порция),
        а не создаёт новую строку. КБЖУ найденной записи используются и для
        ввода вида «название вес», поэтому модель не вызывается.

        Возвращает None, если КБЖУ без модели не посчитать.
        """
        food_input = parse_food_input(text)
        day_id = await self._db.find_target_day(user_id)
        if day_id is not None:
            meal = self._match_meal(await self._db.get_meals(day_id), food_input)
            if meal is not None:
                return await self._merge(user_id, day_id, meal, food_input)

        macros = food_input.macros
        if macros is None:
            # «круассан 60»: КБЖУ подберёт модель (см. add_via_ai)
            return None
        food = Food(
            name=food_input.display or display_name(food_input.name),
            calories=macros.calories,
            protein=macros.protein,
            fat=macros.fat,
            carbs=macros.carbs,
        )
        return await self._store(user_id, food, weight=food_input.weight)

    async def add_via_ai(self, user_id: int, text: str) -> AddFoodResult:
        """Распознать свободное описание или «название вес» через DeepSeek.

        Название берётся из ответа модели. Если модель вернула found=false
        (это не продукт питания), бросает :class:`FoodNotFoundError` —
        запись в день не добавляется.
        """
        weight_hint = parse_food_input(text).weight
        parsed = await self._deepseek.parse_food(text, weight_hint=weight_hint)
        if not parsed["found"]:
            raise FoodNotFoundError(text)
        food = Food(
            name=str(parsed["name"]),
            calories=float(parsed["calories"]),
            protein=float(parsed["protein"]),
            fat=float(parsed["fat"]),
            carbs=float(parsed["carbs"]),
        )
        return await self._store(user_id, food, weight=weight_hint)

    def _match_meal(self, rows, food_input: FoodInput) -> Meal | None:
        """Последняя запись заметки с тем же названием и того же типа.

        Тип записи — «вес» (вес известен) или «порция» (вес не указан):
        между собой они не смешиваются, для другого типа создаётся новая строка.
        """
        key = food_input.key
        if not key:
            return None
        for row in reversed(rows):
            meal = _meal_from_row(row)
            if (_meal_weight(meal) is not None) != food_input.is_weight:
                continue
            if match_key(meal.name) == key:
                return meal
        return None

    async def _merge(
        self,
        user_id: int,
        day_id: int,
        meal: Meal,
        food_input: FoodInput,
    ) -> AddFoodResult:
        """Обновить совпавшую запись вместо создания новой."""
        if food_input.is_weight:
            stored = _meal_weight(meal) or 0.0
            total = stored + (food_input.weight or 0.0)
            if food_input.per100 is not None:
                # Б/Ж/У на 100 г из свежего сообщения — плотность берём из них
                macros = totals_from_per100(total, *food_input.per100)
            else:
                macros = _scaled(meal, total / stored if stored > 0 else 1.0)
            name = display_name(base_name(meal.name), total)
            weight = total
            added_weight = food_input.weight
        else:
            # порция: указанные Б/Ж/У либо (при вводе без чисел) ещё одна такая же
            macros = _sum(meal, food_input.macros or meal)
            name = meal.name
            weight = meal.weight
            added_weight = None

        await self._db.update_meal(
            meal.id,
            name=name,
            calories=macros.calories,
            protein=macros.protein,
            fat=macros.fat,
            carbs=macros.carbs,
            weight=weight,
        )
        day = await self._db.get_day(day_id)
        return AddFoodResult(
            food=Food(
                name=name,
                calories=macros.calories,
                protein=macros.protein,
                fat=macros.fat,
                carbs=macros.carbs,
            ),
            day=_day_from_row(day),
            is_latest=(await self._db.get_latest_day_id(user_id)) == day_id,
            merged=True,
            added_weight=added_weight,
        )

    async def _store(
        self,
        user_id: int,
        food: Food,
        weight: float | None = None,
    ) -> AddFoodResult:
        day_id = await self._db.get_target_day(user_id, _today())
        await self._db.add_meal(
            day_id,
            name=food.name,
            calories=food.calories,
            protein=food.protein,
            fat=food.fat,
            carbs=food.carbs,
            weight=weight,
        )
        day = await self._db.get_day(day_id)
        return AddFoodResult(
            food=food,
            day=_day_from_row(day),
            is_latest=(await self._db.get_latest_day_id(user_id)) == day_id,
        )
