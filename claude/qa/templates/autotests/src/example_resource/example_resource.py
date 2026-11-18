"""example_resource.py — скопируйте этот модуль как основу для нового API-домена.

Паттерн:
  - один класс на ресурс
  - только статические методы (состояния нет — токены в HttpClient.access_folder)
  - каждый метод принимает status_code с ожидаемым успешным кодом;
    для негативных тестов передайте ожидаемый код ошибки:
        ExampleResource.get(999999, status_code=404)
        ExampleResource.create(name="", status_code=400)
    ВАЖНО: при ожидаемой ошибке метод возвращает None (тело ошибки может
    быть пустым/не-JSON) — не разыменовывайте результат
  - тело запроса переопределяется точечно через **kwargs (deep_merge)
  - параметр access — ключ токена в HttpClient.access_folder
  - ответы парсятся в pydantic-модели из models.py рядом с клиентом
    (тесты работают с атрибутами: resource.name, не resource['name']);
    тело ЗАПРОСА остаётся dict — модели только на ответы

Замените ExampleResource, пути URL и поля тела на свой реальный ресурс.
"""

from typing import Optional

import config
from src.deep_merge_json import deep_merge
from src.example_resource.models import ExampleResourceDto, ExampleResourcePageResult, ResponseId
from src.http_methods import HttpClient

BASE_URL = config.BASE_URL


class ExampleResource:

    @staticmethod
    def create(name: str = "Autotest Resource", status_code: int = 200, **kwargs) -> Optional[int]:
        """Создаёт ресурс. Возвращает id нового ресурса (None при негативном сценарии)."""
        default_body = {
            "name": name,
            "description": "Created by autotest"
        }
        body = deep_merge(default_body, kwargs)
        url = BASE_URL + "/api/example-resources"
        response = HttpClient.post(url, body, access="admin")
        # API может отвечать 200 или 201 на успешное создание
        expected = (200, 201) if status_code == 200 else (status_code,)
        assert response.status_code in expected, f"Создание не удалось: {response.text}"
        if status_code >= 400:
            # Ожидаемая ошибка: тело ошибки через модель НЕ прогонять —
            # JSON-ошибка тоже dict, model_validate упал бы с ValidationError
            return None
        data = HttpClient.parse_json(response)
        return ResponseId.model_validate(data).id if isinstance(data, dict) else None

    @staticmethod
    def get(resource_id: int, status_code: int = 200) -> Optional[ExampleResourceDto]:
        """Возвращает ресурс по id (модель; None при негативном сценарии)."""
        url = BASE_URL + f"/api/example-resources/{resource_id}"
        response = HttpClient.get(url, access="admin")
        assert response.status_code == status_code, f"Получение не удалось: {response.text}"
        if status_code >= 400:
            return None
        data = HttpClient.parse_json(response)
        return ExampleResourceDto.model_validate(data) if isinstance(data, dict) else None

    @staticmethod
    def get_list(page: int = 0, limit: int = 50, status_code: int = 200,
                 **query) -> Optional[ExampleResourcePageResult]:
        """Возвращает постраничный список ресурсов (модель-конверт).

        Доп. фильтры — именованными аргументами: get_list(search="имя").
        Query-строку НЕ собирать руками через f-строки — только
        query_params: requests сам кодирует пробелы/кириллицу/спецсимволы.
        """
        url = BASE_URL + "/api/example-resources"
        response = HttpClient.get(url, access="admin",
                                  query_params={"page": page, "limit": limit, **query})
        assert response.status_code == status_code, f"Получение списка не удалось: {response.text}"
        if status_code >= 400:
            return None
        data = HttpClient.parse_json(response)
        # Защитная догадка о конверте (Шаг 0.4 docs/api-layer.md): API может
        # отдавать голый массив ИЛИ конверт {"data": [...]}. Уточните реальную
        # структуру, поправьте PageResult и оставьте одну ветку.
        if isinstance(data, list):
            return ExampleResourcePageResult(
                data=[ExampleResourceDto.model_validate(item) for item in data])
        return ExampleResourcePageResult.model_validate(data) if isinstance(data, dict) else None

    @staticmethod
    def update(resource_id: int, status_code: int = 204, **kwargs) -> None:
        """Полное обновление (PUT): читает текущее состояние и накатывает kwargs.

        В негативном сценарии (status_code >= 400) предварительное чтение
        пропускается — иначе внутренний get() упал бы на своём 404 раньше,
        чем PUT: update(999999, status_code=404) шлёт kwargs как есть.

        Ловушка read-modify-write: model_dump() без параметров положит в
        тело PUT и id, и None всех Optional-полей — реальный API может это
        отвергнуть. exclude_none здесь — стартовое решение; что именно
        исключать, сверьте со своим API на живом стенде.
        """
        if status_code < 400:
            existing = ExampleResource.get(resource_id)
            existing_body = existing.model_dump(exclude_none=True) if existing else {}
            body = deep_merge(existing_body, kwargs)
        else:
            body = kwargs
        url = BASE_URL + f"/api/example-resources/{resource_id}"
        response = HttpClient.put(url, body, access="admin")
        assert response.status_code == status_code, f"Обновление не удалось: {response.text}"

    @staticmethod
    def partial_update(resource_id: int, status_code: int = 204, **kwargs) -> None:
        """Частичное обновление (PATCH) — отправляет только переданные поля."""
        url = BASE_URL + f"/api/example-resources/{resource_id}"
        response = HttpClient.patch(url, kwargs, access="admin")
        assert response.status_code == status_code, f"Частичное обновление не удалось: {response.text}"

    @staticmethod
    def delete(resource_id: int, status_code: int = 204) -> None:
        """Удаляет ресурс по id. Для негативного теста: delete(id, status_code=404)."""
        url = BASE_URL + f"/api/example-resources/{resource_id}"
        response = HttpClient.delete(url, access="admin")
        assert response.status_code == status_code, f"Удаление не удалось: {response.text}"
