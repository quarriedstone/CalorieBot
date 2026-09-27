"""Порт (интерфейс) хранилища.

Сервисы домена зависят от абстракции :class:`DatabaseInterface`, а конкретные
реализации живут в ``bot/infrastructure/adapters/databases`` — например,
``DatabaseAdapter``.
"""

from __future__ import annotations

from typing import Protocol

from bot.domain.models import Food, Macros, Meal, NoteInfo, User


class DatabaseInterface(Protocol):
    """Хранилище пользователей, заметок и записей о еде.

    Протокол структурный: классу-реализации достаточно иметь эти методы
    с совпадающими сигнатурами (явное наследование не обязательно, но
    ``DatabaseAdapter`` его указывает).

    Методы принимают и возвращают только доменные модели: как данные лежат
    внутри (таблицы, строки, SQL) — деталь реализации. Соединение адаптер
    открывает сам на время запроса, а схему (таблицы и миграции) накатывает
    Alembic — порт об этом ничего не знает.

    Порт — это примитивы хранилища (CRUD), а не операции домена: выбор
    активной и текущей заметки, генерация её названия и проверка владельца
    живут в сервисах, а не здесь.
    """

    # ---------- users ----------
    async def upsert_user(self, user_id: int, username: str | None) -> None: ...

    async def get_user(self, user_id: int) -> User | None: ...

    async def set_goal(self, user_id: int, goal: Macros) -> None: ...

    async def set_active_note(self, user_id: int, note_id: int | None) -> None: ...

    # ---------- notes ----------
    async def add_note(self, user_id: int, date: str, label: str) -> NoteInfo: ...

    async def get_note(self, note_id: int) -> NoteInfo | None: ...

    async def count_notes(self, user_id: int, date: str) -> int: ...

    async def get_last_notes(self, user_id: int, limit: int = 5) -> list[NoteInfo]: ...

    async def delete_note(self, note_id: int) -> None: ...

    # ---------- meals ----------
    async def add_meal(self, note_id: int, food: Food) -> None: ...

    async def get_meals(self, note_id: int) -> list[Meal]: ...

    async def get_meal(self, meal_id: int) -> Meal | None: ...

    async def delete_meal(self, meal_id: int) -> None: ...

    async def get_note_totals(self, note_id: int) -> Macros: ...
