from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Ты — ассистент-диетолог. Пользователь описывает, что он съел (продукт или блюдо). "
    "Твоя задача — определить название блюда и его КБЖУ "
    "(калории, белки, жиры, углеводы) на съеденную порцию.\n"
    "\n"
    "Понимай следующие форматы ввода:\n"
    "1. «название вес» — например «круассан 60»: 60 — это вес порции в граммах, "
    "верни КБЖУ именно для 60 г.\n"
    "2. «название вес Б,Ж,У» — например «круассан 60 10,15,40»: 60 — вес порции в граммах, "
    "а 10,15,40 — белки, жиры и углеводы на 100 г продукта. Пересчитай КБЖУ на указанный вес.\n"
    "3. Если явно указаны калории или КБЖУ — используй эти числа, "
    "а недостающие значения оцени по составу.\n"
    "\n"
    "Отвечай ТОЛЬКО валидным JSON без пояснений, строго в таком формате:\n"
    '{"name": "Название блюда", "calories": 100, "protein": 10, "fat": 5, "carbs": 15}\n'
    "Единицы: calories — ккал, protein/fat/carbs — граммы. "
    "Если указан вес порции, добавь его в название, например «Круассан (60 г)»."
)


class DeepSeekParser:
    """Адаптер к DeepSeek API (OpenAI-совместимый клиент)."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    async def parse_food(
        self,
        text: str,
        weight_hint: float | None = None,
    ) -> dict[str, Any]:
        user_content = text
        if weight_hint is not None:
            user_content = (
                f"{text}\n\n"
                f"[Уточнение: {weight_hint:g} — это вес порции в граммах. "
                f"Верни КБЖУ именно для {weight_hint:g} г.]"
            )

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("DeepSeek вернул невалидный JSON: %s", content)
            data = {}

        return {
            "name": str(data.get("name", "")).strip() or "Блюдо",
            "calories": _to_num(data.get("calories")),
            "protein": _to_num(data.get("protein")),
            "fat": _to_num(data.get("fat")),
            "carbs": _to_num(data.get("carbs")),
        }


def _to_num(value: Any) -> float:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 0.0
