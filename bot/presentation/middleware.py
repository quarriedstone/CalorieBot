from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from bot.container import AppContainer


class ContainerMiddleware(BaseMiddleware):
    """Кладёт сервисы из контейнера в ``data`` каждого апдейта."""

    def __init__(self, container: AppContainer) -> None:
        self._user_service = container.user_service()
        self._day_service = container.day_service()
        self._food_service = container.food_service()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["user_service"] = self._user_service
        data["day_service"] = self._day_service
        data["food_service"] = self._food_service
        return await handler(event, data)
