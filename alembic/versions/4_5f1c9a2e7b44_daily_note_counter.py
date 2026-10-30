"""daily note counter

Добавляет в ``users`` счётчик созданных за сутки заметок: ``notes_day`` —
дата (ISO), к которой относится счётчик, и ``notes_created`` — сколько
заметок создано в эту дату. Удаление заметки счётчик не уменьшает, поэтому
лимит бесплатного тарифа нельзя обойти циклом «создать → удалить».

Revision ID: 5f1c9a2e7b44
Revises: ca71c166eee9
Create Date: 2026-10-30 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5f1c9a2e7b44"
down_revision: Union[str, Sequence[str], None] = "ca71c166eee9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("notes_day", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "notes_created",
                sa.Integer(),
                server_default=sa.text("0"),
                nullable=False,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("notes_created")
        batch_op.drop_column("notes_day")
