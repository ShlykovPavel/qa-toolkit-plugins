"""test_example_page.py — шаблон Selenium-теста страницы (ПРИМЕР).

В шаблоне фронтенд-тесты НЕ гоняются (нет живого стенда) — только
коллекция. Форк задаёт FRONTEND_BASE_URL в .env и запускает
`make frontend`.

Правила (см. docs/frontend.md и docs/tests.md):
  - селекторы снимаются с живой страницы (dump_dom.py), не выдумываются;
  - предусловия данных — через API-клиенты src/, не через UI;
  - каждый тест независим: свои данные, свой драйвер (function scope).

Скопируйте директорию и замените ExamplePage на свою страницу.
"""

import allure
import pytest

pytestmark = pytest.mark.frontend


@allure.epic("Frontend")
@allure.feature("ExamplePage")
class TestExamplePage:

    @allure.description("Сценарий создания сущности через форму админки")
    def test_create_item_via_form(self, example_admin_page):
        page = example_admin_page

        with allure.step("Открыть форму создания"):
            page.create_item_button.click()

        with allure.step("Заполнить и отправить форму"):
            page.item_name_input.send_keys("example item")
            page.save_item_button.click()

        with allure.step("Дождаться подтверждения (toast виден)"):
            assert page.success_toast.is_displayed()
