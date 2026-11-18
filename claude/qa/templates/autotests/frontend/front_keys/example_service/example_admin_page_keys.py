"""example_admin_page_keys.py — ПРИМЕР Selenium page object (страница админки).

Наследуйтесь от ButtonFinder — получите все хелперы find_element_by_*
с ожиданиями (см. frontend/front_keys/element_finder.py).
Добавляйте по одному свойству на каждый UI-элемент, с которым работает тест.

Приоритет селекторов: id → data-атрибут → css → xpath.
Текстовые селекторы — крайний случай (ломаются при смене локализации).

Скопируйте файл для каждой страницы/раздела вашего веб-интерфейса.
Замените ExampleAdminPage на имя своей страницы (DashboardPage, UsersPage...).
"""

from frontend.front_keys.element_finder import ButtonFinder


class ExampleAdminPage(ButtonFinder):

    # Страница логина
    @property
    def login_email_input(self):
        return self.find_element_by_xpath('//input[@type="email"]')

    @property
    def login_password_input(self):
        return self.find_element_by_xpath('//input[@type="password"]')

    @property
    def login_submit_button(self):
        return self.find_element_by_css_selector('button[type="submit"]', "Clickable")

    # Навигация
    @property
    def nav_users_link(self):
        return self.find_element_by_css_selector('a[href="users"]', "Clickable")

    # Список сущностей
    @property
    def create_item_button(self):
        return self.find_element_by_css_selector('.btn-create', "Clickable")

    # Форма сущности
    @property
    def item_name_input(self):
        return self.find_element_by_name("name")

    @property
    def save_item_button(self):
        return self.find_element_by_css_selector('.btn-save', "Clickable")

    # Уведомления
    @property
    def success_toast(self):
        return self.find_element_by_css_selector('.toast-success', "Visible")

    @property
    def error_toast(self):
        return self.find_element_by_css_selector('.toast-error', "Visible")
