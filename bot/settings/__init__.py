"""Настройки приложения, сгруппированные по подсистемам."""

from bot.settings.app import AppSettings
from bot.settings.databases import SqliteSettings
from bot.settings.deepseek import DeepSeekSettings
from bot.settings.payments import PaymentsSettings

__all__ = [
    "AppSettings",
    "DeepSeekSettings",
    "PaymentsSettings",
    "SqliteSettings",
]
