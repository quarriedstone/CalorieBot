"""Порт (интерфейс) хранилища.

Сервисы домена зависят от абстракции :class:`DatabaseInterface`, а конкретные
реализации живут в ``bot/infrastructure/adapters/databases`` — например,
``DatabaseAdapter``.
"""

from __future__ import annotations

from typing import Protocol

from bot.domain.models import DayInfo, Food, Macros, Meal, User


class DatabaseInterface(Protocol):
    """Хранилище пользователей, дней и записей о еде.

    Протокол структурный: классу-реализации достаточно иметь эти методы
    с совпадающими сигнатурами (явное наследование не обязательно, но
    ``DatabaseAdapter`` его указывает).

    Методы принимают и возвращают только доменные модели: как данные лежат
    внутри (таблицы, строки, SQL) — деталь реализации. Соединение адаптер
    открывает сам на время запроса, а схему (таблицы и миграции) накатывает
    Alembic — порт об этом ничего не знает.
    """

    # ---------- users ----------
    async def upsert_user(self, user_id: int, username: str | None) -> None: ...

    async def get_user(self, user_id: int) -> User | None: ...

    async def set_goal(self, user_id: int, goal: Macros) -> None: ...

    async def set_active_day(self, user_id: int, day_id: int | None) -> None: ...

    async def clear_active_day(self, user_id: int) -> None: ...

    # ---------- days ----------
    async def create_day(self, user_id: int, day: str) -> DayInfo: ...

    async def get_latest_day_id(self, user_id: int) -> int | None: ...

    async def get_target_day(self, user_id: int, day: str) -> DayInfo: ...

    async def get_day(self, day_id: int) -> DayInfo | None: ...

    async def get_last_days(self, user_id: int, limit: int = 5) -> list[DayInfo]: ...

    async def delete_day(self, day_id: int) -> None: ...

    # ---------- meals ----------
    async def add_meal(self, day_id: int, food: Food) -> None: ...

    async def get_meals(self, day_id: int) -> list[Meal]: ...

    async def get_meal(self, meal_id: int) -> Meal | None: ...

    async def delete_meal(self, meal_id: int) -> None: ...

    async def get_day_totals(self, day_id: int) -> Macros: ...
