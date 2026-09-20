from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.domain.parsing import parse_goal
from bot.domain.services import DayService, FoodService, UserService
from bot.presentation import keyboards as kb
from bot.presentation.formatting import (
    GOAL_PROMPT,
    HELP_TEXT,
    added_text,
    build_day_text,
    macros_str,
)

logger = logging.getLogger(__name__)
router = Router()


class GoalState(StatesGroup):
    waiting = State()


async def _show_day(message: Message, day_service: DayService, day_id: int) -> None:
    summary = await day_service.get_summary(day_id)
    if summary is None:
        return
    await message.answer(
        build_day_text(summary),
        reply_markup=kb.day_actions(show_today=not summary.is_latest),
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
        await message.answer(f"Не понял.\n\n{GOAL_PROMPT}")
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


# ---------- Новый день ----------
@router.message(F.text == kb.MENU_NEW_DAY, StateFilter(None))
async def new_day(message: Message, day_service: DayService) -> None:
    day = await day_service.start_new_day(message.from_user.id)
    await _show_day(message, day_service, day.id)


@router.callback_query(F.data == "newday")
async def new_day_cb(callback: CallbackQuery, day_service: DayService) -> None:
    day = await day_service.start_new_day(callback.from_user.id)
    await callback.answer("Новый день создан")
    await _show_day(callback.message, day_service, day.id)


# ---------- История ----------
@router.message(F.text == kb.MENU_HISTORY, StateFilter(None))
async def history(message: Message, day_service: DayService) -> None:
    days = await day_service.get_history(message.from_user.id, 5)
    if not days:
        await message.answer("История пока пуста.", reply_markup=kb.main_menu())
        return
    await message.answer("Последние дни:", reply_markup=kb.history_menu(days))


@router.callback_query(F.data.startswith("day:"))
async def show_day_cb(callback: CallbackQuery, day_service: DayService) -> None:
    try:
        day_id = int(callback.data.split(":", 1)[1])
    except ValueError:
        await callback.answer("Неверный запрос.")
        return
    day = await day_service.select_day(callback.from_user.id, day_id)
    if day is None:
        await callback.answer("День не найден.")
        return
    await callback.answer("Продукты будут добавляться в этот день")
    await _show_day(callback.message, day_service, day.id)


@router.callback_query(F.data == "today")
async def today_cb(callback: CallbackQuery, day_service: DayService) -> None:
    day = await day_service.back_to_today(callback.from_user.id)
    await callback.answer("Возврат к текущему дню")
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
    except Exception:
        logger.exception("Ошибка при обращении к DeepSeek")
        await processing.edit_text("Не удалось распознать блюдо. Попробуйте ещё раз.")
        return

    await processing.edit_text(added_text(result))
    await _show_day(message, day_service, result.day.id)
