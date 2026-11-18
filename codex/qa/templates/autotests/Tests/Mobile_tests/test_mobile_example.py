"""test_mobile_example.py — шаблон мобильного Appium UI-теста
(нативные драйверы UiAutomator2 / XCUITest).

Показывает:
  - навигацию на экран фичи через модуль (Appium/Modules/example_module.py)
  - проверку видимости элемента по стабильному идентификатору
  - паттерн «создать в UI и проверить в списке»

Реальные идентификаторы элементов снимаются с живого приложения скриптом
dump_ui_tree.py — для тест-кейса проходом сценария целиком
(--walkthrough); см. docs/mobile.md, «Как показать агенту экраны приложения».

Каждый тест получает свежий драйвер (function-scoped фикстура в conftest.py).
Если приложению нужен логин — добавьте фикстуру login_in_app (образец
закомментирован в conftest.py) и укажите её параметром теста.

Скопируйте файл и замените ExampleModule / ExampleFeature на свою фичу.
"""

import allure
import pytest

from Appium.Modules.example_module import ExampleModule  # замените на свой модуль

pytestmark = pytest.mark.mobile


@allure.epic("Mobile")
@allure.feature("ExampleFeature")
class TestMobileExample:

    @allure.description("Переход к фиче → главный элемент экрана виден")
    def test_feature_visible(self, mobile_data, driver):
        module = ExampleModule(driver)
        module.open_feature()
        assert module.feature_title is not None, "Заголовок фичи не найден"

    @allure.description("Создание элемента в фиче и проверка его в списке")
    def test_create_item_in_feature(self, mobile_data, driver):
        """Шаблон потока «создать + проверить» в мобильном UI."""
        module = ExampleModule(driver)
        module.open_feature()
        module.create_item(name="autotest item")

        items = module.get_items_list()
        assert any(item == "autotest item" for item in items), \
            "Созданный элемент не найден в списке"
