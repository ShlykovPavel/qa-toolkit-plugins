"""example_admin_page_pw.py — ПРИМЕР page object playwright-ветки (админка).

Зеркало selenium-эталона example_admin_page_keys.py по структуре: класс на
страницу, по @property на каждый UI-элемент, НИКАКОЙ логики — только
локаторы. Действия/сценарии — в тестах.

Локатор: есть data-testid — get_by_test_id (docs/locator-conventions.md).
У страницы этого примера ключей нет, поэтому ниже — лестница для элементов
без ключа (docs/frontend.md, раздел ветки): get_by_role(+name) →
get_by_label → get_by_placeholder → css (резерв). Локаторы ниже
get_by_test_id — техдолг: в копии ставь комментарий у каждого.

Ожидания НЕ настраиваются здесь: действия playwright ждут сами (auto-wait),
видимость результата тест проверяет через expect(...).to_be_visible().

Скопируйте файл для каждой страницы/раздела вашего веб-интерфейса.
"""

from playwright.sync_api import Locator, Page


class ExampleAdminPagePw:

    def __init__(self, page: Page):
        self.page = page

    # Страница логина
    @property
    def login_email_input(self) -> Locator:
        return self.page.get_by_label("Email")

    @property
    def login_password_input(self) -> Locator:
        return self.page.get_by_label("Пароль")

    @property
    def login_submit_button(self) -> Locator:
        return self.page.get_by_role("button", name="Войти")

    # Список сущностей
    @property
    def create_item_button(self) -> Locator:
        return self.page.get_by_role("button", name="Создать")

    # Форма сущности
    @property
    def item_name_input(self) -> Locator:
        return self.page.get_by_label("Имя")

    @property
    def save_item_button(self) -> Locator:
        return self.page.get_by_role("button", name="Сохранить")

    # Уведомления
    @property
    def success_toast(self) -> Locator:
        # техдолг: у тоста нет role/label/testid — попросить у фронтов role="alert"
        return self.page.locator(".toast-success")
