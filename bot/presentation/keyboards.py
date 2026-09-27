from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from bot.domain.models import Meal, NoteInfo

MENU_GOAL = "🎯 Цель КБЖУ"
MENU_NEW_NOTE = "📝 Новая заметка"
MENU_HISTORY = "📂 Выбрать заметку"
MENU_DELETE_NOTE = "🗑 Удалить заметку"
MENU_PLAN = "ℹ️ Мой план"
CANCEL = "❌ Отмена"

DELETE_PRODUCT = "🗑 Удалить продукт"

MENU_TEXTS = {
    MENU_GOAL,
    MENU_NEW_NOTE,
    MENU_HISTORY,
    MENU_DELETE_NOTE,
    MENU_PLAN,
    CANCEL,
}


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MENU_GOAL)],
            [KeyboardButton(text=MENU_NEW_NOTE), KeyboardButton(text=MENU_HISTORY)],
            [KeyboardButton(text=MENU_DELETE_NOTE)],
            [KeyboardButton(text=MENU_PLAN)],
        ],
        resize_keyboard=True,
    )


def cancel_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=CANCEL)]],
        resize_keyboard=True,
    )


def history_menu(notes: list[NoteInfo]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"📅 {n.label}", callback_data=f"note:{n.id}")]
        for n in notes
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def note_actions(note_id: int) -> InlineKeyboardMarkup:
    """Кнопки под карточкой заметки: удалить продукт из этой заметки."""
    rows = [
        [
            InlineKeyboardButton(
                text=DELETE_PRODUCT, callback_data=f"delproduct:{note_id}"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def note_delete_confirm(note_id: int) -> InlineKeyboardMarkup:
    """Подтверждение удаления заметки."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Удалить", callback_data=f"delnoteok:{note_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена", callback_data=f"delnoteno:{note_id}"
                )
            ],
        ]
    )


DELETE_PAGE_SIZE = 8


def delete_menu(note_id: int, meals: list[Meal], page: int = 0) -> InlineKeyboardMarkup:
    """Выбор продукта на удаление: номера идут в обратном порядке.

    Последний продукт заметки показывается первым. На странице не больше
    ``DELETE_PAGE_SIZE`` номеров; если записи не поместились, снизу
    появляется широкая кнопка «Далее» — переход к более ранним записям.
    """
    total = len(meals)
    last_page = max(0, (total - 1) // DELETE_PAGE_SIZE)
    page = min(max(page, 0), last_page)

    end = total - page * DELETE_PAGE_SIZE
    start = max(0, end - DELETE_PAGE_SIZE)
    numbered = list(enumerate(meals[start:end], start=start + 1))[::-1]

    rows = [
        [
            InlineKeyboardButton(text=str(number), callback_data=f"delmeal:{meal.id}")
            for number, meal in numbered[i : i + 2]
        ]
        for i in range(0, len(numbered), 2)
    ]
    if start > 0:
        rows.append(
            [
                InlineKeyboardButton(
                    text="Далее",
                    callback_data=f"delpage:{note_id}:{page + 1}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)
