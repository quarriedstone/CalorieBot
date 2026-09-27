from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.domain.models import NoteSummary
from bot.domain.services import (
    FoodNotFoundError,
    FoodService,
    NoteService,
    UserService,
)
from bot.presentation import keyboards as kb
from bot.presentation.formatting import (
    GOAL_PROMPT,
    HELP_TEXT,
    NO_GOAL_PROMPT,
    NO_NOTE_PROMPT,
    SELECT_NOTE_PROMPT,
    added_text,
    build_note_text,
    confirm_note_delete_text,
    delete_prompt_text,
    deleted_text,
    macros_str,
    not_found_text,
    note_deleted_text,
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
    callback: CallbackQuery, note_service: NoteService
) -> NoteSummary | None:
    """Сводка заметки из callback_data с проверкой владельца."""
    note_id = _int_arg(callback.data, 1)
    if note_id is None:
        await callback.answer("Неверный запрос.")
        return None
    summary = await note_service.get_summary_for_user(callback.from_user.id, note_id)
    if summary is None:
        await callback.answer("Заметка не найдена.")
    return summary


async def _need_note_choice(message: Message, note_service: NoteService) -> bool:
    """Блокирует действие, пока заметка не создана и не выбрана.

    Заметка никогда не создаётся неявно при вводе продукта: первую заметку
    пользователь создаёт сам кнопкой «📝 Новая заметка». Если заметки есть,
    но активная не выбрана, предлагаем выбрать её из истории.
    """
    user_id = message.from_user.id
    if await note_service.get_selected_note(user_id) is not None:
        return False
    notes = await note_service.get_history(user_id, 5)
    if not notes:
        await message.answer(NO_NOTE_PROMPT, reply_markup=kb.main_menu())
        return True
    await message.answer(SELECT_NOTE_PROMPT, reply_markup=kb.history_menu(notes))
    return True


async def _has_goal(
    message: Message,
    user_service: UserService,
    state: FSMContext,
) -> bool:
    """Без цели КБЖУ считать нечего: просим сначала создать цель.

    Сразу переводим диалог в режим ввода цели, чтобы следующее сообщение
    пользователя было распознано как Б/Ж/У, а не как название продукта.
    """
    if await user_service.get_goal(message.from_user.id) is not None:
        return True
    await state.set_state(GoalState.waiting)
    await message.answer(NO_GOAL_PROMPT, reply_markup=kb.cancel_menu())
    return False


