"""Сервис блюд: точный расчёт по БЖУ или оценка через DeepSeek."""

from __future__ import annotations

import re

from bot.domain.models import (
    AddFoodResult,
    Food,
    Macros,
    PortionFood,
    StructuredFood,
)
from bot.domain.services.common import today
from bot.domain.services.interfaces import DatabaseInterface
from bot.infrastructure.adapters.deepseek import DeepSeekAdapter

__all__ = ["FoodNotFoundError", "FoodService"]

# Число: целое или дробное с запятой/точкой (60, 62.5, 82,5)
_NUM = r"\d+(?:[.,]\d+)?"
# Разделитель между Б, Ж и У: запятая, слэш или пробел(ы)
_SEP = r"(?:\s*[,/]\s*|\s+)"

# «название вес» или «название вес Б,Ж,У»,
# например «круассан 60» или «круассан 60 10,15,40».
_STRUCTURED_RE = re.compile(
    rf"^\s*(?P<name>.+?)\s+(?P<weight>{_NUM})"
    rf"(?:\s+(?P<p>{_NUM}){_SEP}(?P<f>{_NUM}){_SEP}(?P<c>{_NUM}))?\s*$",
)

# «название Б,Ж,У» — Б/Ж/У сразу на съеденную порцию, вес не указывается,
# например «Экспонента 30 0 6.5».
_PORTION_RE = re.compile(
    rf"^\s*(?P<name>.+?)\s+(?P<p>{_NUM}){_SEP}(?P<f>{_NUM}){_SEP}(?P<c>{_NUM})\s*$",
)

# Скобки вокруг чисел: «Экспонента (30/0/6,5)» → «Экспонента 30/0/6,5».
_BRACKET_RE = re.compile(r"[(\[]\s*(?P<inner>[^()\[\]]*?)\s*[)\]]")
# Внутри скобок допустимы только числа и разделители, иначе это часть названия.
_NUMERIC_INNER_RE = re.compile(r"[\d\s.,/]+")


class FoodNotFoundError(Exception):
    """DeepSeek не распознал продукт (found=false)."""

    def __init__(self, query: str) -> None:
        super().__init__(query)
        self.query = query


