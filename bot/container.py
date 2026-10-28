from __future__ import annotations

from dependency_injector import containers, providers
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from bot.domain.services import (
    FoodService,
    NoteService,
    PaymentService,
    UserService,
)
from bot.infrastructure.adapters.database import DatabaseAdapter
from bot.infrastructure.adapters.deepseek import DeepSeekAdapter
from bot.settings import (
    AppSettings,
    DeepSeekSettings,
    PaymentsSettings,
    SqliteSettings,
)


class AppContainer(containers.DeclarativeContainer):
    """Композиция зависимостей: настройки, адаптеры и сервисы."""

    app_settings = providers.Singleton(AppSettings)
    sqlite_settings = providers.Singleton(SqliteSettings)
    deepseek_settings = providers.Singleton(DeepSeekSettings)
    payments_settings = providers.Singleton(PaymentsSettings)

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
    payment_service = providers.Singleton(
        PaymentService,
        db=database_adapter,
        free_notes=payments_settings.provided.free_notes,
        free_meals=payments_settings.provided.free_meals,
        grant_days=payments_settings.provided.grant_days,
    )
