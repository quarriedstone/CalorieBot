"""Общие настройки приложения."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Настройки бота (переменные окружения ``BOT_TOKEN`` и ``ADMIN_IDS``).

    ``admin_ids`` — Telegram ID через запятую: только им доступны служебные
    команды вроде ``/grant``. Пустая строка — админов нет.
    """

    bot_token: str
    admin_ids: str = ""

    @property
    def admin_id_set(self) -> set[int]:
        """ID администраторов без пустых и нечисловых значений."""
        result: set[int] = set()
        for chunk in self.admin_ids.split(","):
            chunk = chunk.strip()
            if chunk.isdigit():
                result.add(int(chunk))
        return result

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
