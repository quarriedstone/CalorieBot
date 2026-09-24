"""Порт (интерфейс) хранилища.

Сервисы домена зависят от абстракции :class:`DatabaseInterface`, а конкретные
реализации живут в ``bot/infrastructure/adapters/databases`` — например,
``SqliteAdapter``.
"""

from __future__ import annotations

from typing import Protocol

import aiosqlite

Row = aiosqlite.Row
"""Строка результата запроса (``aiosqlite.Row``)."""


class DatabaseInterface(Protocol):
    """Хранилище пользователей, дней и записей о еде.

    Протокол структурный: классу-реализации достаточно иметь эти методы
    с совпадающими сигнатурами (явное наследование не обязательно, но
    ``SqliteAdapter`` его указывает).

    Здесь только публичные операции с данными. Управление подключением
    (``init``/``shutdown``) — деталь конкретного адаптера, в порт не входит:
    жизненным циклом занимается тот, кто создаёт адаптер.
    """

    # ---------- users ----------
    async def upsert_user(self, user_id: int, username: str | None) -> None: ...

    async def get_user(self, user_id: int) -> Row | None: ...

    async def set_goal(
        self,
        user_id: int,
        calories: float,
        protein: float,
        fat: float,
        carbs: float,
    ) -> None: ...

    async def set_active_day(self, user_id: int, day_id: int | None) -> None: ...

    async def clear_active_day(self, user_id: int) -> None: ...

    # ---------- days ----------
    async def create_day(self, user_id: int, day: str) -> int: ...

    async def get_latest_day_id(self, user_id: int) -> int | None: ...

    async def get_current_day(self, user_id: int, day: str) -> int: ...

    async def get_target_day(self, user_id: int, day: str) -> int: ...

    async def get_day(self, day_id: int) -> Row | None: ...

    async def get_last_days(self, user_id: int, limit: int = 5) -> list[Row]: ...

    async def delete_day(self, day_id: int) -> None: ...

    # ---------- meals ----------
    async def add_meal(
        self,
        day_id: int,
        name: str,
        calories: float,
        protein: float,
        fat: float,
        carbs: float,
    ) -> None: ...

    async def get_meals(self, day_id: int) -> list[Row]: ...

    async def get_meal(self, meal_id: int) -> Row | None: ...

    async def delete_meal(self, meal_id: int) -> None: ...

    async def get_day_totals(self, day_id: int) -> dict[str, float]: ...
