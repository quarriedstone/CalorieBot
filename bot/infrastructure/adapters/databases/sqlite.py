from __future__ import annotations

from pathlib import Path
from types import TracebackType
from typing import Self

import aiosqlite

from bot.domain.models import DayInfo, Food, Macros, Meal, User
from bot.domain.services.interfaces import DatabaseInterface


class SqliteAdapter(DatabaseInterface):
    """Адаптер поверх SQLite (aiosqlite), реализует :class:`DatabaseInterface`.

    Соединение открывается на входе в контекстный менеджер и закрывается на выходе::

        async with container.sqlite_adapter() as db:
            ...

    Схемой владеет Alembic (``alembic upgrade head``): адаптер не создаёт таблицы
    и не меняет их структуру, только читает и пишет данные.
    """

    def __init__(self, path: str) -> None:
        self._path = path
        self._conn: aiosqlite.Connection | None = None

    # ---------- жизненный цикл ----------
    async def __aenter__(self) -> Self:
        """Открыть соединение и убедиться, что БД мигрирована."""
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self._path)
        self._conn.row_factory = aiosqlite.Row
        await self._check_migrated()
        return self

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _tb: TracebackType | None,
    ) -> None:
        await self._close()

    @property
    def conn(self) -> aiosqlite.Connection:
        assert self._conn is not None, "Database is not connected"
        return self._conn

    # ---------- users ----------
    async def upsert_user(self, user_id: int, username: str | None) -> None:
        await self.conn.execute(
            "INSERT INTO users (user_id, username) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET username = excluded.username",
            (user_id, username),
        )
        await self.conn.commit()

    async def get_user(self, user_id: int) -> User | None:
        async with self.conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
        return None if row is None else self._user_from_row(row)

    async def set_goal(self, user_id: int, goal: Macros) -> None:
        await self.conn.execute(
            "UPDATE users SET goal_calories = ?, goal_protein = ?, "
            "goal_fat = ?, goal_carbs = ? WHERE user_id = ?",
            (goal.calories, goal.protein, goal.fat, goal.carbs, user_id),
        )
        await self.conn.commit()

    async def set_active_day(self, user_id: int, day_id: int | None) -> None:
        """Запомнить день для добавления продуктов (None — последний день)."""
        await self.conn.execute(
            "UPDATE users SET active_day_id = ? WHERE user_id = ?", (day_id, user_id)
        )
        await self.conn.commit()

    async def clear_active_day(self, user_id: int) -> None:
        await self.set_active_day(user_id, None)

    # ---------- days ----------
    async def create_day(self, user_id: int, day: str) -> DayInfo:
        count = await self._count_days_on(user_id, day)
        label = day if count == 0 else f"{day} ({count + 1})"
        cur = await self.conn.execute(
            "INSERT INTO days (user_id, day, label) VALUES (?, ?, ?)",
            (user_id, day, label),
        )
        await self.conn.commit()
        assert cur.lastrowid is not None, "SQLite не вернул id созданного дня"
        return DayInfo(id=int(cur.lastrowid), user_id=user_id, date=day, label=label)

    async def get_latest_day_id(self, user_id: int) -> int | None:
        async with self.conn.execute(
            "SELECT id FROM days WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
        return int(row["id"]) if row is not None else None

    async def get_target_day(self, user_id: int, day: str) -> DayInfo:
        """День для добавления продуктов: выбранный в истории или последний."""
        user = await self.get_user(user_id)
        if user is not None and user.active_day_id is not None:
            selected = await self.get_day(user.active_day_id)
            if selected is not None and selected.user_id == user_id:
                return selected
        return await self._get_current_day(user_id, day)

    async def get_day(self, day_id: int) -> DayInfo | None:
        async with self.conn.execute(
            "SELECT * FROM days WHERE id = ?", (day_id,)
        ) as cur:
            row = await cur.fetchone()
        return None if row is None else self._day_from_row(row)

    async def get_last_days(self, user_id: int, limit: int = 5) -> list[DayInfo]:
        async with self.conn.execute(
            "SELECT * FROM days WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ) as cur:
            return [self._day_from_row(row) for row in await cur.fetchall()]

    async def delete_day(self, day_id: int) -> None:
        """Удалить день вместе с его записями.

        Каскад в SQLite по умолчанию выключен, поэтому записи чистим вручную.
        """
        await self.conn.execute("DELETE FROM meals WHERE day_id = ?", (day_id,))
        await self.conn.execute("DELETE FROM days WHERE id = ?", (day_id,))
        await self.conn.commit()

    # ---------- meals ----------
    async def add_meal(self, day_id: int, food: Food) -> None:
        await self.conn.execute(
            "INSERT INTO meals (day_id, name, calories, protein, fat, carbs) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (day_id, food.name, food.calories, food.protein, food.fat, food.carbs),
        )
        await self.conn.commit()

    async def get_meals(self, day_id: int) -> list[Meal]:
        async with self.conn.execute(
            "SELECT * FROM meals WHERE day_id = ? ORDER BY id", (day_id,)
        ) as cur:
            return [self._meal_from_row(row) for row in await cur.fetchall()]

    async def get_meal(self, meal_id: int) -> Meal | None:
        async with self.conn.execute(
            "SELECT * FROM meals WHERE id = ?", (meal_id,)
        ) as cur:
            row = await cur.fetchone()
        return None if row is None else self._meal_from_row(row)

    async def delete_meal(self, meal_id: int) -> None:
        await self.conn.execute("DELETE FROM meals WHERE id = ?", (meal_id,))
        await self.conn.commit()

    async def get_day_totals(self, day_id: int) -> Macros:
        async with self.conn.execute(
            "SELECT COALESCE(SUM(calories), 0) AS calories, "
            "COALESCE(SUM(protein), 0) AS protein, "
            "COALESCE(SUM(fat), 0) AS fat, "
            "COALESCE(SUM(carbs), 0) AS carbs "
            "FROM meals WHERE day_id = ?",
            (day_id,),
        ) as cur:
            row = await cur.fetchone()
        assert row is not None, "SUM() не вернул строку"
        return Macros(
            calories=float(row["calories"]),
            protein=float(row["protein"]),
            fat=float(row["fat"]),
            carbs=float(row["carbs"]),
        )

    # ---------- внутренние методы ----------
    async def _close(self) -> None:
        """Закрыть соединение. Вызывается выходом из ``async with``."""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def _check_migrated(self) -> None:
        """Проверить, что схему накатил Alembic, иначе — понятная ошибка."""
        async with self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            ("alembic_version",),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            raise RuntimeError(
                f"База {self._path} не мигрирована: "
                "выполните `alembic upgrade head`"
            )

    async def _count_days_on(self, user_id: int, day: str) -> int:
        """Сколько дней пользователя уже заведено на эту дату."""
        async with self.conn.execute(
            "SELECT COUNT(*) AS c FROM days WHERE user_id = ? AND day = ?",
            (user_id, day),
        ) as cur:
            row = await cur.fetchone()
        assert row is not None, "COUNT(*) не вернул строку"
        return int(row["c"])

    async def _get_current_day(self, user_id: int, day: str) -> DayInfo:
        """Последний день пользователя или новый, если дней ещё нет."""
        latest = await self.get_latest_day_id(user_id)
        if latest is None:
            return await self.create_day(user_id, day)
        current = await self.get_day(latest)
        assert current is not None, "Последний день не найден в БД"
        return current

    @staticmethod
    def _user_from_row(row: aiosqlite.Row) -> User:
        goal = (
            None
            if row["goal_calories"] is None
            else Macros(
                calories=float(row["goal_calories"]),
                protein=float(row["goal_protein"] or 0),
                fat=float(row["goal_fat"] or 0),
                carbs=float(row["goal_carbs"] or 0),
            )
        )
        return User(
            id=int(row["user_id"]),
            username=row["username"],
            goal=goal,
            active_day_id=(
                None if row["active_day_id"] is None else int(row["active_day_id"])
            ),
        )

    @staticmethod
    def _day_from_row(row: aiosqlite.Row) -> DayInfo:
        return DayInfo(
            id=int(row["id"]),
            user_id=int(row["user_id"]),
            date=str(row["day"]),
            label=str(row["label"]),
        )

    @staticmethod
    def _meal_from_row(row: aiosqlite.Row) -> Meal:
        return Meal(
            id=int(row["id"]),
            day_id=int(row["day_id"]),
            name=str(row["name"]),
            calories=float(row["calories"]),
            protein=float(row["protein"]),
            fat=float(row["fat"]),
            carbs=float(row["carbs"]),
        )
