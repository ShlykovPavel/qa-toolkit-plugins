"""example_module.py — ПРИМЕР модуля мобильной фичи. Единственный образец слоя
Modules: модуль оборачивает UI-взаимодействия одного экрана, локаторы живут
в соответствующем классе app_keys.

Скопируйте файл для каждой фичи вашего приложения (логин, главный экран,
профиль и т.д.). Замените:
  - ExampleModule           → ВашаФичаModule
  - example_feature_buttons → локаторы вашей фичи (в app_keys/)
  - имена элементов         → реальные идентификаторы из дампа экрана
    (dump_ui_tree.py, см. docs/mobile.md)

Каждое действие логируйте через Logger.log_mobile_action — это основной
источник диагностики при падениях.
"""

from logger import Logger
from Appium.app_keys.base_elements_buttons import BaseElements

# Замените на реальный app_keys-класс вашей фичи:
# from Appium.app_keys.example_feature_buttons import ExampleFeatureButtons


class ExampleModule:
    """Обёртка UI-взаимодействий экрана ExampleFeature."""

    def __init__(self, driver):
        self.driver = driver
        # self.buttons = ExampleFeatureButtons(driver)  # раскомментируйте, когда есть app_keys
        self.base = BaseElements(driver)

    def open_feature(self):
        """Переходит на экран фичи (например, тап по нижней навигации)."""
        Logger.log_mobile_action("Переход на экран ExampleFeature")
        # self.buttons.click_element(self.buttons.feature_nav_button)

    @property
    def feature_title(self):
        """Элемент заголовка экрана фичи (ошибка с понятным текстом, если не найден).

        Для проверки ОТСУТСТВИЯ элемента используйте другой паттерн:
        is_element_not_presented("app_ключ") — а не element_expected=False
        (тот вернёт None при отсутствии и упадёт при наличии, элемент он
        не возвращает никогда).
        """
        # Замените на реальный идентификатор из дампа экрана
        return self.base.get_element("app_example_feature_title")

    def create_item(self, name: str) -> None:
        """Нажимает кнопку создания и заполняет имя элемента."""
        Logger.log_mobile_action(f"Создание элемента: {name}")
        # self.buttons.click_element(self.buttons.create_button)
        # self.buttons.type_text(self.buttons.name_input, name)
        # self.buttons.click_element(self.base.submit_button)

    def get_items_list(self) -> list:
        """Возвращает имена элементов, видимых на экране."""
        Logger.log_mobile_action("Получение списка элементов")
        # Замените на реальное чтение списка
        # elements = self.buttons.item_list_tiles
        # return [el.text for el in elements]
        return []
