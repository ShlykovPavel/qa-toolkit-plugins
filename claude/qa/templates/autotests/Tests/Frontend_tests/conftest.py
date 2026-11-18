"""conftest.py — фикстуры фронтенд-тестов Selenium (ШАБЛОН).

Необходимые переменные окружения — docs/frontend.md, «Driver-фабрика и env».

При форке:
  1. Задайте FRONTEND_BASE_URL (и креды UI-логина) в .env.
  2. Раскомментируйте и адаптируйте фикстуру логина (образец ниже).
"""

import allure
import pytest

from frontend.driver_factory import get_driver


# ---------------------------------------------------------------------------
# Selenium-драйвер
# ---------------------------------------------------------------------------

@pytest.fixture()
def driver():
    """Свежий Selenium-драйвер на каждый тест; после теста закрывается.

    НЕ autouse — браузер дорог и нужен не каждому фронт-тесту:
    тест, которому нужен браузер, берёт фикстуру параметром явно.
    """
    drv = get_driver()
    yield drv
    drv.quit()


# ---------------------------------------------------------------------------
# Диагностика при падении: скриншот + page_source в Allure
# ---------------------------------------------------------------------------

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Прикладывает скриншот и HTML страницы к упавшему тесту.

    Guard'ы обязательны: тест мог упасть в setup ДО создания драйвера —
    тогда прикладывать нечего, а хук не должен ронять прогон сам.
    """
    outcome = yield
    rep = outcome.get_result()
    if rep.when in ("call", "setup") and rep.failed:
        drv = getattr(item, "funcargs", {}).get("driver")
        if drv is not None:
            try:
                allure.attach(
                    drv.get_screenshot_as_png(),
                    name="screenshot",
                    attachment_type=allure.attachment_type.PNG,
                )
                allure.attach(
                    drv.page_source,
                    name="page_source",
                    attachment_type=allure.attachment_type.HTML,
                )
            except Exception as e:
                print(f"Не удалось снять диагностику с драйвера: {e}")


# ---------------------------------------------------------------------------
# Пример: фикстура логина в админку через UI
# ---------------------------------------------------------------------------
# Живой логин — дело форка: реализуйте page object страницы логина
# (frontend/front_keys/, образец — example_admin_page_keys.py) и
# раскомментируйте. Креды — только из env (имена переменных — из паспорта).
#
# import os
#
# import config
# from frontend.front_keys.example_service.example_admin_page_keys import ExampleAdminPage
#
# @pytest.fixture()
# def login_in_admin(driver):
#     """Логинится в админку перед тестом, возвращает драйвер на её странице."""
#     driver.get(config.FRONTEND_BASE_URL)
#     page = ExampleAdminPage(driver)
#     page.login_email_input.send_keys(os.getenv("UI_ADMIN_EMAIL"))
#     page.login_password_input.send_keys(os.getenv("UI_ADMIN_PASSWORD"))
#     page.login_submit_button.click()
#     return driver
