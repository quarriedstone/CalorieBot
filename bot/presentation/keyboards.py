from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from bot.domain.models import DayInfo

MENU_GOAL = "🎯 Цель КБЖУ"
MENU_NEW_DAY = "📅 Новый день"
MENU_HISTORY = "📜 История"
MENU_PLAN = "ℹ️ Мой план"
CANCEL = "❌ Отмена"

MENU_TEXTS = {MENU_GOAL, MENU_NEW_DAY, MENU_HISTORY, MENU_PLAN, CANCEL}


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MENU_GOAL)],
            [KeyboardButton(text=MENU_NEW_DAY), KeyboardButton(text=MENU_HISTORY)],
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


def day_actions(show_today: bool = False) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="📅 Новый день", callback_data="newday")]]
    if show_today:
        rows.append(
            [InlineKeyboardButton(text="↩️ Текущий день", callback_data="today")]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)
