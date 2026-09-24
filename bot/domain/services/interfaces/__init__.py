"""Порты (интерфейсы) доменного слоя, от которых зависят сервисы."""

from __future__ import annotations

from bot.domain.services.interfaces.database import DatabaseInterface

__all__ = ["DatabaseInterface"]
