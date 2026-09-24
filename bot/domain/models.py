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


class Meal(Food):
    """Блюдо из таблицы дня: КБЖУ, id записи и день, к которому она относится."""

    id: int
    day_id: int


class DayInfo(BaseModel):
    """Запись дня."""

    id: int
    user_id: int
    date: str
    label: str


class User(BaseModel):
    """Пользователь: имя, цель КБЖУ и выбранный день."""

    id: int
    username: str | None = None
    goal: Macros | None = None
    active_day_id: int | None = None


class DaySummary(BaseModel):
    """Сводка дня: блюда, итоги, цель и признак «последний ли это день»."""

    day: DayInfo
    meals: list[Meal]
    totals: Macros
    goal: Macros | None = None
    is_latest: bool


class AddFoodResult(BaseModel):
    """Результат добавления блюда."""

    food: Food
    day: DayInfo
    is_latest: bool


class DeleteMealResult(BaseModel):
    """Результат удаления блюда: что удалили и обновлённая сводка дня."""

    food: Food
    summary: DaySummary
