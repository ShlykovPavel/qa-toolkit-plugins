"""models.py — pydantic-модели ответов домена (эталон: копируйте вместе
с клиентом при создании нового домена).

Правила (подробно — docs/api-layer.md, «Модели ответов (pydantic)»):
  - модель на каждую схему ответа, которую клиент отдаёт вызывающему коду;
  - имена полей — КАК В СПЕКЕ (обычно camelCase), без перевода в
    snake_case: модель обязана совпадать с JSON 1-в-1;
  - общие конвенции API (ResponseId, PageResult, ...) — импорт из
    src/common_models.py, НЕ копия;
  - тело запроса остаётся dict — модели только на ответы.
"""

from typing import Optional

from pydantic import BaseModel

from src.common_models import PageResult, ResponseId

__all__ = ["ExampleResourceDto", "ExampleResourcePageResult", "ResponseId"]


class ExampleResourceDto(BaseModel):
    """Ответ GET /api/example-resources/{id} — карточка ресурса.

    Обязательность полей — по спеке ресурса: то, что API может не вернуть,
    помечайте Optional со значением по умолчанию, иначе парсинг упадёт.
    """

    id: int
    name: str
    description: Optional[str] = None


ExampleResourcePageResult = PageResult[ExampleResourceDto]
"""Конверт списка GET /api/example-resources (см. догадку в PageResult)."""
