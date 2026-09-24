"""Сервис блюд: точный расчёт по БЖУ или оценка через DeepSeek."""

from __future__ import annotations

from bot.domain.models import AddFoodResult, Food
from bot.domain.parsing import (
    display_name,
    numbers_outside_brackets,
    parse_portion,
    parse_structured,
    totals_from_per100,
)
from bot.domain.services.common import today
from bot.domain.services.interfaces import DatabaseInterface
from bot.infrastructure.adapters.deepseek import DeepSeekAdapter

__all__ = ["FoodNotFoundError", "FoodService"]


class FoodNotFoundError(Exception):
    """DeepSeek не распознал продукт (found=false)."""

    def __init__(self, query: str) -> None:
        super().__init__(query)
        self.query = query


class FoodService:
    """Добавление блюда: точный расчёт по БЖУ или оценка через DeepSeek."""

    def __init__(self, db: DatabaseInterface, deepseek: DeepSeekAdapter) -> None:
        self._db = db
        self._deepseek = deepseek

    async def try_add_exact(self, user_id: int, text: str) -> AddFoodResult | None:
        """Точный расчёт по указанным Б/Ж/У, без обращения к API.

        Форматы:
        - «название вес Б,Ж,У» — Б/Ж/У на 100 г, пересчёт на указанный вес;
        - «название Б,Ж,У» — Б/Ж/У на всю порцию, вес не указывается.
        Числа целиком в скобках («Экспонента (30 0 6,5)») — это второй формат,
        даже если запятая в дроби выглядит как разделитель.

        Возвращает None, если текст не подходит ни под один формат.
        """
        structured = parse_structured(text)
        per100 = structured.per100 if structured is not None else None
        if (
            structured is not None
            and per100 is not None
            and numbers_outside_brackets(text)
        ):
            protein_100, fat_100, carbs_100 = per100
            name = display_name(structured.name, structured.weight)
            macros = totals_from_per100(
                structured.weight, protein_100, fat_100, carbs_100
            )
        else:
            portion = parse_portion(text)
            if portion is None:
                return None
            name = display_name(portion.name)
            macros = portion.macros
        return await self._store(
            user_id,
            Food(
                name=name,
                calories=macros.calories,
                protein=macros.protein,
                fat=macros.fat,
                carbs=macros.carbs,
            ),
        )

    async def add_via_ai(self, user_id: int, text: str) -> AddFoodResult:
        """Распознать свободное описание или «название вес» через DeepSeek.

        Название берётся из ответа модели. Если модель вернула found=false
        (это не продукт питания), бросает :class:`FoodNotFoundError` —
        запись в день не добавляется.
        """
        structured = parse_structured(text)
        weight_hint = structured.weight if structured is not None else None
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
        return await self._store(user_id, food)

    async def _store(self, user_id: int, food: Food) -> AddFoodResult:
        day = await self._db.get_target_day(user_id, today())
        await self._db.add_meal(day.id, food)
        return AddFoodResult(
            food=food,
            day=day,
            is_latest=(await self._db.get_latest_day_id(user_id)) == day.id,
        )
