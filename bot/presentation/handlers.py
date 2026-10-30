from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)

from bot.domain.models import NoteInfo, NoteSummary
from bot.domain.services import (
    FoodNotFoundError,
    FoodService,
    FoodValueError,
    NoteService,
    PaymentService,
    UserService,
)
from bot.domain.services.food import MAX_WEIGHT
from bot.presentation import keyboards as kb
from bot.presentation.formatting import (
    GOAL_PROMPT,
    GRANT_USAGE,
    HELP_TEXT,
    NO_GOAL_PROMPT,
    NO_NOTE_PROMPT,
    REVOKE_USAGE,
    SELECT_NOTE_PROMPT,
    added_text,
    build_note_text,
    confirm_note_delete_text,
    delete_prompt_text,
    deleted_text,
    granted_text,
    history_text,
    invalid_food_text,
    macros_str,
    meal_limit_text,
    not_found_text,
    note_deleted_text,
    note_limit_text,
    payment_success_text,
    revoked_text,
    subscription_line,
    subscription_text,
)
from bot.settings import PaymentsSettings

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


def _optional_int(value: str | None) -> int | None:
    """Число из аргумента команды или None, если это не число."""
    if value is None or not value.isdigit():
        return None
    return int(value)


def _is_admin(message: Message, admin_ids: set[int]) -> bool:
    """Служебная команда: остальным не отвечаем вовсе."""
    user = message.from_user
    return user is not None and user.id in admin_ids


def _command_args(message: Message) -> list[str]:
    """Аргументы команды без самой команды."""
    return (message.text or "").split()[1:]


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


async def _history_page(
    note_service: NoteService, user_id: int, page: int
) -> tuple[list[NoteInfo], bool]:
    """Страница истории заметок и признак «есть ещё более старые».

    Берётся на одну заметку больше, чем помещается на страницу: если лишняя
    нашлась — значит, дальше есть что показывать.
    """
    page = max(page, 0)
    notes = await note_service.get_history(
        user_id,
        kb.HISTORY_PAGE_SIZE + 1,
        page * kb.HISTORY_PAGE_SIZE,
    )
    return notes[: kb.HISTORY_PAGE_SIZE], len(notes) > kb.HISTORY_PAGE_SIZE


async def _need_note_choice(message: Message, note_service: NoteService) -> bool:
    """Блокирует действие, пока заметка не создана и не выбрана.

    Заметка никогда не создаётся неявно при вводе продукта: первую заметку
    пользователь создаёт сам кнопкой «📝 Новая заметка». Если заметки есть,
    но активная не выбрана, предлагаем выбрать её из истории.
    """
    user_id = message.from_user.id
    if await note_service.get_selected_note(user_id) is not None:
        return False
    notes, has_next = await _history_page(note_service, user_id, 0)
    if not notes:
        await message.answer(NO_NOTE_PROMPT, reply_markup=kb.main_menu())
        return True
    await message.answer(
        SELECT_NOTE_PROMPT,
        reply_markup=kb.history_menu(notes, 0, has_next),
    )
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


# ---------- Служебные команды ----------
@router.message(Command("grant"))
async def grant_subscription(
    message: Message,
    user_service: UserService,
    payment_service: PaymentService,
    admin_ids: set[int],
) -> None:
    """Выдать подписку: /grant [user_id] [дней] — по умолчанию себе на 3650."""
    user = message.from_user
    if user is None or not _is_admin(message, admin_ids):
        return
    args = _command_args(message)
    target_id = _optional_int(args[0]) if args else None
    days = _optional_int(args[1]) if len(args) > 1 else None
    if (
        len(args) > 2
        or (args and target_id is None)
        or (len(args) > 1 and (days is None or days <= 0))
    ):
        await message.answer(GRANT_USAGE)
        return
    target = user.id if target_id is None else target_id
    await user_service.ensure_user(target)
    paid_until = await payment_service.grant(target, days)
    await message.answer(granted_text(target, paid_until))


@router.message(Command("revoke"))
async def revoke_subscription(
    message: Message,
    payment_service: PaymentService,
    admin_ids: set[int],
) -> None:
    """Снять подписку: /revoke [user_id]."""
    user = message.from_user
    if user is None or not _is_admin(message, admin_ids):
        return
    args = _command_args(message)
    target_id = _optional_int(args[0]) if args else None
    if len(args) > 1 or (args and target_id is None):
        await message.answer(REVOKE_USAGE)
        return
    target = user.id if target_id is None else target_id
    await payment_service.revoke(target)
    await message.answer(revoked_text(target))


