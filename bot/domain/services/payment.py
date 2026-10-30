"""Сервис подписки: счета Telegram Stars, продление и лимиты тарифа."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from bot.domain.models import Payment
from bot.domain.services.interfaces import DatabaseInterface

__all__ = ["PaymentService"]

STATUS_PENDING = "pending"
STATUS_PAID = "paid"


class PaymentService:
    """Платежи, подписка и ограничения бесплатного тарифа.

    Подписка — это дата окончания в :attr:`bot.domain.models.User.paid_until`:
    и оплата звёздами, и ручная выдача администратором продлевают её на число
    дней, отдельного «пожизненного» режима нет.
    """

    def __init__(
        self,
        db: DatabaseInterface,
        free_notes: int = 3,  # заметок в сутки
        free_meals: int = 10,
        grant_days: int = 3650,
    ) -> None:
        self._db = db
        self.free_notes = free_notes
        self.free_meals = free_meals
        self.grant_days = grant_days

    async def start(
        self, user_id: int, amount: int, currency: str, days: int
    ) -> Payment:
        """Создать ожидающий счёт на подписку.

        ``payload`` счёта вернётся из Telegram в ``pre_checkout_query``
        и ``successful_payment`` — по нему находится запись в хранилище.
        """
        return await self._db.add_payment(
            user_id, uuid4().hex, amount, currency, days
        )

    async def check_precheckout(
        self, user_id: int, payload: str, amount: int, currency: str
    ) -> tuple[bool, str]:
        """Можно ли принять оплату по этому счёту.

        Возвращает признак «можно» и текст ошибки для Telegram. Цена сверяется
        с сохранённым счётом, а не с данными, пришедшими от клиента.
        """
        payment = await self._db.get_payment_by_payload(payload)
        if payment is None or payment.user_id != user_id:
            return False, "Счёт не найден."
        if payment.status != STATUS_PENDING:
            return False, "Счёт уже оплачен."
        if payment.amount != amount or payment.currency != currency:
            return False, "Сумма счёта не совпадает."
        return True, ""

    async def confirm(
        self,
        user_id: int,
        payload: str,
        telegram_charge_id: str,
        provider_charge_id: str | None = None,
    ) -> str | None:
        """Зафиксировать оплату и продлить подписку.

        Возвращает новое время окончания подписки или ``None``, если счёт
        не найден, принадлежит другому пользователю или уже оплачен —
        повторная доставка ``successful_payment`` доступ не удваивает.
        """
        payment = await self._db.get_payment_by_payload(payload)
        if payment is None or payment.user_id != user_id:
            return None
        paid = await self._db.mark_payment_paid(
            payment.id, telegram_charge_id, provider_charge_id
        )
        if not paid:
            return None
        return await self._extend(user_id, payment.days)

    async def grant(self, user_id: int, days: int | None = None) -> str:
        """Выдать подписку вручную и вернуть новое время окончания.

        По умолчанию — на :attr:`grant_days` дней (3650 ≈ 10 лет).
        """
        return await self._extend(user_id, self.grant_days if days is None else days)

    async def revoke(self, user_id: int) -> None:
        """Снять подписку."""
        await self._db.set_paid_until(user_id, None)

    async def paid_until(self, user_id: int) -> str | None:
        """ISO-время окончания подписки или ``None``, если её нет."""
        user = await self._db.get_user(user_id)
        return None if user is None else user.paid_until

    async def is_subscribed(self, user_id: int) -> bool:
        """Активна ли подписка прямо сейчас."""
        until = self._parse(await self.paid_until(user_id))
        return until is not None and until > self._now()

    async def can_create_note(self, user_id: int) -> bool:
        """Можно ли создать ещё одну заметку сегодня (подписка снимает лимит).

        Считаются все заметки, созданные за сутки, в том числе удалённые:
        иначе лимит обходится циклом «создать → удалить».
        """
        if await self.is_subscribed(user_id):
            return True
        user = await self._db.get_user(user_id)
        created = 0 if user is None else user.notes_created_on(self._today())
        return created < self.free_notes

    async def can_add_meal(self, user_id: int, note_id: int) -> bool:
        """Можно ли добавить запись в заметку (подписка снимает лимит)."""
        if await self.is_subscribed(user_id):
            return True
        return await self._db.count_meals(note_id) < self.free_meals

    # ---------- внутренние методы ----------
    async def _extend(self, user_id: int, days: int) -> str:
        """Продлить подписку на ``days`` дней от максимума из «сейчас» и срока."""
        current = self._parse(await self.paid_until(user_id))
        start = self._now()
        if current is not None and current > start:
            start = current
        paid_until = (start + timedelta(days=days)).isoformat(timespec="seconds")
        await self._db.set_paid_until(user_id, paid_until)
        return paid_until

    @staticmethod
    def _parse(value: str | None) -> datetime | None:
        """Разобрать сохранённое время окончания подписки."""
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)

    @staticmethod
    def _today() -> str:
        """Сегодняшняя дата в формате ISO — как у заметок."""
        return date.today().isoformat()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)
