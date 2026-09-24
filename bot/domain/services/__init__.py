"""Доменные сервисы: пользователь, дни и блюда.

Реализации разложены по модулям (один сервис — один файл), а порты хранилища
живут в подпакете :mod:`bot.domain.services.interfaces`.
"""

from __future__ import annotations

from bot.domain.services.day import DayService
from bot.domain.services.food import FoodNotFoundError, FoodService
from bot.domain.services.user import UserService

__all__ = [
    "DayService",
    "FoodNotFoundError",
    "FoodService",
    "UserService",
]
