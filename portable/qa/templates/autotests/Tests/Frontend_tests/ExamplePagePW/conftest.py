"""conftest.py для фронтенд-тестов ExamplePagePW (ШАБЛОН, playwright-ветка).

Вся директория пропускается на коллекции, если playwright не установлен
(importorskip ниже) — selenium-веткам форков опциональный довесок
requirements-playwright.txt не нужен.

Инфраструктурные фикстуры (page, context, browser) даёт плагин
pytest-playwright — своя driver-фабрика ветке не нужна. Headless — его
дефолт; браузер выбирается флагом `--browser chromium|firefox|webkit`.
"""

import pytest

pytest.importorskip("playwright", reason="playwright-ветка: поставьте requirements-playwright.txt")

import config
from frontend.pw_keys.example_service.example_admin_page_pw import ExampleAdminPagePw


@pytest.fixture()
def example_admin_page_pw(page):
    """Открывает админку по FRONTEND_BASE_URL, возвращает её page object."""
    page.goto(config.FRONTEND_BASE_URL)
    return ExampleAdminPagePw(page)
