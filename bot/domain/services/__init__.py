"""Доменные сервисы: пользователь, заметки, блюда и подписка.

Реализации разложены по модулям (один сервис — один файл), а порты хранилища
живут в подпакете :mod:`bot.domain.services.interfaces`.
"""

from __future__ import annotations

from bot.domain.services.food import FoodNotFoundError, FoodService
from bot.domain.services.note import NoteService
from bot.domain.services.payment import PaymentService
from bot.domain.services.user import UserService

__all__ = [
    "FoodNotFoundError",
    "FoodService",
    "NoteService",
    "PaymentService",
    "UserService",
]