# ---------- Мой план ----------
@router.message(F.text == kb.MENU_PLAN, StateFilter(None))
async def show_plan(
    message: Message,
    user_service: UserService,
    payment_service: PaymentService,
) -> None:
    goal = await user_service.get_goal(message.from_user.id)
    if goal is None:
        await message.answer(
            "Цель КБЖУ ещё не задана. Задайте её кнопкой «🎯 Цель КБЖУ».",
            reply_markup=kb.main_menu(),
        )
        return
    user_id = message.from_user.id
    active = await payment_service.is_subscribed(user_id)
    paid_until = await payment_service.paid_until(user_id) if active else None
    await message.answer(
        f"Ваша цель на день:\n{macros_str(goal)}\n\n{subscription_line(paid_until)}",
        reply_markup=kb.main_menu(),
    )


# ---------- Подписка ----------
@router.message(F.text == kb.MENU_SUBSCRIBE, StateFilter(None))
async def subscribe(
    message: Message,
    payment_service: PaymentService,
    payments_settings: PaymentsSettings,
) -> None:
    """Состояние подписки и кнопка оплаты звёздами."""
    user_id = message.from_user.id
    await message.answer(
        subscription_text(
            paid_until=await payment_service.paid_until(user_id),
            active=await payment_service.is_subscribed(user_id),
            price=payments_settings.price,
            days=payments_settings.days,
            free_notes=payments_settings.free_notes,
            free_meals=payments_settings.free_meals,
        ),
        reply_markup=kb.pay_button(payments_settings.price),
    )


@router.callback_query(F.data == kb.PAY_CALLBACK)
async def pay_subscribe_cb(
    callback: CallbackQuery,
    payment_service: PaymentService,
    payments_settings: PaymentsSettings,
) -> None:
    """Выставить счёт на подписку (Telegram Stars)."""
    payment = await payment_service.start(
        callback.from_user.id,
        payments_settings.price,
        payments_settings.currency,
        payments_settings.days,
    )
    await callback.answer()
    await callback.message.answer_invoice(
        title=payments_settings.title,
        description=payments_settings.description,
        payload=payment.payload,
        provider_token=payments_settings.provider_token,
        currency=payments_settings.currency,
        prices=[
            LabeledPrice(
                label=payments_settings.title, amount=payments_settings.price
            )
        ],
    )


@router.pre_checkout_query()
async def pre_checkout(
    query: PreCheckoutQuery, payment_service: PaymentService
) -> None:
    """Подтверждение счёта: Telegram ждёт ответ не дольше 10 секунд."""
    ok, error = await payment_service.check_precheckout(
        query.from_user.id,
        query.invoice_payload,
        query.total_amount,
        query.currency,
    )
    await query.answer(ok=ok, error_message=None if ok else error)


@router.message(F.successful_payment)
async def payment_done(
    message: Message,
    payment_service: PaymentService,
    user_service: UserService,
) -> None:
    """Оплата прошла: фиксируем платёж и продлеваем подписку."""
    successful = message.successful_payment
    user = message.from_user
    if successful is None or user is None:
        return
    # Запись пользователя нужна для сохранения срока подписки.
    await user_service.ensure_user(user.id)
    paid_until = await payment_service.confirm(
        user.id,
        successful.invoice_payload,
        successful.telegram_payment_charge_id,
        successful.provider_payment_charge_id,
    )
    if paid_until is None:
        logger.warning(
            "Оплата по счёту %s не применена: счёт не найден или уже оплачен",
            successful.invoice_payload,
        )
        return
    await message.answer(
        payment_success_text(paid_until), reply_markup=kb.main_menu()
    )


# ---------- Новая заметка ----------
@router.message(F.text == kb.MENU_NEW_NOTE, StateFilter(None))
async def new_note(
    message: Message,
    note_service: NoteService,
    payment_service: PaymentService,
    payments_settings: PaymentsSettings,
) -> None:
    """Новая заметка — в бесплатном тарифе их ограниченное число."""
    if not await payment_service.can_create_note(message.from_user.id):
        await message.answer(
            note_limit_text(payments_settings.free_notes),
            reply_markup=kb.pay_button(payments_settings.price),
        )
        return
    note = await note_service.start_new_note(message.from_user.id)
    await _show_note(message, note_service, note.id)


