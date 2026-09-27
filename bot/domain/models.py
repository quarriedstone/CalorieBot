from __future__ import annotations

from pydantic import BaseModel

# Калорийность макронутриентов (ккал/г).
CALORIES_PER_PROTEIN = 4.0
CALORIES_PER_FAT = 9.0
CALORIES_PER_CARB = 4.0


class Macros(BaseModel):
    """Калории и БЖУ без названия (цель, итоги заметки)."""

    calories: float
    protein: float
    fat: float
    carbs: float

    @classmethod
    def from_nutrients(cls, protein: float, fat: float, carbs: float) -> Macros:
        """Собрать КБЖУ, посчитав калории по формуле Б×4 + Ж×9 + У×4."""
        return cls(
            calories=(
                protein * CALORIES_PER_PROTEIN
                + fat * CALORIES_PER_FAT
                + carbs * CALORIES_PER_CARB
            ),
            protein=protein,
            fat=fat,
            carbs=carbs,
        )


class Food(Macros):
    """Блюдо с названием и КБЖУ."""

    name: str


class Meal(Food):
    """Блюдо из заметки: КБЖУ, id записи и заметка, к которой она относится."""

    id: int
    note_id: int


class NoteInfo(BaseModel):
    """Заметка: дата, название и владелец."""

    id: int
    user_id: int
    date: str
    label: str


class User(BaseModel):
    """Пользователь: имя, цель КБЖУ и выбранная заметка."""

    id: int
    username: str | None = None
    goal: Macros | None = None
    active_note_id: int | None = None


class NoteSummary(BaseModel):
    """Сводка заметки: блюда, итоги, цель и признак «последняя ли она»."""

    note: NoteInfo
    meals: list[Meal]
    totals: Macros
    goal: Macros | None = None
    is_latest: bool


class AddFoodResult(BaseModel):
    """Результат добавления блюда."""

    food: Food
    note: NoteInfo
    is_latest: bool


class DeleteMealResult(BaseModel):
    """Результат удаления блюда: что удалили и обновлённая сводка заметки."""

    food: Food
    summary: NoteSummary


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
        return Macros.from_nutrients(self.protein, self.fat, self.carbs)
