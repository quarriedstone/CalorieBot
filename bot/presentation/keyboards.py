from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from bot.domain.models import DayInfo, Meal

MENU_GOAL = "🎯 Цель КБЖУ"
MENU_NEW_DAY = "📝 Новая заметка"
MENU_HISTORY = "📂 Выбрать заметку"
MENU_DELETE = "🗑 Удалить продукт"
MENU_PLAN = "ℹ️ Мой план"
CANCEL = "❌ Отмена"

MENU_TEXTS = {MENU_GOAL, MENU_NEW_DAY, MENU_HISTORY, MENU_DELETE, MENU_PLAN, CANCEL}


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MENU_GOAL)],
            [KeyboardButton(text=MENU_NEW_DAY), KeyboardButton(text=MENU_HISTORY)],
            [KeyboardButton(text=MENU_DELETE)],
            [KeyboardButton(text=MENU_PLAN)],
        ],
        resize_keyboard=True,
    )


def cancel_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=CANCEL)]],
        resize_keyboard=True,
    )


def history_menu(days: list[DayInfo]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"📅 {d.label}", callback_data=f"day:{d.id}")]
        for d in days
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def day_actions(day_id: int) -> InlineKeyboardMarkup:
    """Кнопки под карточкой заметки: удалить заметку."""
    rows = [
        [
            InlineKeyboardButton(
                text="🗑 Удалить заметку", callback_data=f"delday:{day_id}"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def day_delete_confirm(day_id: int) -> InlineKeyboardMarkup:
    """Подтверждение удаления заметки."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Удалить", callback_data=f"deldayok:{day_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена", callback_data=f"deldayno:{day_id}"
                )
            ],
        ]
    )


DELETE_PAGE_SIZE = 8


def delete_menu(day_id: int, meals: list[Meal], page: int = 0) -> InlineKeyboardMarkup:
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
                    callback_data=f"delpage:{day_id}:{page + 1}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)
