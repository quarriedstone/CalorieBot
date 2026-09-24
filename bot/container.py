from __future__ import annotations

from dependency_injector import containers, providers

from bot.config import settings
from bot.domain.services import DayService, FoodService, UserService
from bot.infrastructure.adapters.databases.sqlite import SqliteAdapter
from bot.infrastructure.adapters.deepseek import DeepSeekAdapter


class AppContainer(containers.DeclarativeContainer):
    """Композиция зависимостей: адаптеры и сервисы."""

    sqlite_adapter = providers.Singleton(SqliteAdapter, settings.db_path)
    deepseek_adapter = providers.Singleton(
        DeepSeekAdapter,
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
    )

    user_service = providers.Singleton(UserService, db=sqlite_adapter)
    day_service = providers.Singleton(DayService, db=sqlite_adapter, users=user_service)
    food_service = providers.Singleton(FoodService, db=sqlite_adapter, deepseek=deepseek_adapter)
