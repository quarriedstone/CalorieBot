from __future__ import annotations

from bot.domain.models import AddFoodResult, DaySummary, DeleteMealResult, Food, Macros

HELP_TEXT = (
    "Я помогу следить за КБЖУ.\n\n"
    "Как добавлять еду — просто напишите сообщение:\n"
    "• «круассан 60» — 60 г, КБЖУ подберу сам\n"
    "• «круассан 60 10,15,40» — 60 г, БЖУ указаны на 100 г (посчитаю точно)\n"
    "• «Экспонента 30 0 6.5» — БЖУ на всю порцию (посчитаю точно)\n"
    "• «овсянка на молоке, 300 ккал» — свободное описание\n\n"
    "Заметка, открытая из истории, становится активной: следующие продукты "
    "сохранятся в неё.\n\n"
    "Удалить лишнюю запись — кнопка «🗑 Удалить продукт», всю заметку — "
    "«🗑 Удалить заметку» на карточке заметки.\n\n"
    "Пока заметка не выбрана, продукты не добавляются: выберите её из списка.\n\n"
    "Сначала задайте цель КБЖУ кнопкой «🎯 Цель КБЖУ»."
)

GOAL_PROMPT = (
    "Отправьте цель одним сообщением — белки/жиры/углеводы, "
    "например 120/60/220.\n"
    "Калории посчитаю по формуле Б×4 + Ж×9 + У×4."
)

DELETE_PROMPT = "🗑 Выберите продукт для удаления:"

SELECT_DAY_PROMPT = "📅 Сначала выберите заметку — нажмите на нужную в списке ниже."


def fmt(value: float) -> str:
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
        text += f"\n✏️ Записано в заметку {result.day.label}."
    return text


def deleted_text(result: DeleteMealResult) -> str:
    return f"🗑 Удалено: {result.food.name} — {food_str(result.food)}"


def confirm_day_delete_text(summary: DaySummary) -> str:
    """Вопрос перед удалением заметки вместе с записями."""
    return (
        f"🗑 Удалить заметку {summary.day.label} вместе со всеми записями?\n"
        f"Записей: {len(summary.meals)} · итого {macros_str(summary.totals)}\n\n"
        "Действие нельзя отменить."
    )


def day_deleted_text(label: str) -> str:
    return f"🗑 Заметка {label} удалена."


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


def build_day_text(summary: DaySummary) -> str:
    lines = [f"📅 {summary.day.label}", ""]
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
