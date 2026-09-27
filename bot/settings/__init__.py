"""Настройки приложения, сгруппированные по подсистемам."""

from bot.settings.app import AppSettings
from bot.settings.databases import SqliteSettings
from bot.settings.deepseek import DeepSeekSettings

__all__ = ["AppSettings", "DeepSeekSettings", "SqliteSettings"]
