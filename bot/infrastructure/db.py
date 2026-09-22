from __future__ import annotations

from pathlib import Path

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    goal_calories REAL,
    goal_protein REAL,
    goal_fat REAL,
    goal_carbs REAL,
    active_day_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS days (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    day TEXT NOT NULL,
    label TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS meals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day_id INTEGER NOT NULL REFERENCES days(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    weight REAL,
    calories REAL NOT NULL DEFAULT 0,
    protein REAL NOT NULL DEFAULT 0,
    fat REAL NOT NULL DEFAULT 0,
    carbs REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class Database:
    """Адаптер поверх SQLite (aiosqlite)."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._conn: aiosqlite.Connection | None = None

    async def init(self) -> None:
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self._path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA)
        await self._migrate()
        await self._conn.commit()

    async def _migrate(self) -> None:
        """Добавить недостающие колонки в уже существующую БД."""
        await self._add_missing_columns("users", {"active_day_id": "INTEGER"})
        await self._add_missing_columns("meals", {"weight": "REAL"})

    async def _add_missing_columns(self, table: str, columns: dict[str, str]) -> None:
        """Добавить колонки ``columns`` (имя → тип), которых нет в таблице."""
        async with self.conn.execute(f"PRAGMA table_info({table})") as cur:
            existing = {row["name"] for row in await cur.fetchall()}
        for name, column_type in columns.items():
            if name not in existing:
                await self.conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN {name} {column_type}"
                )

    async def shutdown(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

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

    async def get_user(self, user_id: int) -> aiosqlite.Row | None:
        async with self.conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cur:
            return await cur.fetchone()

    async def set_goal(
        self,
        user_id: int,
        calories: float,
        protein: float,
        fat: float,
        carbs: float,
    ) -> None:
        await self.conn.execute(
            "UPDATE users SET goal_calories = ?, goal_protein = ?, "
            "goal_fat = ?, goal_carbs = ? WHERE user_id = ?",
            (calories, protein, fat, carbs, user_id),
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
    async def _count_days_on(self, user_id: int, day: str) -> int:
        async with self.conn.execute(
            "SELECT COUNT(*) AS c FROM days WHERE user_id = ? AND day = ?",
            (user_id, day),
        ) as cur:
            row = await cur.fetchone()
        return int(row["c"])

    async def create_day(self, user_id: int, day: str) -> int:
        count = await self._count_days_on(user_id, day)
        label = day if count == 0 else f"{day} ({count + 1})"
        cur = await self.conn.execute(
            "INSERT INTO days (user_id, day, label) VALUES (?, ?, ?)",
            (user_id, day, label),
        )
        await self.conn.commit()
        return int(cur.lastrowid)

    async def get_latest_day_id(self, user_id: int) -> int | None:
        async with self.conn.execute(
            "SELECT id FROM days WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
        return int(row["id"]) if row is not None else None

    async def get_target_day(self, user_id: int, day: str) -> int:
        """День для добавления продуктов: выбранный в истории или последний.

        Если дней нет совсем, создаёт новый.
        """
        found = await self.find_target_day(user_id)
        if found is not None:
            return found
        return await self.create_day(user_id, day)

    async def find_target_day(self, user_id: int) -> int | None:
        """День для добавления продуктов, не создавая его."""
        user = await self.get_user(user_id)
        if user is not None and user["active_day_id"] is not None:
            selected = await self.get_day(int(user["active_day_id"]))
            if selected is not None and int(selected["user_id"]) == user_id:
                return int(selected["id"])
        return await self.get_latest_day_id(user_id)

    async def get_day(self, day_id: int) -> aiosqlite.Row | None:
        async with self.conn.execute(
            "SELECT * FROM days WHERE id = ?", (day_id,)
        ) as cur:
            return await cur.fetchone()

    async def get_last_days(self, user_id: int, limit: int = 5) -> list[aiosqlite.Row]:
        async with self.conn.execute(
            "SELECT * FROM days WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ) as cur:
            return list(await cur.fetchall())

    async def delete_day(self, day_id: int) -> None:
        """Удалить день вместе с его записями.

        Каскад в SQLite по умолчанию выключен, поэтому записи чистим вручную.
        """
        await self.conn.execute("DELETE FROM meals WHERE day_id = ?", (day_id,))
        await self.conn.execute("DELETE FROM days WHERE id = ?", (day_id,))
        await self.conn.commit()

    # ---------- meals ----------
    async def add_meal(
        self,
        day_id: int,
        name: str,
        calories: float,
        protein: float,
        fat: float,
        carbs: float,
        weight: float | None = None,
    ) -> None:
        await self.conn.execute(
            "INSERT INTO meals (day_id, name, weight, calories, protein, fat, carbs) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (day_id, name, weight, calories, protein, fat, carbs),
        )
        await self.conn.commit()

    async def update_meal(
        self,
        meal_id: int,
        name: str,
        calories: float,
        protein: float,
        fat: float,
        carbs: float,
        weight: float | None,
    ) -> None:
        """Перезаписать запись: повтор блюда обновляет её, а не дублирует."""
        await self.conn.execute(
            "UPDATE meals SET name = ?, weight = ?, calories = ?, protein = ?, "
            "fat = ?, carbs = ? WHERE id = ?",
            (name, weight, calories, protein, fat, carbs, meal_id),
        )
        await self.conn.commit()

    async def get_meals(self, day_id: int) -> list[aiosqlite.Row]:
        async with self.conn.execute(
            "SELECT * FROM meals WHERE day_id = ? ORDER BY id", (day_id,)
        ) as cur:
            return list(await cur.fetchall())

    async def get_meal(self, meal_id: int) -> aiosqlite.Row | None:
        async with self.conn.execute(
            "SELECT * FROM meals WHERE id = ?", (meal_id,)
        ) as cur:
            return await cur.fetchone()

    async def delete_meal(self, meal_id: int) -> None:
        await self.conn.execute("DELETE FROM meals WHERE id = ?", (meal_id,))
        await self.conn.commit()

    async def get_day_totals(self, day_id: int) -> dict[str, float]:
        async with self.conn.execute(
            "SELECT COALESCE(SUM(calories), 0) AS calories, "
            "COALESCE(SUM(protein), 0) AS protein, "
            "COALESCE(SUM(fat), 0) AS fat, "
            "COALESCE(SUM(carbs), 0) AS carbs "
            "FROM meals WHERE day_id = ?",
            (day_id,),
        ) as cur:
            row = await cur.fetchone()
        return {
            "calories": float(row["calories"]),
            "protein": float(row["protein"]),
            "fat": float(row["fat"]),
            "carbs": float(row["carbs"]),
        }
