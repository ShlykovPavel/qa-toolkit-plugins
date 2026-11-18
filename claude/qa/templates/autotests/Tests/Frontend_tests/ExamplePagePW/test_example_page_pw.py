"""test_example_page_pw.py — шаблон теста playwright-ветки (ПРИМЕР).

В шаблоне фронтенд-тесты НЕ гоняются (нет живого стенда) — только
коллекция. Форк задаёт FRONTEND_BASE_URL в .env, ставит
requirements-playwright.txt и запускает `make frontend`.

Правила (docs/frontend.md, раздел playwright-ветки):
  - локаторы снимаются с живой страницы (dump_dom.py --locators role
    или Playwright MCP), не выдумываются;
  - действия ждут сами (auto-wait); ожидаемый результат — через
    expect(...).to_be_visible() и другие web-first ассерты;
  - предусловия данных — через API-клиенты src/, не через UI.

Скопируйте директорию и замените ExamplePagePW на свою страницу.
"""

import allure
import pytest

pytest.importorskip("playwright", reason="playwright-ветка: поставьте requirements-playwright.txt")

from playwright.sync_api import expect

pytestmark = pytest.mark.frontend


@allure.epic("Frontend")
@allure.feature("ExamplePagePW")
class TestExamplePagePw:

    @allure.description("Сценарий создания сущности через форму админки (playwright)")
    def test_create_item_via_form(self, example_admin_page_pw):
        page_object = example_admin_page_pw

        with allure.step("Открыть форму создания"):
            page_object.create_item_button.click()

        with allure.step("Заполнить и отправить форму"):
            page_object.item_name_input.fill("example item")
            page_object.save_item_button.click()

        with allure.step("Дождаться подтверждения (toast виден)"):
            expect(page_object.success_toast).to_be_visible()
