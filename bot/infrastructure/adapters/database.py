"""Адаптер базы данных: SQLAlchemy поверх aiosqlite."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from bot.domain.models import Food, Macros, Meal, NoteInfo, User
from bot.domain.services.interfaces import DatabaseInterface
from bot.infrastructure import models as tables


class DatabaseAdapter(DatabaseInterface):
    """Адаптер базы данных поверх SQLAlchemy (aiosqlite).

    Долгоживущего соединения нет: ``NullPool`` плюс сессия на один запрос —
    соединение открывается на время метода и закрывается на выходе. Запросы
    собираются из моделей таблиц (:mod:`bot.infrastructure.models`), SQL руками
    не пишется. Атрибуты таблиц названы как поля доменных моделей, поэтому
    строка превращается в модель через ``model_validate(..., from_attributes=True)``.
    Схемой владеет Alembic (``alembic upgrade head``): адаптер не создаёт таблицы
    и не меняет их структуру, только читает и пишет данные.

    Движок приходит готовым (его собирает контейнер из :class:`SqliteSettings`):
    адаптер не знает ни про путь к файлу БД, ни про драйвер.
    """

    def __init__(self, engine: AsyncEngine) -> None:
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    # ---------- users ----------
    async def upsert_user(self, user_id: int, username: str | None) -> None:
        stmt = sqlite_insert(tables.User).values(id=user_id, username=username)
        async with self._session() as session:
            await session.execute(
                stmt.on_conflict_do_update(
                    index_elements=[tables.User.id],
                    set_={"username": stmt.excluded.username},
                )
            )
            await session.commit()

    async def get_user(self, user_id: int) -> User | None:
        async with self._session() as session:
            row = (
                await session.scalars(
                    select(tables.User).where(tables.User.id == user_id)
                )
            ).one_or_none()
        return None if row is None else User.model_validate(row, from_attributes=True)

    async def set_goal(self, user_id: int, goal: Macros) -> None:
        async with self._session() as session:
            await session.execute(
                update(tables.User)
                .where(tables.User.id == user_id)
                .values(
                    goal_calories=goal.calories,
                    goal_protein=goal.protein,
                    goal_fat=goal.fat,
                    goal_carbs=goal.carbs,
                )
            )
            await session.commit()

    async def set_active_note(self, user_id: int, note_id: int | None) -> None:
        """Запомнить выбранную заметку (None — сбросить выбор)."""
        async with self._session() as session:
            await session.execute(
                update(tables.User)
                .where(tables.User.id == user_id)
                .values(active_note_id=note_id)
            )
            await session.commit()

    # ---------- notes ----------
    async def add_note(self, user_id: int, date: str, label: str) -> NoteInfo:
        async with self._session() as session:
            note_id = await session.scalar(
                insert(tables.Note)
                .values(user_id=user_id, date=date, label=label)
                .returning(tables.Note.id)
            )
            await session.commit()
        assert note_id is not None, "SQLite не вернул id созданной заметки"
        return NoteInfo(id=note_id, user_id=user_id, date=date, label=label)

    async def get_note(self, note_id: int) -> NoteInfo | None:
        async with self._session() as session:
            row = (
                await session.scalars(
                    select(tables.Note).where(tables.Note.id == note_id)
                )
            ).one_or_none()
        return (
            None
            if row is None
            else NoteInfo.model_validate(row, from_attributes=True)
        )

    async def get_last_notes(self, user_id: int, limit: int = 5) -> list[NoteInfo]:
        async with self._session() as session:
            rows = (
                await session.scalars(
                    select(tables.Note)
                    .where(tables.Note.user_id == user_id)
                    .order_by(tables.Note.id.desc())
                    .limit(limit)
                )
            ).all()
        return [NoteInfo.model_validate(row, from_attributes=True) for row in rows]

    async def count_notes(self, user_id: int, date: str) -> int:
        """Сколько заметок пользователя создано на эту дату."""
        async with self._session() as session:
            count = await session.scalar(
                select(func.count())
                .select_from(tables.Note)
                .where(tables.Note.user_id == user_id, tables.Note.date == date)
            )
        return count or 0

    async def delete_note(self, note_id: int) -> None:
        """Удалить заметку вместе с её записями.

        Каскад в SQLite по умолчанию выключен, поэтому записи чистим вручную.
        """
        async with self._session() as session:
            await session.execute(
                delete(tables.Meal).where(tables.Meal.note_id == note_id)
            )
            await session.execute(delete(tables.Note).where(tables.Note.id == note_id))
            await session.commit()

    # ---------- meals ----------
    async def add_meal(self, note_id: int, food: Food) -> None:
        async with self._session() as session:
            await session.execute(
                insert(tables.Meal).values(
                    note_id=note_id,
                    name=food.name,
                    calories=food.calories,
                    protein=food.protein,
                    fat=food.fat,
                    carbs=food.carbs,
                )
            )
            await session.commit()

    async def get_meals(self, note_id: int) -> list[Meal]:
        async with self._session() as session:
            rows = (
                await session.scalars(
                    select(tables.Meal)
                    .where(tables.Meal.note_id == note_id)
                    .order_by(tables.Meal.id)
                )
            ).all()
        return [Meal.model_validate(row, from_attributes=True) for row in rows]

    async def get_meal(self, meal_id: int) -> Meal | None:
        async with self._session() as session:
            row = (
                await session.scalars(
                    select(tables.Meal).where(tables.Meal.id == meal_id)
                )
            ).one_or_none()
        return None if row is None else Meal.model_validate(row, from_attributes=True)

    async def delete_meal(self, meal_id: int) -> None:
        async with self._session() as session:
            await session.execute(delete(tables.Meal).where(tables.Meal.id == meal_id))
            await session.commit()

    async def get_note_totals(self, note_id: int) -> Macros:
        async with self._session() as session:
            row = (
                await session.execute(
                    select(
                        func.coalesce(func.sum(tables.Meal.calories), 0).label(
                            "calories"
                        ),
                        func.coalesce(func.sum(tables.Meal.protein), 0).label(
                            "protein"
                        ),
                        func.coalesce(func.sum(tables.Meal.fat), 0).label("fat"),
                        func.coalesce(func.sum(tables.Meal.carbs), 0).label("carbs"),
                    ).where(tables.Meal.note_id == note_id)
                )
            ).one()
        return Macros(
            calories=float(row.calories),
            protein=float(row.protein),
            fat=float(row.fat),
            carbs=float(row.carbs),
        )

    # ---------- внутренние методы ----------
    @asynccontextmanager
    async def _session(self) -> AsyncGenerator[AsyncSession]:
        """Сессия на время одного запроса: соединение закроет ``NullPool``."""
        async with self._sessions() as session:
            yield session
