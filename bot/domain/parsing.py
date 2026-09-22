from __future__ import annotations

import re

from pydantic import BaseModel

from bot.domain.models import Macros

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

# Вес в хвосте названия: «Круассан (60 г)» или «Круассан 60 г».
_NAME_WEIGHT_RE = re.compile(
    r"[(\s]\s*(?P<weight>\d+(?:[.,]\d+)?)\s*г\.?\s*\)?\s*$",
    re.IGNORECASE,
)

# Калорийность макронутриентов (ккал/г).
CALORIES_PER_PROTEIN = 4.0
CALORIES_PER_FAT = 9.0
CALORIES_PER_CARB = 4.0


class StructuredFood(BaseModel):
    """Разобранный ввод вида «название вес [Б,Ж,У на 100 г]»."""

    name: str
    weight: float
    protein_100: float | None = None
    fat_100: float | None = None
    carbs_100: float | None = None

    @property
    def per100(self) -> tuple[float, float, float] | None:
        """Б/Ж/У на 100 г или None, если указаны не все три."""
        if self.protein_100 is None or self.fat_100 is None or self.carbs_100 is None:
            return None
        return (self.protein_100, self.fat_100, self.carbs_100)


class PortionFood(BaseModel):
    """Разобранный ввод вида «название Б,Ж,У» — КБЖУ на всю порцию."""

    name: str
    protein: float
    fat: float
    carbs: float

    @property
    def macros(self) -> Macros:
        """КБЖУ порции с калориями по формуле Б×4 + Ж×9 + У×4."""
        return Macros(
            calories=calories_from_macros(self.protein, self.fat, self.carbs),
            protein=self.protein,
            fat=self.fat,
            carbs=self.carbs,
        )


def calories_from_macros(protein: float, fat: float, carbs: float) -> float:
    """Калории по формуле Б×4 + Ж×9 + У×4."""
    return (
        protein * CALORIES_PER_PROTEIN
        + fat * CALORIES_PER_FAT
        + carbs * CALORIES_PER_CARB
    )


def totals_from_per100(
    weight: float,
    protein_100: float,
    fat_100: float,
    carbs_100: float,
) -> Macros:
    """Пересчитать БЖУ с 100 г на фактический вес порции."""
    factor = weight / 100.0
    protein = protein_100 * factor
    fat = fat_100 * factor
    carbs = carbs_100 * factor
    return Macros(
        calories=calories_from_macros(protein, fat, carbs),
        protein=protein,
        fat=fat,
        carbs=carbs,
    )


def display_name(name: str, weight: float | None = None) -> str:
    """Привести название к виду «Круассан (60 г)»."""
    cleaned = name.strip().rstrip(".,;:!?-—–").strip()
    if cleaned:
        label = cleaned[:1].upper() + cleaned[1:]
    else:
        label = "Блюдо"
    if weight is not None:
        label = f"{label} ({weight:g} г)"
    return label


def _to_num(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value.replace(",", "."))
    except ValueError:
        return None


def _unwrap_brackets(text: str) -> str:
    """Убрать скобки вокруг чисел: «Экспонента (30/0/6,5)» → «... 30/0/6,5».

    Скобки с нечисловым содержимым не трогаем — они могут быть частью названия.
    """

    def _replace(match: re.Match[str]) -> str:
        inner = match.group("inner").strip()
        if not inner or _NUMERIC_INNER_RE.fullmatch(inner) is None:
            return match.group(0)
        return f" {inner} "

    return re.sub(r"\s+", " ", _BRACKET_RE.sub(_replace, text)).strip()


def numbers_outside_brackets(text: str) -> bool:
    """Есть ли в тексте числа вне скобок.

    «круассан 60 (10/15/40)» — да (вес снаружи), «Экспонента (30 0 6,5)» — нет:
    такой ввод читается как Б/Ж/У на порцию, а не как вес.
    """
    return re.search(r"\d", _BRACKET_RE.sub(" ", text)) is not None


def weight_from_name(name: str) -> float | None:
    """Вес из хвоста названия: «Круассан (60 г)» → 60."""
    match = _NAME_WEIGHT_RE.search(name)
    if match is None:
        return None
    return _to_num(match.group("weight"))


def base_name(name: str) -> str:
    """Название без хвостового веса: «Круассан (60 г)» → «Круассан»."""
    match = _NAME_WEIGHT_RE.search(name)
    base = name[: match.start()] if match is not None else name
    return base.strip().rstrip(".,;:!?-—–").strip()


def match_key(name: str) -> str:
    """Ключ для поиска повторов: название без веса, регистра и лишних пробелов."""
    base = base_name(name).lower().replace("ё", "е")
    return re.sub(r"\s+", " ", base).strip(" .,;:!?—-–")


