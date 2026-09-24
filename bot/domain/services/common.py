"""Общие помощники сервисов: текущая дата и строки БД → доменные модели."""

from __future__ import annotations

from datetime import date

from bot.domain.models import DayInfo, Meal
from bot.domain.services.interfaces import Row

__all__ = ["day_from_row", "meal_from_row", "today"]


def today() -> str:
    """Сегодняшняя дата в формате ISO."""
    return date.today().isoformat()


def day_from_row(row: Row) -> DayInfo:
    """Преобразовать строку таблицы ``days`` в модель дня."""
    return DayInfo(
        id=int(row["id"]),
        user_id=int(row["user_id"]),
        date=str(row["day"]),
        label=str(row["label"]),
    )


def meal_from_row(row: Row) -> Meal:
    """Преобразовать строку таблицы ``meals`` в модель блюда."""
    return Meal(
        id=int(row["id"]),
        name=str(row["name"]),
        calories=float(row["calories"]),
        protein=float(row["protein"]),
        fat=float(row["fat"]),
        carbs=float(row["carbs"]),
    )
