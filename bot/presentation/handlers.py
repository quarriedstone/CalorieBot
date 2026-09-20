from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.domain.models import DaySummary
from bot.domain.parsing import parse_goal
from bot.domain.services import (
    DayService,
    FoodNotFoundError,
    FoodService,
    UserService,
)
from bot.presentation import keyboards as kb
from bot.presentation.formatting import (
    GOAL_PROMPT,
    HELP_TEXT,
    NO_GOAL_PROMPT,
    SELECT_DAY_PROMPT,
    added_text,
    build_day_text,
    confirm_day_delete_text,
    day_deleted_text,
    delete_prompt_text,
    deleted_text,
    macros_str,
    not_found_text,
)

logger = logging.getLogger(__name__)
router = Router()


class GoalState(StatesGroup):
    waiting = State()


def _int_arg(data: str | None, index: int) -> int | None:
    """Числовой аргумент callback_data вида «prefix:1:2»."""
    try:
        return int((data or "").split(":")[index])
    except (IndexError, ValueError):
        return None


async def _own_summary(
    callback: CallbackQuery, day_service: DayService
) -> DaySummary | None:
    """Сводка заметки из callback_data с проверкой владельца."""
    day_id = _int_arg(callback.data, 1)
    if day_id is None:
        await callback.answer("Неверный запрос.")
        return None
    summary = await day_service.get_summary_for_user(callback.from_user.id, day_id)
    if summary is None:
        await callback.answer("Заметка не найдена.")
    return summary


async def _need_day_choice(message: Message, day_service: DayService) -> bool:
    """Блокирует действие, пока заметка не выбрана заново из истории."""
    if not await day_service.needs_day_choice(message.from_user.id):
        return False
    days = await day_service.get_history(message.from_user.id, 5)
    await message.answer(SELECT_DAY_PROMPT, reply_markup=kb.history_menu(days))
    return True


async def _has_goal(message: Message, user_service: UserService) -> bool:
    """Без цели КБЖУ считать нечего: просим сначала создать цель."""
    if await user_service.get_goal(message.from_user.id) is not None:
        return True
    await message.answer(NO_GOAL_PROMPT, reply_markup=kb.main_menu())
    return False


async def _show_day(message: Message, day_service: DayService, day_id: int) -> None:
    summary = await day_service.get_summary(day_id)
    if summary is None:
        return
    await message.answer(
        build_day_text(summary),
        reply_markup=kb.day_actions(summary.day.id),
    )


# ---------- Команды ----------
@router.message(CommandStart())
async def cmd_start(message: Message, user_service: UserService) -> None:
    await user_service.register(message.from_user.id, message.from_user.username)
    await message.answer(HELP_TEXT, reply_markup=kb.main_menu())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=kb.main_menu())


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменено.", reply_markup=kb.main_menu())


# ---------- Цель КБЖУ ----------
@router.message(F.text == kb.MENU_GOAL, StateFilter(None))
async def goal_start(message: Message, state: FSMContext) -> None:
    await state.set_state(GoalState.waiting)
    await message.answer(GOAL_PROMPT, reply_markup=kb.cancel_menu())


@router.message(GoalState.waiting, F.text != kb.CANCEL)
async def goal_input(
    message: Message,
    state: FSMContext,
    user_service: UserService,
) -> None:
    goal = parse_goal(message.text or "")
    if goal is None:
        await message.answer(NO_GOAL_PROMPT)
        return
    await user_service.set_goal(message.from_user.id, goal)
    await state.clear()
    await message.answer(
        f"Цель сохранена!\n{macros_str(goal)}",
        reply_markup=kb.main_menu(),
    )


@router.message(F.text == kb.CANCEL)
async def cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменено.", reply_markup=kb.main_menu())


# ---------- Мой план ----------
@router.message(F.text == kb.MENU_PLAN, StateFilter(None))
async def show_plan(message: Message, user_service: UserService) -> None:
    goal = await user_service.get_goal(message.from_user.id)
    if goal is None:
        await message.answer(
            "Цель КБЖУ ещё не задана. Задайте её кнопкой «🎯 Цель КБЖУ».",
            reply_markup=kb.main_menu(),
        )
        return
    await message.answer(
        f"Ваша цель на день:\n{macros_str(goal)}",
        reply_markup=kb.main_menu(),
    )


# ---------- Новая заметка ----------
@router.message(F.text == kb.MENU_NEW_DAY, StateFilter(None))
async def new_day(message: Message, day_service: DayService) -> None:
    day = await day_service.start_new_day(message.from_user.id)
    await _show_day(message, day_service, day.id)


# ---------- Удаление заметки ----------
@router.callback_query(F.data.startswith("delday:"))
async def delete_day_ask(callback: CallbackQuery, day_service: DayService) -> None:
    summary = await _own_summary(callback, day_service)
    if summary is None:
        return
    await callback.answer()
    await callback.message.edit_text(
        confirm_day_delete_text(summary),
        reply_markup=kb.day_delete_confirm(summary.day.id),
    )


@router.callback_query(F.data.startswith("deldayno:"))
async def delete_day_cancel(callback: CallbackQuery, day_service: DayService) -> None:
    summary = await _own_summary(callback, day_service)
    if summary is None:
        return
    await callback.answer("Удаление отменено")
    await callback.message.edit_text(
        build_day_text(summary),
        reply_markup=kb.day_actions(summary.day.id),
    )


