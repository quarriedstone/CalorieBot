"""Настройки подписки и приёма платежей."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class PaymentsSettings(BaseSettings):
    """Параметры подписки и лимитов бесплатного тарифа.

    Переменные окружения — ``PAYMENTS_*`` (см. ``.env``); значения по умолчанию
    подходят для Telegram Stars: 150 звёзд за 30 дней, досрочная выдача
    администратору — на 3650 дней (≈10 лет).

    ``provider_token`` для звёзд не нужен (передаётся пустой строкой) и оставлен
    на случай подключения фиатного провайдера.
    """

    currency: str = "XTR"
    price: int = 150
    days: int = 30
    grant_days: int = 3650
    provider_token: str = ""
    title: str = "CalorieBot Premium"
    description: str = (
        "Без лимитов: любые заметки и записи о еде в течение срока подписки."
    )
    free_notes: int = 3
    free_meals: int = 10

    model_config = SettingsConfigDict(
        env_prefix="PAYMENTS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
