from __future__ import annotations

import math
from datetime import datetime

from bot.domain.models import AddFoodResult, DeleteMealResult, Food, Macros, NoteSummary

HELP_TEXT = (
    "👋 Я помогу следить за КБЖУ.\n\n"
    "Сначала задайте цель КБЖУ кнопкой «🎯 Цель КБЖУ».\n\n"
    "Чтобы начать новую заметку — нажмите «📝 Новая заметка».\n"
    "🍽️ Как добавлять еду — просто напишите сообщение:\n"
    "• «круассан 60» — 60 г круассана, КБЖУ подберу сам\n"
    "• «круассан 60 10,15,40» — 60 г круассана, БЖУ указаны на 100 г "
    "(для 60 г посчитаю сам)\n"
    "• «Экспонента 30 0 6.5» — продукт с итоговыми БЖУ на всю порцию "
    "(калории посчитаю сам)\n\n"
    "По кнопке «📂 Выбрать заметку» выбранная заметка становится активной: "
    "следующие продукты сохранятся в неё.\n\n"
    "Удалить лишнюю запись — кнопка «🗑 Удалить продукт» на карточке "
    "заметки, всю заметку — кнопка «🗑 Удалить заметку» в меню.\n\n"
    "💎 Кнопка «💎 Подписка» снимает лимиты на число заметок и записей; "
    "бесплатный тариф и статус подписки видны там же.\n\n"
    "❗️ Без заметки продукты не добавляются: первую создайте кнопкой "
    "«📝 Новая заметка», а если заметка не выбрана — выберите её из списка."
)

GOAL_PROMPT = (
    "Отправьте цель одним сообщением — белки/жиры/углеводы, "
    "например 120/60/220.\n"
    "Калории посчитаю по формуле Б×4 + Ж×9 + У×4."
)

NO_GOAL_TEXT = "❗️ Сначала создайте цель!"
NO_GOAL_PROMPT = f"{NO_GOAL_TEXT}\n\n{GOAL_PROMPT}"

DELETE_PROMPT = "🗑 Выберите продукт для удаления:"

SELECT_NOTE_PROMPT = "📅 Сначала выберите заметку — нажмите на нужную в списке ниже."

GRANT_USAGE = "Использование: /grant [user_id] [дней]"
REVOKE_USAGE = "Использование: /revoke [user_id]"


def history_text(page: int = 0) -> str:
    """Заголовок списка заметок: на первой странице — «последние»."""
    if page <= 0:
        return "📂 Последние заметки:"
    return f"📂 Заметки — страница {page + 1}:"

NO_NOTE_TEXT = "❗️ Сначала создайте новую заметку!"
NO_NOTE_PROMPT = (
    f"{NO_NOTE_TEXT}\n\n"
    "Заметок пока нет: нажмите «📝 Новая заметка», а затем напишите, что съели."
)


def fmt(value: float) -> str:
    if not math.isfinite(value):
        # inf/nan из старых записей: int() на них падает и роняет всю карточку
        return "—"
    return f"{value:.0f}" if value == int(value) else f"{value:.1f}"


def signed(value: float) -> str:
    return f"+{fmt(value)}" if value > 0 else fmt(value)


def macro_str(calories: float, protein: float, fat: float, carbs: float) -> str:
    return (
        f"{fmt(calories)} ккал "
        f"(Б {fmt(protein)} / Ж {fmt(fat)} / У {fmt(carbs)})"
    )


def macros_str(m: Macros) -> str:
    return macro_str(m.calories, m.protein, m.fat, m.carbs)


def food_str(f: Food) -> str:
    return macro_str(f.calories, f.protein, f.fat, f.carbs)


def added_text(result: AddFoodResult) -> str:
    text = f"✅ Добавлено: {result.food.name} — {food_str(result.food)}"
    if not result.is_latest:
        text += f"\n✏️ Записано в заметку {result.note.label}."
    return text


def deleted_text(result: DeleteMealResult) -> str:
    return f"🗑 Удалено: {result.food.name} — {food_str(result.food)}"


def confirm_note_delete_text(summary: NoteSummary) -> str:
    """Вопрос перед удалением заметки вместе с записями."""
    return (
        f"🗑 Удалить заметку {summary.note.label} вместе со всеми записями?\n"
        f"Записей: {len(summary.meals)} · итого {macros_str(summary.totals)}\n\n"
        "Действие нельзя отменить."
    )


def note_deleted_text(label: str) -> str:
    return f"🗑 Заметка {label} удалена."