def parse_structured(text: str) -> StructuredFood | None:
    """Разобрать «название вес [Б,Ж,У]".

    Возвращает None, если текст не подходит под формат (тогда его обрабатывает
    DeepSeek как свободное описание). Если указан только вес —
    ``per100`` будет None, а КБЖУ подберёт модель.
    """
    match = _STRUCTURED_RE.match(_unwrap_brackets(text))
    if match is None:
        return None

    name = match.group("name").strip()
    weight = _to_num(match.group("weight"))
    if not name or weight is None or weight <= 0:
        return None

    protein = _to_num(match.group("p"))
    fat = _to_num(match.group("f"))
    carbs = _to_num(match.group("c"))
    if protein is None or fat is None or carbs is None:
        return StructuredFood(name=name, weight=weight)

    return StructuredFood(
        name=name,
        weight=weight,
        protein_100=protein,
        fat_100=fat,
        carbs_100=carbs,
    )


def parse_portion(text: str) -> PortionFood | None:
    """Разобрать «название Б,Ж,У» — Б/Ж/У на всю порцию, без веса.

    Возвращает None, если текст не в этом формате.
    """
    match = _PORTION_RE.match(_unwrap_brackets(text))
    if match is None:
        return None

    name = match.group("name").strip()
    protein = _to_num(match.group("p"))
    fat = _to_num(match.group("f"))
    carbs = _to_num(match.group("c"))
    if not name or protein is None or fat is None or carbs is None:
        return None
    if not any(char.isalpha() for char in name):
        # «1 2 3 4» — это не название продукта, такой ввод разбирает модель
        return None

    return PortionFood(name=name, protein=protein, fat=fat, carbs=carbs)


class FoodInput(BaseModel):
    """Разобранный ввод еды: название, вес, КБЖУ (если считаются локально).

    ``weight`` известен только тогда, когда вес указан в самом сообщении;
    ``macros`` — только когда КБЖУ не требует обращения к модели;
    ``per100`` — явные Б/Ж/У на 100 г (используются при объединении повторов).
    """

    name: str
    weight: float | None = None
    macros: Macros | None = None
    per100: tuple[float, float, float] | None = None
    display: str | None = None

    @property
    def key(self) -> str:
        """Ключ для поиска такого же блюда в заметке."""
        return match_key(self.name)

    @property
    def is_weight(self) -> bool:
        """Указан ли вес порции (иначе ввод считается «порцией»)."""
        return self.weight is not None


def parse_food_input(text: str) -> FoodInput:
    """Разобрать ввод еды в объединённый вид, не обращаясь к модели.

    Порядок разбора: «название вес Б,Ж,У» → «название Б,Ж,У» → «название вес» →
    название с весом в скобках → свободный текст. Для свободного текста
    ``macros`` и ``weight`` пустые: это описание разбирает модель.
    """
    structured = parse_structured(text)
    per100 = structured.per100 if structured is not None else None
    if structured is not None and per100 is not None and numbers_outside_brackets(text):
        return FoodInput(
            name=structured.name,
            weight=structured.weight,
            macros=totals_from_per100(structured.weight, *per100),
            per100=per100,
            display=display_name(structured.name, structured.weight),
        )

    portion = parse_portion(text)
    if portion is not None:
        return FoodInput(
            name=portion.name,
            macros=portion.macros,
            display=display_name(portion.name),
        )

    if structured is not None:
        # «название вес»: КБЖУ подберёт модель либо возьмёт из совпавшей записи
        return FoodInput(
            name=structured.name,
            weight=structured.weight,
            display=display_name(structured.name, structured.weight),
        )

    raw = text.strip()
    weight = weight_from_name(raw)
    base = base_name(raw) if weight is not None else raw
    if weight is not None and any(char.isalpha() for char in base):
        # «овсянка (300 г)»: вес указан в скобках, КБЖУ подберёт модель
        return FoodInput(
            name=base,
            weight=weight,
            display=display_name(base, weight),
        )
    return FoodInput(name=raw)


def _goal_numbers(text: str, separators: str) -> list[float] | None:
    parts = [p for p in re.split(separators, text) if p]
    if len(parts) != 3:
        return None
    try:
        return [float(p.replace(",", ".")) for p in parts]
    except ValueError:
        return None


def parse_goal(text: str) -> Macros | None:
    """Разобрать цель вида «Б/Ж/У», например «120/60/220».

    Возвращает Macros либо None. Калории считаются по формуле
    Б×4 + Ж×9 + У×4.
    """
    text = text.strip()
    # «120/60/220», «120 60 220» — запятая внутри числа = разделитель дробей
    values = _goal_numbers(text, r"[\s/|;]+")
    if values is None:
        # «120,60,220» — запятая как разделитель
        values = _goal_numbers(text, r"\s*,\s*")
    if values is None or any(v < 0 for v in values):
        return None
    protein, fat, carbs = values
    return Macros(
        calories=calories_from_macros(protein, fat, carbs),
        protein=protein,
        fat=fat,
        carbs=carbs,
    )
