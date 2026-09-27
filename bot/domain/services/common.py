"""Общие помощники сервисов."""

from __future__ import annotations

from datetime import date

__all__ = ["today"]


def today() -> str:
    """Сегодняшняя дата в формате ISO."""
    return date.today().isoformat()
