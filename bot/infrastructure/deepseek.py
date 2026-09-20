from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI
from openai.types.responses import ResponseFormatTextJSONSchemaConfigParam

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Ты — ассистент-диетолог. Пользователь описывает, что он съел (продукт или блюдо). "
    "Твоя задача — понять, является ли ввод продуктом питания, и оценить его КБЖУ "
    "(калории, белки, жиры, углеводы) на съеденную порцию.\n"
    "\n"
    "Форматы ввода:\n"
    "1. «название вес» — например «круассан 60»: 60 — это вес порции в граммах, "
    "верни КБЖУ именно для 60 г.\n"
    "2. «название вес Б,Ж,У» — например «круассан 60 10,15,40»: 60 — вес порции в граммах, "
    "а 10,15,40 — белки, жиры и углеводы на 100 г продукта. Пересчитай КБЖУ на этот вес.\n"
    "3. «название Б,Ж,У» — например «експонента 30 0 6.5»: вес не указан, "
    "три числа — это белки, жиры и углеводы на всю порцию.\n"
    "4. Свободное описание — например «овсянка на молоке, 300 ккал»: оцени блюдо целиком.\n"
    "5. Если явно указаны калории или КБЖУ — используй эти числа, "
    "а недостающие значения оцени по составу.\n"
    "\n"
    "Когда ставить found = false:\n"
    "- ввод не является продуктом питания или блюдом: имя, город, бренд без продукта, "
    "случайный набор букв (например, «Москва», «Ыропа», «абракадабра»);\n"
    "- такого продукта или блюда не существует либо ты его не знаешь.\n"
    "НИКОГДА не выдумывай продукт и не подбирай КБЖУ наугад. При found = false: "
    'name = "", calories/protein/fat/carbs = 0, confidence = 0, '
    "reason — коротко почему.\n"
    "\n"
    "confidence (0–100) — уверенность именно в КБЖУ, а не в том, что это еда:\n"
    "- 90–100 — продукт широко известен или состав указан пользователем точно;\n"
    "- 50–89 — блюдо узнаваемо, но состав варьируется (салаты, домашняя готовка);\n"
    "- 1–49 — оценка грубая, продукт известен плохо;\n"
    "- 0 — КБЖУ неизвестны (found = false).\n"
    "\n"
    "reason — короткое пояснение к оценке (например, «точный состав указан пользователем», "
    "«блюдо с плавающим составом», «не продукт питания»).\n"
    "Единицы: calories — ккал, protein/fat/carbs — граммы. "
    "Если указан вес порции, добавь его в название, например «Круассан (60 г)». "
    "Если found = true, поле name не должно быть пустым."
)

# Строгая JSON-схема ответа (Responses API: text.format = json_schema).
FOOD_ESTIMATE_FORMAT: ResponseFormatTextJSONSchemaConfigParam = {
    "type": "json_schema",
    "name": "food_estimate",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "found",
            "name",
            "calories",
            "protein",
            "fat",
            "carbs",
            "confidence",
            "reason",
        ],
        "properties": {
            "found": {
                "type": "boolean",
                "description": "true — продукт или блюдо узнано; false — это не еда",
            },
            "name": {
                "type": "string",
                "description": "Название блюда с весом; при found=false пустая строка",
            },
            "calories": {"type": "number", "description": "ккал на порцию"},
            "protein": {"type": "number", "description": "белки, г"},
            "fat": {"type": "number", "description": "жиры, г"},
            "carbs": {"type": "number", "description": "углеводы, г"},
            "confidence": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "уверенность в КБЖУ, 0–100",
            },
            "reason": {
                "type": "string",
                "description": "короткое пояснение к оценке",
            },
        },
    },
}


class DeepSeekParser:
    """Адаптер к DeepSeek API (OpenAI-совместимый клиент)."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-flash",
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    async def parse_food(
        self,
        text: str,
        weight_hint: float | None = None,
    ) -> dict[str, Any]:
        """Оценить блюдо через Responses API.

        Возвращает found/name/calories/protein/fat/carbs/confidence/reason.
        ``found=False`` означает, что ввод не является продуктом питания.
        """
        user_content = text
        if weight_hint is not None:
            user_content = (
                f"{text}\n\n"
                f"[Уточнение: {weight_hint:g} — это вес порции в граммах. "
                f"Верни КБЖУ именно для {weight_hint:g} г.]"
            )

        response = await self._client.responses.create(
            model=self._model,
            instructions=SYSTEM_PROMPT,
            input=user_content,
            temperature=0.1,
            text={"format": FOOD_ESTIMATE_FORMAT},
        )
        raw = response.output_text
        logger.info("Сырой ответ DeepSeek на %r: %s", text, raw)
        if response.status != "completed":
            logger.warning(
                "Ответ DeepSeek не завершён: status=%s error=%s",
                response.status,
                response.error,
            )
            raise RuntimeError(f"DeepSeek: status={response.status}")

        content = raw or "{}"
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("Ответ DeepSeek не является валидным JSON")
            data = {}

        return {
            "found": bool(data.get("found", False)),
            "name": str(data.get("name") or "").strip() or "Блюдо",
            "calories": _to_num(data.get("calories")),
            "protein": _to_num(data.get("protein")),
            "fat": _to_num(data.get("fat")),
            "carbs": _to_num(data.get("carbs")),
            "confidence": _to_confidence(data.get("confidence")),
            "reason": str(data.get("reason") or "").strip(),
        }


def _to_num(value: Any) -> float:
    """Число из ответа модели; отсутствующее поле — 0, нечисловое — лог."""
    if value is None:
        return 0.0
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        logger.warning("Не удалось разобрать число из ответа DeepSeek: %r", value)
        return 0.0


def _to_confidence(value: Any) -> int:
    """Уверенность 0–100; отсутствующее или нечисловое значение — 0."""
    if value is None:
        return 0
    try:
        return max(0, min(100, int(float(value))))
    except (TypeError, ValueError):
        logger.warning("Не удалось разобрать confidence: %r", value)
        return 0