def _date(value: str | None) -> str:
    """Дата из ISO-времени в формате ДД.ММ.ГГГГ."""
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(value).strftime("%d.%m.%Y")
    except ValueError:
        return value


def subscription_text(
    paid_until: str | None,
    active: bool,
    price: int,
    days: int,
    free_notes: int,
    free_meals: int,
) -> str:
    """Текст раздела «💎 Подписка»."""
    status = f"активна до {_date(paid_until)}" if active else "не активна"
    return (
        "💎 Подписка\n\n"
        f"Статус: {status}\n"
        f"Стоимость: {days} дней за {price} ⭐\n\n"
        f"Бесплатно: заметок — {free_notes} в сутки, "
        f"записей в каждой — до {free_meals}."
    )


def subscription_line(paid_until: str | None) -> str:
    """Строка статуса подписки для «ℹ️ Мой план»."""
    if paid_until is None:
        return "💎 Подписка: не активна"
    return f"💎 Подписка: до {_date(paid_until)}"


def note_limit_text(free_notes: int) -> str:
    """Paywall: закончились бесплатные заметки."""
    return (
        f"🔒 Бесплатно можно создать не больше {free_notes} заметок в сутки "
        "(удалённые тоже считаются). Новые будут доступны завтра.\n"
        "Подписка снимает лимит — оформить можно кнопкой ниже."
    )


def invalid_food_text(max_weight: float) -> str:
    """Вес или Б/Ж/У вне разумных пределов — запись не добавлена."""
    return (
        "⚠️ Слишком большие числа — запись не добавлена.\n"
        f"Вес порции — до {max_weight:g} г, Б/Ж/У на 100 г — не больше 100."
    )


def meal_limit_text(free_meals: int) -> str:
    """Paywall: закончились бесплатные записи в заметке."""
    return (
        f"🔒 В бесплатной заметке не больше {free_meals} записей.\n"
        "Подписка снимает лимит — оформить можно кнопкой ниже."
    )


def payment_success_text(paid_until: str) -> str:
    return f"✅ Оплата прошла!\n💎 Подписка активна до {_date(paid_until)}."


def granted_text(user_id: int, paid_until: str) -> str:
    return f"✅ Подписка {user_id} активна до {_date(paid_until)}."


def revoked_text(user_id: int) -> str:
    return f"🚫 Подписка {user_id} снята."


def not_found_text(query: str) -> str:
    """Продукт не распознан (found=false), запись не добавляется."""
    return (
        f"🤷 Продукт не найден: «{query}».\n"
        "Уточните название и вес — например «круассан 60» — "
        "или укажите вес и БЖУ на 100 г: «круассан 60 10,15,40»."
    )


def delete_prompt_text(meals: list[Food]) -> str:
    lines = [DELETE_PROMPT, ""]
    lines.extend(f"{i}. {m.name}" for i, m in enumerate(meals, 1))
    lines.append("")
    lines.append("Нажмите номер продукта на клавиатуре ниже.")
    return "\n".join(lines)


def build_note_text(summary: NoteSummary) -> str:
    lines = [f"📅 {summary.note.label}", ""]
    if summary.meals:
        for i, meal in enumerate(summary.meals, 1):
            lines.append(f"{i}. {meal.name} — {food_str(meal)}")
    else:
        lines.append("Записей пока нет.")
    lines.append("")
    lines.append(f"Итого: {macros_str(summary.totals)}")
    if summary.goal is not None:
        lines.append(f"Цель: {macros_str(summary.goal)}")
        diff_calories = summary.goal.calories - summary.totals.calories
        diff_protein = summary.goal.protein - summary.totals.protein
        diff_fat = summary.goal.fat - summary.totals.fat
        diff_carbs = summary.goal.carbs - summary.totals.carbs
        if diff_calories >= 0:
            lines.append(f"Осталось: {fmt(diff_calories)} ккал")
        else:
            lines.append(f"Превышение: {fmt(-diff_calories)} ккал")
        lines.append(
            f"Остаток Б/Ж/У: {signed(diff_protein)} / "
            f"{signed(diff_fat)} / {signed(diff_carbs)} г"
        )
    else:
        lines.append("Цель КБЖУ не задана — задайте её кнопкой «🎯 Цель КБЖУ».")
    text = "\n".join(lines)
    if not summary.is_latest:
        text += "\n\n✏️ Новые продукты будут добавляться в эту заметку."
    return text
