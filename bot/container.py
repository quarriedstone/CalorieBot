from __future__ import annotations

from dependency_injector import containers, providers

from bot.config import settings
from bot.domain.services import DayService, FoodService, UserService
from bot.infrastructure.db import Database
from bot.infrastructure.deepseek import DeepSeekParser


class AppContainer(containers.DeclarativeContainer):
    """Композиция зависимостей: адаптеры и сервисы."""

    db_path = providers.Singleton(Database, settings.db_path)
    deepseek_adapter = providers.Singleton(
        DeepSeekParser,
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
    )

    user_service = providers.Singleton(UserService, db=db_path)
    day_service = providers.Singleton(DayService, db=db_path, users=user_service)
    food_service = providers.Singleton(FoodService, db=db_path, deepseek=deepseek_adapter)