class FoodService:
    """Добавление блюда: точный расчёт по БЖУ или оценка через DeepSeek."""

    def __init__(self, db: DatabaseInterface, deepseek: DeepSeekAdapter) -> None:
        self._db = db
        self._deepseek = deepseek

    async def try_add_exact(self, user_id: int, text: str) -> AddFoodResult | None:
        """Точный расчёт по указанным Б/Ж/У, без обращения к API.

        Форматы:
        - «название вес Б,Ж,У» — Б/Ж/У на 100 г, пересчёт на указанный вес;
        - «название Б,Ж,У» — Б/Ж/У на всю порцию, вес не указывается.
        Числа целиком в скобках («Экспонента (30 0 6,5)») — это второй формат,
        даже если запятая в дроби выглядит как разделитель.

        Возвращает None, если текст не подходит ни под один формат.
        """
        structured = self._parse_structured(text)
        per100 = structured.per100 if structured is not None else None
        if (
            structured is not None
            and per100 is not None
            and self._numbers_outside_brackets(text)
        ):
            protein_100, fat_100, carbs_100 = per100
            name = self._display_name(structured.name, structured.weight)
            macros = self._totals_from_per100(
                structured.weight, protein_100, fat_100, carbs_100
            )
        else:
            portion = self._parse_portion(text)
            if portion is None:
                return None
            name = self._display_name(portion.name)
            macros = portion.macros
        return await self._store(
            user_id,
            Food(
                name=name,
                calories=macros.calories,
                protein=macros.protein,
                fat=macros.fat,
                carbs=macros.carbs,
            ),
        )

    async def add_via_ai(self, user_id: int, text: str) -> AddFoodResult:
        """Распознать свободное описание или «название вес» через DeepSeek.

        Название берётся из ответа модели. Если модель вернула found=false
        (это не продукт питания), бросает :class:`FoodNotFoundError` —
        запись в день не добавляется.
        """
        structured = self._parse_structured(text)
        weight_hint = structured.weight if structured is not None else None
        parsed = await self._deepseek.parse_food(text, weight_hint=weight_hint)
        if not parsed["found"]:
            raise FoodNotFoundError(text)
        food = Food(
            name=str(parsed["name"]),
            calories=float(parsed["calories"]),
            protein=float(parsed["protein"]),
            fat=float(parsed["fat"]),
            carbs=float(parsed["carbs"]),
        )
        return await self._store(user_id, food)

    # ---------- внутренние методы ----------
    async def _store(self, user_id: int, food: Food) -> AddFoodResult:
        day = await self._db.get_target_day(user_id, today())
        await self._db.add_meal(day.id, food)
        return AddFoodResult(
            food=food,
            day=day,
            is_latest=(await self._db.get_latest_day_id(user_id)) == day.id,
        )

    @staticmethod
    def _parse_structured(text: str) -> StructuredFood | None:
        """Разобрать «название вес [Б,Ж,У]».

        Возвращает None, если текст не подходит под формат (тогда его
        обрабатывает DeepSeek как свободное описание). Если указан только
        вес — ``per100`` будет None, а КБЖУ подберёт модель.
        """
        match = _STRUCTURED_RE.match(FoodService._unwrap_brackets(text))
        if match is None:
            return None

        name = match.group("name").strip()
        weight = FoodService._to_num(match.group("weight"))
        if not name or weight is None or weight <= 0:
            return None

        protein = FoodService._to_num(match.group("p"))
        fat = FoodService._to_num(match.group("f"))
        carbs = FoodService._to_num(match.group("c"))
        if protein is None or fat is None or carbs is None:
            return StructuredFood(name=name, weight=weight)

        return StructuredFood(
            name=name,
            weight=weight,
            protein_100=protein,
            fat_100=fat,
            carbs_100=carbs,
        )

    @staticmethod
    def _parse_portion(text: str) -> PortionFood | None:
        """Разобрать «название Б,Ж,У» — Б/Ж/У на всю порцию, без веса.

        Возвращает None, если текст не в этом формате.
        """
        match = _PORTION_RE.match(FoodService._unwrap_brackets(text))
        if match is None:
            return None

        name = match.group("name").strip()
        protein = FoodService._to_num(match.group("p"))
        fat = FoodService._to_num(match.group("f"))
        carbs = FoodService._to_num(match.group("c"))
        if not name or protein is None or fat is None or carbs is None:
            return None
        if not any(char.isalpha() for char in name):
            # «1 2 3 4» — это не название продукта, такой ввод разбирает модель
            return None

        return PortionFood(name=name, protein=protein, fat=fat, carbs=carbs)

    @staticmethod
    def _display_name(name: str, weight: float | None = None) -> str:
        """Привести название к виду «Круассан (60 г)»."""
        cleaned = name.strip().rstrip(".,;:!?-—–").strip()
        if cleaned:
            label = cleaned[:1].upper() + cleaned[1:]
        else:
            label = "Блюдо"
        if weight is not None:
            label = f"{label} ({weight:g} г)"
        return label

    @staticmethod
    def _totals_from_per100(
        weight: float,
        protein_100: float,
        fat_100: float,
        carbs_100: float,
    ) -> Macros:
        """Пересчитать БЖУ с 100 г на фактический вес порции."""
        factor = weight / 100.0
        return Macros.from_nutrients(
            protein_100 * factor,
            fat_100 * factor,
            carbs_100 * factor,
        )

    @staticmethod
    def _numbers_outside_brackets(text: str) -> bool:
        """Есть ли в тексте числа вне скобок.

        «круассан 60 (10/15/40)» — да (вес снаружи), «Экспонента (30 0 6,5)» —
        нет: такой ввод читается как Б/Ж/У на порцию, а не как вес.
        """
        return re.search(r"\d", _BRACKET_RE.sub(" ", text)) is not None

    @staticmethod
    def _unwrap_brackets(text: str) -> str:
        """Убрать скобки вокруг чисел: «Экспонента (30/0/6,5)» → «... 30/0/6,5».

        Скобки с нечисловым содержимым не трогаем — они могут быть частью
        названия.
        """

        def _replace(match: re.Match[str]) -> str:
            inner = match.group("inner").strip()
            if not inner or _NUMERIC_INNER_RE.fullmatch(inner) is None:
                return match.group(0)
            return f" {inner} "

        return re.sub(r"\s+", " ", _BRACKET_RE.sub(_replace, text)).strip()

    @staticmethod
    def _to_num(value: str | None) -> float | None:
        if value is None:
            return None
        try:
            return float(value.replace(",", "."))
        except ValueError:
            return None
