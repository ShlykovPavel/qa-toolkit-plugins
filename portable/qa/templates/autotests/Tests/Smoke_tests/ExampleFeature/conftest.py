"""conftest.py для smoke-тестов ExampleFeature.

Фикстуры, специфичные для этой фичи. Общие для всех доменов — в Tests/conftest.py.
"""

import pytest

from src.data_generators import generate_name
from src.example_resource.example_resource import ExampleResource
from src.teardown_utils import report_teardown_failure


@pytest.fixture()
def smoke_resource():
    """Создаёт ресурс до теста, возвращает его id, удаляет после."""
    resource_id = ExampleResource.create(name=generate_name("smoke_resource"))
    yield resource_id
    try:
        ExampleResource.delete(resource_id)
    except Exception as e:
        report_teardown_failure(f"ресурс {resource_id} не удалён: {e}")


@pytest.fixture()
def resource_cleaner():
    """Собирает id ресурсов, созданных прямо в тесте, и удаляет их в teardown.

    Использование:
        def test_create(self, resource_cleaner):
            resource_id = ExampleResource.create(...)
            resource_cleaner.append(resource_id)
    """
    created_ids = []
    yield created_ids
    for resource_id in created_ids:
        try:
            ExampleResource.delete(resource_id)
        except Exception as e:
            report_teardown_failure(f"ресурс {resource_id} не удалён: {e}")
