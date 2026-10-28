"""Таблица ``payments``."""

from __future__ import annotations

from sqlalchemy import Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from bot.infrastructure.models.base import Base


class Payment(Base):
    """Счёт на подписку и результат его оплаты.

    Атрибуты названы как поля доменной модели :class:`bot.domain.models.Payment`,
    поэтому строка БД превращается в неё без ручного маппинга.

    ``payload`` уникален — это метка счёта, которая возвращается из Telegram
    в ``pre_checkout_query``. ``telegram_charge_id`` тоже уникален: повторная
    доставка ``successful_payment`` не должна выдавать доступ дважды (SQLite
    разрешает несколько ``NULL`` в уникальной колонке).
    """

    __tablename__ = "payments"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column()
    payload: Mapped[str] = mapped_column(Text(), unique=True)
    amount: Mapped[int] = mapped_column(Integer())
    currency: Mapped[str] = mapped_column(Text())
    days: Mapped[int] = mapped_column(Integer())
    status: Mapped[str] = mapped_column(Text(), server_default=text("'pending'"))
    telegram_charge_id: Mapped[str | None] = mapped_column(Text(), unique=True)
    provider_charge_id: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[str] = mapped_column(
        Text(), server_default=text("(datetime('now'))")
    )
    paid_at: Mapped[str | None] = mapped_column(Text())


__all__ = ["Payment"]
