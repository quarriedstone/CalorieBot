"""Настройки DeepSeek API."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class DeepSeekSettings(BaseSettings):
    """Ключ, адрес и модель DeepSeek (Responses API).

    Переменные окружения — ``DEEPSEEK_API_KEY``, ``DEEPSEEK_BASE_URL``,
    ``DEEPSEEK_MODEL`` (см. ``.env``); обязателен только ключ.
    """

    api_key: str
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-flash"

    model_config = SettingsConfigDict(
        env_prefix="DEEPSEEK_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
