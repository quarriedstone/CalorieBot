"""initial schema: users, days, meals

Схема описана через SQLAlchemy (`op.create_table`). Миграция терпима к БД,
созданной до Alembic (старым кодом приложения): существующие таблицы она
не трогает, а колонку `users.active_day_id` добавляет, если её нет.

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

CREATED_AT_DEFAULT = sa.text("(datetime('now'))")
ZERO_DEFAULT = sa.text("0")


def _existing_tables() -> set[str]:
    """Имена таблиц, которые уже есть в БД."""
    return set(sa.inspect(op.get_bind()).get_table_names())


def _column_names(table: str) -> set[str]:
    """Имена колонок таблицы (пустое множество, если таблицы нет)."""
    inspector = sa.inspect(op.get_bind())
    if table not in set(inspector.get_table_names()):
        return set()
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade() -> None:
    """Создать схему; на БД от старого кода — только добавить active_day_id."""
    tables = _existing_tables()

    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("user_id", sa.Integer(), primary_key=True),
            sa.Column("username", sa.Text(), nullable=True),
            sa.Column("goal_calories", sa.REAL(), nullable=True),
            sa.Column("goal_protein", sa.REAL(), nullable=True),
            sa.Column("goal_fat", sa.REAL(), nullable=True),
            sa.Column("goal_carbs", sa.REAL(), nullable=True),
            sa.Column("active_day_id", sa.Integer(), nullable=True),
            sa.Column(
                "created_at",
                sa.Text(),
                nullable=False,
                server_default=CREATED_AT_DEFAULT,
            ),
        )
    elif "active_day_id" not in _column_names("users"):
        op.add_column(
            "users", sa.Column("active_day_id", sa.Integer(), nullable=True)
        )

    if "days" not in tables:
        op.create_table(
            "days",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("day", sa.Text(), nullable=False),
            sa.Column("label", sa.Text(), nullable=False),
            sa.Column(
                "created_at",
                sa.Text(),
                nullable=False,
                server_default=CREATED_AT_DEFAULT,
            ),
            sqlite_autoincrement=True,
        )

    if "meals" not in tables:
        op.create_table(
            "meals",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "day_id",
                sa.Integer(),
                sa.ForeignKey("days.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column(
                "calories", sa.REAL(), nullable=False, server_default=ZERO_DEFAULT
            ),
            sa.Column(
                "protein", sa.REAL(), nullable=False, server_default=ZERO_DEFAULT
            ),
            sa.Column("fat", sa.REAL(), nullable=False, server_default=ZERO_DEFAULT),
            sa.Column(
                "carbs", sa.REAL(), nullable=False, server_default=ZERO_DEFAULT
            ),
            sa.Column(
                "created_at",
                sa.Text(),
                nullable=False,
                server_default=CREATED_AT_DEFAULT,
            ),
            sqlite_autoincrement=True,
        )


def downgrade() -> None:
    """Удалить схему (порядок обратный из-за ссылок)."""
    op.drop_table("meals")
    op.drop_table("days")
    op.drop_table("users")
