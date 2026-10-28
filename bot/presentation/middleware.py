from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from bot.container import AppContainer
from bot.settings import PaymentsSettings


class ContainerMiddleware(BaseMiddleware):
    """Кладёт сервисы и настройки из контейнера в ``data`` каждого апдейта."""

    def __init__(self, container: AppContainer) -> None:
        self._user_service = container.user_service()
        self._note_service = container.note_service()
        self._food_service = container.food_service()
        self._payment_service = container.payment_service()
        self._payments_settings: PaymentsSettings = container.payments_settings()
        self._admin_ids = container.app_settings().admin_id_set

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["user_service"] = self._user_service
        data["note_service"] = self._note_service
        data["food_service"] = self._food_service
        data["payment_service"] = self._payment_service
        data["payments_settings"] = self._payments_settings
        data["admin_ids"] = self._admin_ids
        return await handler(event, data)
