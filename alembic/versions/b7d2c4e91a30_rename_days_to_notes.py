"""rename days to notes

Сущность «день» переименована в «заметку» и на уровне схемы: таблица
``days`` → ``notes``, колонка ``days.day`` → ``notes.date``,
``meals.day_id`` → ``meals.note_id``, ``users.active_day_id`` →
``users.active_note_id``.

SQLite умеет переименовывать таблицы и колонки на месте (``ALTER TABLE ...
RENAME TO/COLUMN``, SQLite 3.25+), поэтому данные, автоинкремент и внешний
ключ ``meals.note_id`` сохраняются без пересоздания таблиц.

Revision ID: b7d2c4e91a30
Revises: e58a0fd6ec87
Create Date: 2026-09-27 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7d2c4e91a30"
down_revision: Union[str, Sequence[str], None] = "e58a0fd6ec87"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("days", "notes")
    op.execute("ALTER TABLE notes RENAME COLUMN day TO date")
    op.execute("ALTER TABLE meals RENAME COLUMN day_id TO note_id")
    op.execute("ALTER TABLE users RENAME COLUMN active_day_id TO active_note_id")


def downgrade() -> None:
    op.execute("ALTER TABLE users RENAME COLUMN active_note_id TO active_day_id")
    op.execute("ALTER TABLE meals RENAME COLUMN note_id TO day_id")
    op.execute("ALTER TABLE notes RENAME COLUMN date TO day")
    op.rename_table("notes", "days")
