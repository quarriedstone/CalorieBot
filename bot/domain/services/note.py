"""Сервис заметок: создание, история, выбор активной, сводка и удаление."""

from __future__ import annotations

from bot.domain.models import DeleteMealResult, NoteInfo, NoteSummary
from bot.domain.services.common import today
from bot.domain.services.interfaces import DatabaseInterface
from bot.domain.services.user import UserService

__all__ = ["NoteService"]


class NoteService:
    """Заметки, история, выбор активной заметки и сводка."""

    def __init__(self, db: DatabaseInterface, users: UserService) -> None:
        self._db = db
        self._users = users

    async def start_new_note(self, user_id: int) -> NoteInfo:
        """Создать новую заметку на сегодня и сделать её выбранной."""
        note = await self._create_note(user_id)
        await self._db.set_active_note(user_id, note.id)
        return note

    async def get_current_note(self, user_id: int) -> NoteInfo:
        """Заметка для записи продуктов: выбранная, иначе последняя.

        Если заметок ещё нет, создаётся новая на сегодня.
        """
        selected = await self.get_selected_note(user_id)
        if selected is not None:
            return selected
        latest = await self._latest_note(user_id)
        if latest is not None:
            return latest
        return await self._create_note(user_id)

    async def select_note(self, user_id: int, note_id: int) -> NoteInfo | None:
        note = await self._own_note(user_id, note_id)
        if note is None:
            return None
        await self._db.set_active_note(user_id, note_id)
        return note

    async def get_selected_note(self, user_id: int) -> NoteInfo | None:
        """Активная заметка пользователя или None, если она не выбрана."""
        user = await self._db.get_user(user_id)
        if user is None or user.active_note_id is None:
            return None
        return await self._own_note(user_id, user.active_note_id)

    async def get_history(self, user_id: int, limit: int = 5) -> list[NoteInfo]:
        return await self._db.get_last_notes(user_id, limit)

    async def delete_note(self, user_id: int, note_id: int) -> NoteInfo | None:
        """Удалить заметку пользователя вместе с записями.

        Возвращает None, если заметки нет или она чужая. Если заметка была
        выбранной, выбор сбрасывается.
        """
        note = await self._own_note(user_id, note_id)
        if note is None:
            return None
        user = await self._db.get_user(user_id)
        if user is not None and user.active_note_id == note_id:
            await self._db.set_active_note(user_id, None)
        await self._db.delete_note(note_id)
        return note

    async def is_latest_note(self, user_id: int, note_id: int) -> bool:
        """Последняя ли это заметка пользователя."""
        latest = await self._latest_note(user_id)
        return latest is not None and latest.id == note_id

    async def get_summary(self, note_id: int) -> NoteSummary | None:
        note = await self._db.get_note(note_id)
        if note is None:
            return None
        return NoteSummary(
            note=note,
            meals=await self._db.get_meals(note_id),
            totals=await self._db.get_note_totals(note_id),
            goal=await self._users.get_goal(note.user_id),
            is_latest=await self.is_latest_note(note.user_id, note_id),
        )

    async def get_summary_for_user(
        self, user_id: int, note_id: int
    ) -> NoteSummary | None:
        """Сводка заметки, если она принадлежит пользователю."""
        if await self._own_note(user_id, note_id) is None:
            return None
        return await self.get_summary(note_id)

    async def delete_meal(self, user_id: int, meal_id: int) -> DeleteMealResult | None:
        """Удалить блюдо пользователя и вернуть обновлённую сводку заметки.

        Возвращает None, если блюда нет или оно принадлежит чужой заметке.
        """
        meal = await self._db.get_meal(meal_id)
        if meal is None:
            return None
        if await self._own_note(user_id, meal.note_id) is None:
            return None
        await self._db.delete_meal(meal_id)
        summary = await self.get_summary(meal.note_id)
        if summary is None:
            return None
        return DeleteMealResult(food=meal, summary=summary)

    # ---------- внутренние методы ----------
    async def _create_note(self, user_id: int) -> NoteInfo:
        """Создать заметку на сегодня с уникальным названием."""
        date = today()
        count = await self._db.count_notes(user_id, date)
        label = date if not count else f"{date} ({count + 1})"
        return await self._db.add_note(user_id, date, label)

    async def _latest_note(self, user_id: int) -> NoteInfo | None:
        notes = await self._db.get_last_notes(user_id, 1)
        return notes[0] if notes else None

    async def _own_note(self, user_id: int, note_id: int) -> NoteInfo | None:
        """Заметка, если она существует и принадлежит пользователю."""
        note = await self._db.get_note(note_id)
        if note is None or note.user_id != user_id:
            return None
        return note
