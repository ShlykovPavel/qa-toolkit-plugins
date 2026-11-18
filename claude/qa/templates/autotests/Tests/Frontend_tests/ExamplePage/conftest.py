"""conftest.py для фронтенд-тестов ExamplePage (ШАБЛОН).

Фикстуры, специфичные для этой страницы. Общие для всех фронтенд-тестов
(driver, скриншот-хук) — в Tests/Frontend_tests/conftest.py.
"""

import pytest

import config
from frontend.front_keys.example_service.example_admin_page_keys import ExampleAdminPage


@pytest.fixture()
def example_admin_page(driver):
    """Открывает админку по FRONTEND_BASE_URL и возвращает её page object.

    Драйвер создаётся только внутри function-фикстуры (через параметр
    driver) — на уровне импорта/класса браузер не поднимается, иначе
    коллекция тестов падала бы без установленного Chrome.
    """
    driver.get(config.FRONTEND_BASE_URL)
    return ExampleAdminPage(driver)