@router.callback_query(F.data.startswith("deldayok:"))
async def delete_day_cb(callback: CallbackQuery, day_service: DayService) -> None:
    user_id = callback.from_user.id
    day_id = _int_arg(callback.data, 1)
    if day_id is None:
        await callback.answer("Неверный запрос.")
        return
    day = await day_service.delete_day(user_id, day_id)
    if day is None:
        await callback.answer("Заметка не найдена.")
        return
    await callback.answer("Заметка удалена")
    text = day_deleted_text(day.label)
    days = await day_service.get_history(user_id, 5)
    if not days:
        await callback.message.edit_text(
            f"{text}\n\nЗаметок пока нет — новая заметка создастся при добавлении "
            "продукта или по кнопке «📝 Новая заметка».",
            reply_markup=None,
        )
        return
    await callback.message.edit_text(
        f"{text}\n\nВыберите заметку заново — из истории:",
        reply_markup=kb.history_menu(days),
    )


# ---------- Выбор заметки ----------
@router.message(F.text == kb.MENU_HISTORY, StateFilter(None))
async def history(message: Message, day_service: DayService) -> None:
    days = await day_service.get_history(message.from_user.id, 5)
    if not days:
        await message.answer("Заметок пока нет.", reply_markup=kb.main_menu())
        return
    await message.answer("Последние заметки:", reply_markup=kb.history_menu(days))


@router.callback_query(F.data.startswith("day:"))
async def show_day_cb(callback: CallbackQuery, day_service: DayService) -> None:
    day_id = _int_arg(callback.data, 1)
    if day_id is None:
        await callback.answer("Неверный запрос.")
        return
    day = await day_service.select_day(callback.from_user.id, day_id)
    if day is None:
        await callback.answer("Заметка не найдена.")
        return
    await callback.answer("Продукты будут добавляться в эту заметку")
    await _show_day(callback.message, day_service, day.id)


# ---------- Добавление блюда ----------
@router.message(
    F.text,
    ~F.text.startswith("/"),
    ~F.text.in_(kb.MENU_TEXTS),
    StateFilter(None),
)
async def add_food(
    message: Message,
    user_service: UserService,
    day_service: DayService,
    food_service: FoodService,
) -> None:
    await user_service.register(message.from_user.id, message.from_user.username)
    if not await _has_goal(message, user_service):
        return
    if await _need_day_choice(message, day_service):
        return
    text = message.text.strip()

    # «круассан 60 10,15,40» — точный расчёт без обращения к API.
    result = await food_service.try_add_exact(message.from_user.id, text)
    if result is not None:
        await message.answer(added_text(result))
        await _show_day(message, day_service, result.day.id)
        return

    # «круассан 60» или свободное описание — КБЖУ подбирает DeepSeek.
    processing = await message.answer("Считаю КБЖУ… ⏳")
    try:
        result = await food_service.add_via_ai(message.from_user.id, text)
    except FoodNotFoundError:
        await processing.edit_text(not_found_text(text))
        return
    except Exception:
        logger.exception("Ошибка при обращении к DeepSeek")
        await processing.edit_text("Не удалось распознать блюдо. Попробуйте ещё раз.")
        return

    await processing.edit_text(added_text(result))
    await _show_day(message, day_service, result.day.id)


# ---------- Удаление продукта ----------
@router.message(F.text == kb.MENU_DELETE, StateFilter(None))
async def delete_start(message: Message, day_service: DayService) -> None:
    if await _need_day_choice(message, day_service):
        return
    day = await day_service.get_current_day(message.from_user.id)
    summary = await day_service.get_summary(day.id)
    if summary is None or not summary.meals:
        await message.answer(
            "В этой заметке пока нечего удалять.",
            reply_markup=kb.main_menu(),
        )
        return
    await message.answer(
        delete_prompt_text(summary.meals),
        reply_markup=kb.delete_menu(day.id, summary.meals),
    )


@router.callback_query(F.data.startswith("delpage:"))
async def delete_page_cb(callback: CallbackQuery, day_service: DayService) -> None:
    day_id = _int_arg(callback.data, 1)
    page = _int_arg(callback.data, 2)
    if day_id is None or page is None:
        await callback.answer("Неверный запрос.")
        return
    summary = await day_service.get_summary_for_user(callback.from_user.id, day_id)
    if summary is None or not summary.meals:
        await callback.answer("Продукты не найдены.")
        return
    await callback.answer()
    await callback.message.edit_reply_markup(
        reply_markup=kb.delete_menu(day_id, summary.meals, page=page)
    )


@router.callback_query(F.data.startswith("delmeal:"))
async def delete_meal_cb(callback: CallbackQuery, day_service: DayService) -> None:
    meal_id = _int_arg(callback.data, 1)
    if meal_id is None:
        await callback.answer("Неверный запрос.")
        return
    result = await day_service.delete_meal(callback.from_user.id, meal_id)
    if result is None:
        await callback.answer("Продукт не найден.")
        return
    await callback.answer("Продукт удалён")
    await callback.message.edit_text(
        f"{deleted_text(result)}\n\n{build_day_text(result.summary)}",
        reply_markup=kb.day_actions(result.summary.day.id),
    )