async def _show_note(message: Message, note_service: NoteService, note_id: int) -> None:
    summary = await note_service.get_summary(note_id)
    if summary is None:
        return
    await message.answer(
        build_note_text(summary),
        reply_markup=kb.note_actions(summary.note.id),
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
    goal = user_service.parse_goal(message.text or "")
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
@router.message(F.text == kb.MENU_NEW_NOTE, StateFilter(None))
async def new_note(message: Message, note_service: NoteService) -> None:
    note = await note_service.start_new_note(message.from_user.id)
    await _show_note(message, note_service, note.id)


# ---------- Удаление заметки ----------
@router.callback_query(F.data.startswith("delnote:"))
async def delete_note_ask(callback: CallbackQuery, note_service: NoteService) -> None:
    summary = await _own_summary(callback, note_service)
    if summary is None:
        return
    await callback.answer()
    await callback.message.edit_text(
        confirm_note_delete_text(summary),
        reply_markup=kb.note_delete_confirm(summary.note.id),
    )


@router.callback_query(F.data.startswith("delnoteno:"))
async def delete_note_cancel(
    callback: CallbackQuery, note_service: NoteService
) -> None:
    summary = await _own_summary(callback, note_service)
    if summary is None:
        return
    await callback.answer("Удаление отменено")
    await callback.message.edit_text(
        build_note_text(summary),
        reply_markup=kb.note_actions(summary.note.id),
    )


@router.callback_query(F.data.startswith("delnoteok:"))
async def delete_note_cb(callback: CallbackQuery, note_service: NoteService) -> None:
    user_id = callback.from_user.id
    note_id = _int_arg(callback.data, 1)
    if note_id is None:
        await callback.answer("Неверный запрос.")
        return
    note = await note_service.delete_note(user_id, note_id)
    if note is None:
        await callback.answer("Заметка не найдена.")
        return
    await callback.answer("Заметка удалена")
    text = note_deleted_text(note.label)
    notes = await note_service.get_history(user_id, 5)
    if not notes:
        await callback.message.edit_text(
            f"{text}\n\nНовая заметка создастся по кнопке «📝 Новая заметка».",
            reply_markup=None,
        )
        return
    await callback.message.edit_text(
        f"{text}\n\nВыберите заметку заново — из истории:",
        reply_markup=kb.history_menu(notes),
    )


# ---------- Выбор заметки ----------
@router.message(F.text == kb.MENU_HISTORY, StateFilter(None))
async def history(message: Message, note_service: NoteService) -> None:
    notes = await note_service.get_history(message.from_user.id, 5)
    if not notes:
        await message.answer("Заметок пока нет.", reply_markup=kb.main_menu())
        return
    await message.answer("Последние заметки:", reply_markup=kb.history_menu(notes))


@router.callback_query(F.data.startswith("note:"))
async def show_note_cb(callback: CallbackQuery, note_service: NoteService) -> None:
    note_id = _int_arg(callback.data, 1)
    if note_id is None:
        await callback.answer("Неверный запрос.")
        return
    note = await note_service.select_note(callback.from_user.id, note_id)
    if note is None:
        await callback.answer("Заметка не найдена.")
        return
    await callback.answer("Продукты будут добавляться в эту заметку")
    await _show_note(callback.message, note_service, note.id)


# ---------- Добавление блюда ----------
@router.message(
    F.text,
    ~F.text.startswith("/"),
    ~F.text.in_(kb.MENU_TEXTS),
    StateFilter(None),
)
async def add_food(
    message: Message,
    state: FSMContext,
    user_service: UserService,
    note_service: NoteService,
    food_service: FoodService,
) -> None:
    await user_service.register(message.from_user.id, message.from_user.username)
    if not await _has_goal(message, user_service, state):
        return
    if await _need_note_choice(message, note_service):
        return
    text = message.text.strip()

    # «круассан 60 10,15,40» — точный расчёт без обращения к API.
    result = await food_service.try_add_exact(message.from_user.id, text)
    if result is not None:
        await message.answer(added_text(result))
        await _show_note(message, note_service, result.note.id)
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
    await _show_note(message, note_service, result.note.id)


# ---------- Удаление продукта ----------
@router.message(F.text == kb.MENU_DELETE, StateFilter(None))
async def delete_start(message: Message, note_service: NoteService) -> None:
    if await _need_note_choice(message, note_service):
        return
    note = await note_service.get_current_note(message.from_user.id)
    summary = await note_service.get_summary(note.id)
    if summary is None or not summary.meals:
        await message.answer(
            "В этой заметке пока нечего удалять.",
            reply_markup=kb.main_menu(),
        )
        return
    await message.answer(
        delete_prompt_text(summary.meals),
        reply_markup=kb.delete_menu(note.id, summary.meals),
    )


@router.callback_query(F.data.startswith("delpage:"))
async def delete_page_cb(callback: CallbackQuery, note_service: NoteService) -> None:
    note_id = _int_arg(callback.data, 1)
    page = _int_arg(callback.data, 2)
    if note_id is None or page is None:
        await callback.answer("Неверный запрос.")
        return
    summary = await note_service.get_summary_for_user(callback.from_user.id, note_id)
    if summary is None or not summary.meals:
        await callback.answer("Продукты не найдены.")
        return
    await callback.answer()
    await callback.message.edit_reply_markup(
        reply_markup=kb.delete_menu(note_id, summary.meals, page=page)
    )


@router.callback_query(F.data.startswith("delmeal:"))
async def delete_meal_cb(callback: CallbackQuery, note_service: NoteService) -> None:
    meal_id = _int_arg(callback.data, 1)
    if meal_id is None:
        await callback.answer("Неверный запрос.")
        return
    result = await note_service.delete_meal(callback.from_user.id, meal_id)
    if result is None:
        await callback.answer("Продукт не найден.")
        return
    await callback.answer("Продукт удалён")
    await callback.message.edit_text(
        f"{deleted_text(result)}\n\n{build_note_text(result.summary)}",
        reply_markup=kb.note_actions(result.summary.note.id),
    )
