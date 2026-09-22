"""Временный скрипт проверки объединения повторов блюда (удалить после прогона)."""

import asyncio

from bot.domain.services import FoodService
from bot.infrastructure.db import Database

USER = 1


class StubDeepSeek:
    """Заглушка модели: считает вызовы и возвращает предсказуемое название."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, float | None]] = []

    async def parse_food(self, text: str, weight_hint: float | None = None):
        self.calls.append((text, weight_hint))
        name = text.split()[0].capitalize()
        if weight_hint is not None:
            name = f"{name} ({weight_hint:g} г)"
        return {
            "found": True,
            "name": name,
            "calories": 200.0,
            "protein": 4.0,
            "fat": 10.0,
            "carbs": 22.0,
        }


FAILED = False


def check(label: str, condition: bool, extra: str = "") -> None:
    global FAILED
    if not condition:
        FAILED = True
    print(f"[{'OK  ' if condition else 'FAIL'}] {label} {extra}")


def show(result) -> None:
    print(
        f"       {result.food.name} | {result.food.calories:.1f} ккал "
        f"Б{result.food.protein:.1f} Ж{result.food.fat:.1f} У{result.food.carbs:.1f} "
        f"| merged={result.merged} added={result.added_weight}"
    )


def near(value: float, expected: float) -> bool:
    return abs(value - expected) < 1e-6


async def dump(db: Database, day_id: int) -> None:
    rows = await db.get_meals(day_id)
    print(f"       в БД строк: {len(rows)}")
    for row in rows:
        print(
            f"         #{row['id']} {row['name']!r} weight={row['weight']} "
            f"ккал={row['calories']:.1f}"
        )


async def main() -> None:
    db = Database(":memory:")
    await db.init()
    ai = StubDeepSeek()
    food = FoodService(db, ai)
    day_id = await db.get_target_day(USER, "2026-09-22")

    print("\n1. Точный ввод с весом и Б/Ж/У на 100 г — новая запись")
    result = await food.try_add_exact(USER, "круассан 60 10,15,40")
    assert result is not None
    show(result)
    check("новая строка, вес в названии", not result.merged and result.food.name == "Круассан (60 г)")
    check("КБЖУ для 60 г", near(result.food.calories, 201.0) and near(result.food.protein, 6.0))
    check("API не вызван", not ai.calls)

    print("\n2. Тот же ввод снова — вес и плотность из нового сообщения")
    result = await food.try_add_exact(USER, "круассан 60 10,15,40")
    assert result is not None
    show(result)
    check("объединено", result.merged and result.added_weight == 60.0)
    check("суммарный вес в названии", result.food.name == "Круассан (120 г)")
    check("КБЖУ по новой плотности", near(result.food.calories, 402.0) and near(result.food.protein, 12.0))
    check("API не вызван", not ai.calls)

    print("\n3. «круассан 40» — вес без Б/Ж/У, плотность из существующей записи")
    result = await food.try_add_exact(USER, "круассан 40")
    assert result is not None
    show(result)
    check("объединено без API", result.merged and not ai.calls)
    check("вес 160 г", result.food.name == "Круассан (160 г)" and result.added_weight == 40.0)
    check("КБЖУ пропорционально весу", near(result.food.calories, 536.0) and near(result.food.carbs, 64.0))

    print("\n4. Порционный формат — новая запись, повтор суммируется")
    result = await food.try_add_exact(USER, "Овсянка 30 5 40")
    assert result is not None
    show(result)
    check("новая порция", not result.merged and result.food.name == "Овсянка")
    check("КБЖУ порции", near(result.food.calories, 325.0))
    result = await food.try_add_exact(USER, "Овсянка 30 5 40")
    assert result is not None
    show(result)
    check("порции суммируются", result.merged and result.added_weight is None and near(result.food.calories, 650.0))

    print("\n5. Голое «овсянка» — ещё одна такая же порция, без API")
    result = await food.try_add_exact(USER, "овсянка")
    assert result is not None
    show(result)
    check("порция прибавлена без API", result.merged and not ai.calls and near(result.food.calories, 1300.0))
    check("название не изменилось", result.food.name == "Овсянка")

    print("\n6. «овсянка 200» при порционной записи — типы не совпадают")
    check("локального совпадения нет", await food.try_add_exact(USER, "овсянка 200") is None)
    result = await food.add_via_ai(USER, "овсянка 200")
    show(result)
    check("модель вызвана", len(ai.calls) == 1 and ai.calls[0] == ("овсянка 200", 200.0))
    check("отдельная запись с весом", not result.merged and result.food.name == "Овсянка (200 г)")

    print("\n7. Старая запись (вес только в названии) тоже объединяется")
    await db.add_meal(day_id, "Банан (150 г)", 135.0, 1.5, 0.3, 30.0)
    result = await food.try_add_exact(USER, "банан 50")
    assert result is not None
    show(result)
    check("объединено", result.merged and result.food.name == "Банан (200 г)")
    check("КБЖУ по плотности старой записи", near(result.food.calories, 180.0) and near(result.food.carbs, 40.0))

    print("\n8. Новое блюдо без совпадения — модель + отдельная строка")
    before = len(ai.calls)
    result = await food.add_via_ai(USER, "пицца 100")
    show(result)
    check("модель вызвана", len(ai.calls) == before + 1)
    check("новая строка", not result.merged and result.food.name == "Пицца (100 г)")

    print("\n9. Нет заметок — поиск повтора не создаёт заметку")
    other = 2
    calls_before = len(ai.calls)
    check("совпадения нет, модель не нужна", await food.try_add_exact(other, "овсянка") is None)
    check("заметка не создана", not await db.get_last_days(other, 5))
    check("API не вызван", len(ai.calls) == calls_before)

    print("\n10. Слияние идёт только в активной заметке")
    old_day = await db.create_day(USER, "2026-09-19")
    await db.set_active_day(USER, old_day)
    check("в пустой заметке совпадения нет", await food.try_add_exact(USER, "банан 100") is None)
    await db.add_meal(old_day, "Банан (150 г)", 135.0, 1.5, 0.3, 30.0)
    result = await food.try_add_exact(USER, "банан 100")
    assert result is not None
    show(result)
    check("слияние в выбранной заметке", result.merged and result.day.id == old_day)
    check("вес 250 г", result.food.name == "Банан (250 г)")
    check("КБЖУ по плотности", near(result.food.calories, 225.0) and near(result.food.carbs, 50.0))

    print("\nИтог в заметке:")
    await dump(db, day_id)
    await db.shutdown()
    print("\nРЕЗУЛЬТАТ:", "ЕСТЬ ОШИБКИ" if FAILED else "все проверки пройдены")
    raise SystemExit(1 if FAILED else 0)


asyncio.run(main())
