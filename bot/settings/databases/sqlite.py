"""Настройки хранилища SQLite."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class SqliteSettings(BaseSettings):
    """Путь к файлу БД и URL подключения для SQLAlchemy.

    Путь задаётся переменной окружения ``DB_PATH`` (см. ``.env``), значение по
    умолчанию — ``data/bot.db``. URL собирается из пути здесь, чтобы адаптер
    получал готовую строку подключения и не знал про драйверы.
    """

    path: Path = Path("data/bot.db")

    @property
    def url(self) -> str:
        """URL для async-движка SQLAlchemy (aiosqlite) — его использует бот."""
        return f"sqlite+aiosqlite:///{self.path.as_posix()}"

    @property
    def sync_url(self) -> str:
        """URL для синхронного движка — его использует Alembic."""
        return f"sqlite:///{self.path.as_posix()}"

    model_config = SettingsConfigDict(
        env_prefix="DB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
