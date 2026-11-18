"""conftest.py для примеров многошаговых сценариев."""

import pytest

from src.example_resource.example_resource import ExampleResource
from src.teardown_utils import report_teardown_failure


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
