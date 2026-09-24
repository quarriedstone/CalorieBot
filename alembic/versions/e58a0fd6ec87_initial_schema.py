"""initial schema: users, days, meals

Миграция идемпотентна: на уже развёрнутой БД (до Alembic) она только
создаёт недостающие таблицы и добивает колонку users.active_day_id.

Revision ID: e58a0fd6ec87
Revises:
Create Date: 2026-09-24 23:43:38.480586

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e58a0fd6ec87"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    goal_calories REAL,
    goal_protein REAL,
    goal_fat REAL,
    goal_carbs REAL,
    active_day_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)
"""

DAYS_TABLE = """
CREATE TABLE IF NOT EXISTS days (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    day TEXT NOT NULL,
    label TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)
"""

MEALS_TABLE = """
CREATE TABLE IF NOT EXISTS meals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day_id INTEGER NOT NULL REFERENCES days(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    calories REAL NOT NULL DEFAULT 0,
    protein REAL NOT NULL DEFAULT 0,
    fat REAL NOT NULL DEFAULT 0,
    carbs REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)
"""


def _column_names(table: str) -> set[str]:
    """Имена колонок таблицы через PRAGMA (пустое множество, если таблицы нет)."""
    rows = op.get_bind().execute(sa.text(f"PRAGMA table_info({table})")).fetchall()
    return {str(row[1]) for row in rows}


def upgrade() -> None:
    """Создать схему; на старой БД добить колонку active_day_id."""
    op.execute(USERS_TABLE)
    op.execute(DAYS_TABLE)
    op.execute(MEALS_TABLE)
    if "active_day_id" not in _column_names("users"):
        op.execute("ALTER TABLE users ADD COLUMN active_day_id INTEGER")


def downgrade() -> None:
    """Удалить схему (порядок обратный из-за ссылок)."""
    op.execute("DROP TABLE IF EXISTS meals")
    op.execute("DROP TABLE IF EXISTS days")
    op.execute("DROP TABLE IF EXISTS users")
