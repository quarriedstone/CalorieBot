from __future__ import annotations

from pydantic import BaseModel


class Macros(BaseModel):
    """Калории и БЖУ без названия (цель, итоги дня)."""

    calories: float
    protein: float
    fat: float
    carbs: float


class Food(Macros):
    """Блюдо с названием и КБЖУ."""

    name: str


class DayInfo(BaseModel):
    """Запись дня."""

    id: int
    user_id: int
    date: str
    label: str


class DaySummary(BaseModel):
    """Сводка дня: блюда, итоги, цель и признак «последний ли это день»."""

    day: DayInfo
    meals: list[Food]
    totals: Macros
    goal: Macros | None = None
    is_latest: bool


class AddFoodResult(BaseModel):
    """Результат добавления блюда."""

    food: Food
    day: DayInfo
    is_latest: bool
