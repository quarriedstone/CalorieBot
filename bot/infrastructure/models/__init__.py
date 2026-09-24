"""SQLAlchemy-модели таблиц.

Модели описывают схему БД для Alembic: его ``env.py`` берёт отсюда
``Base.metadata`` (в том числе для autogenerate).
"""

from __future__ import annotations

from bot.infrastructure.models.base import Base
from bot.infrastructure.models.day import Day
from bot.infrastructure.models.meal import Meal
from bot.infrastructure.models.user import User

__all__ = ["Base", "Day", "Meal", "User"]