# ---------- Удаление заметки ----------
@router.message(F.text == kb.MENU_DELETE_NOTE, StateFilter(None))
async def delete_note_start(message: Message, note_service: NoteService) -> None:
    """Удаление заметки из главного меню: подтверждаем и удаляем выбранную."""
    if await _need_note_choice(message, note_service):
        return
    note = await note_service.get_current_note(message.from_user.id)
    summary = await note_service.get_summary(note.id)
    if summary is None:
        await message.answer("Заметка не найдена.", reply_markup=kb.main_menu())
        return
    await message.answer(
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
    notes, has_next = await _history_page(note_service, user_id, 0)
    if not notes:
        await callback.message.edit_text(
            f"{text}\n\nНовая заметка создастся по кнопке «📝 Новая заметка».",
            reply_markup=None,
        )
        return
    await callback.message.edit_text(
        f"{text}\n\nВыберите заметку заново — из истории:",
        reply_markup=kb.history_menu(notes, 0, has_next),
    )


# ---------- Выбор заметки ----------
@router.message(F.text == kb.MENU_HISTORY, StateFilter(None))
async def history(message: Message, note_service: NoteService) -> None:
    notes, has_next = await _history_page(note_service, message.from_user.id, 0)
    if not notes:
        await message.answer("Заметок пока нет.", reply_markup=kb.main_menu())
        return
    await message.answer(
        history_text(),
        reply_markup=kb.history_menu(notes, 0, has_next),
    )


@router.callback_query(F.data.startswith("notepage:"))
async def history_page_cb(
    callback: CallbackQuery, note_service: NoteService
) -> None:
    """Прокрутка списка заметок кнопками «⬅️ Назад» / «Далее ➡️»."""
    page = _int_arg(callback.data, 1)
    if page is None or page < 0:
        await callback.answer("Неверный запрос.")
        return
    user_id = callback.from_user.id
    notes, has_next = await _history_page(note_service, user_id, page)
    # Заметок стало меньше, чем страниц: откатываемся к последней непустой.
    while page > 0 and not notes:
        page -= 1
        notes, has_next = await _history_page(note_service, user_id, page)
    if not notes:
        await callback.answer("Заметок пока нет.")
        return
    await callback.answer()
    await callback.message.edit_text(
        history_text(page),
        reply_markup=kb.history_menu(notes, page, has_next),
    )


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
    payment_service: PaymentService,
    payments_settings: PaymentsSettings,
) -> None:
    await user_service.register(message.from_user.id, message.from_user.username)
    if not await _has_goal(message, user_service, state):
        return
    if await _need_note_choice(message, note_service):
        return
    note = await note_service.get_current_note(message.from_user.id)
    if not await payment_service.can_add_meal(message.from_user.id, note.id):
        await message.answer(
            meal_limit_text(payments_settings.free_meals),
            reply_markup=kb.pay_button(payments_settings.price),
        )
        return
    text = message.text.strip()

    # «круассан 60 10,15,40» — точный расчёт без обращения к API.
    try:
        result = await food_service.try_add_exact(message.from_user.id, text)
    except FoodValueError:
        await message.answer(invalid_food_text(MAX_WEIGHT))
        return
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
    except FoodValueError:
        await processing.edit_text(invalid_food_text(MAX_WEIGHT))
        return
    except Exception:
        logger.exception("Ошибка при обращении к DeepSeek")
        await processing.edit_text("Не удалось распознать блюдо. Попробуйте ещё раз.")
        return

    await processing.edit_text(added_text(result))
    await _show_note(message, note_service, result.note.id)


# ---------- Удаление продукта ----------
@router.callback_query(F.data.startswith("delproduct:"))
async def delete_product_start(
    callback: CallbackQuery, note_service: NoteService
) -> None:
    """Удаление продукта кнопкой на карточке заметки."""
    summary = await _own_summary(callback, note_service)
    if summary is None:
        return
    if not summary.meals:
        await callback.answer("В этой заметке пока нечего удалять.")
        return
    await callback.answer()
    await callback.message.edit_text(
        delete_prompt_text(summary.meals),
        reply_markup=kb.delete_menu(summary.note.id, summary.meals),
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
