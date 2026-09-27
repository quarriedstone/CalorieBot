from __future__ import annotations

from dependency_injector import containers, providers
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from bot.domain.services import FoodService, NoteService, UserService
from bot.infrastructure.adapters.database import DatabaseAdapter
from bot.infrastructure.adapters.deepseek import DeepSeekAdapter
from bot.settings import AppSettings, DeepSeekSettings, SqliteSettings


class AppContainer(containers.DeclarativeContainer):
    """Композиция зависимостей: настройки, адаптеры и сервисы."""

    app_settings = providers.Singleton(AppSettings)
    sqlite_settings = providers.Singleton(SqliteSettings)
    deepseek_settings = providers.Singleton(DeepSeekSettings)

    # Движок без пула соединений: каждый запрос адаптера открывает своё соединение
    # и закрывает его на выходе, поэтому закрывать движок при остановке не нужно.
    sqlite_engine = providers.Singleton(
        create_async_engine, sqlite_settings.provided.url, poolclass=NullPool
    )

    database_adapter = providers.Singleton(DatabaseAdapter, engine=sqlite_engine)
    deepseek_adapter = providers.Singleton(
        DeepSeekAdapter,
        api_key=deepseek_settings.provided.api_key,
        base_url=deepseek_settings.provided.base_url,
        model=deepseek_settings.provided.model,
    )

    user_service = providers.Singleton(UserService, db=database_adapter)
    note_service = providers.Singleton(
        NoteService, db=database_adapter, users=user_service
    )
    food_service = providers.Singleton(
        FoodService,
        db=database_adapter,
        deepseek=deepseek_adapter,
        notes=note_service,
    )
