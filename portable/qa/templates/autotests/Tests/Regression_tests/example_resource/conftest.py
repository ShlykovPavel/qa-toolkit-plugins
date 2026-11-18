"""conftest.py для регрессионных тестов example_resource.

Фикстуры, специфичные для этого домена. Общие — в Tests/conftest.py.
"""

import pytest

from src.data_generators import generate_name
from src.example_resource.example_resource import ExampleResource
from src.teardown_utils import report_teardown_failure


@pytest.fixture()
def create_resource():
    """Создаёт ресурс до теста, возвращает его id, удаляет после.

    Имя всегда уникальное (generate_name) — обязательное условие
    параллельного прогона. Teardown терпим к 404: тесты удаления сами
    удаляют ресурс — повторное удаление не должно ронять тест.
    """
    resource_id = ExampleResource.create(name=generate_name("regression_resource"))
    yield resource_id
    try:
        ExampleResource.delete(resource_id)
    except Exception as e:
        report_teardown_failure(f"ресурс {resource_id} не удалён: {e}")


@pytest.fixture()
def resource_cleaner():
    """Собирает id ресурсов, созданных прямо в тесте, и удаляет их в teardown."""
    created_ids = []
    yield created_ids
    for resource_id in created_ids:
        try:
            ExampleResource.delete(resource_id)
        except Exception as e:
            report_teardown_failure(f"ресурс {resource_id} не удалён: {e}")
