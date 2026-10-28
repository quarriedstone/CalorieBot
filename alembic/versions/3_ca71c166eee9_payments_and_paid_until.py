"""payments and paid_until

Добавляет учёт подписок: таблицу ``payments`` со счетами Telegram Stars
и колонку ``users.paid_until`` — ISO-время окончания подписки (UTC).

``payments.payload`` и ``payments.telegram_charge_id`` уникальны: первый
защищает от повторного подтверждения своего же счёта, второй — от выдачи
доступа дважды при повторной доставке ``successful_payment``.

Revision ID: ca71c166eee9
Revises: b7d2c4e91a30
Create Date: 2026-10-28 22:29:23.420573

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ca71c166eee9"
down_revision: Union[str, Sequence[str], None] = "b7d2c4e91a30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column(
            "status", sa.Text(), server_default=sa.text("'pending'"), nullable=False
        ),
        sa.Column("telegram_charge_id", sa.Text(), nullable=True),
        sa.Column("provider_charge_id", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.Text(),
            server_default=sa.text("(datetime('now'))"),
            nullable=False,
        ),
        sa.Column("paid_at", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payload"),
        sa.UniqueConstraint("telegram_charge_id"),
        sqlite_autoincrement=True,
    )
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("paid_until", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("paid_until")

    op.drop_table("payments")
