"""Декларативная база SQLAlchemy-моделей."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """База моделей таблиц; её ``metadata`` использует Alembic (autogenerate)."""
