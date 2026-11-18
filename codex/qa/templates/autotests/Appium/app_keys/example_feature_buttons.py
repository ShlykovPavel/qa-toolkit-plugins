"""example_feature_buttons.py — шаблон локаторов для экрана фичи.

Каждый класс маппит стабильные идентификаторы элементов (Android resource-id /
iOS accessibilityIdentifier; во Flutter — Semantics.identifier) на
Python-свойства. Наследуйтесь от ScreenActions — получите поиск/клики/скроллы.

Откуда берутся идентификаторы:
  1. Снять дамп экрана и извлечь их: dump_ui_tree.py — для
     тест-кейса проходом сценария (--walkthrough); все способы —
     docs/mobile.md, «Как показать агенту экраны приложения».
  2. Если идентификаторов у элементов нет — это БЛОКЕР: тесты не пишутся,
     разработчикам приложения уходит список недостающих id
     (контракт и готовый промпт — docs/locator-conventions.md).

Скопируйте файл для каждого нового экрана. Переименуйте ExampleFeatureButtons.
"""

from Appium.app_keys.screen_actions import ScreenActions


class ExampleFeatureButtons(ScreenActions):

    # ------------------------------------------------------------------
    # Навигация
    # ------------------------------------------------------------------

    @property
    def feature_nav_button(self):
        """Кнопка нижней навигации, открывающая фичу."""
        return self.get_element("app_example_feature_nav_button")

    # ------------------------------------------------------------------
    # Элементы экрана
    # ------------------------------------------------------------------

    @property
    def screen_title(self):
        """Заголовок экрана фичи."""
        return self.get_element("app_example_feature_title")

    @property
    def create_button(self):
        """FAB / кнопка «+» создания нового элемента."""
        return self.get_element("app_example_create_button")

    @property
    def name_input(self):
        """Поле ввода имени элемента."""
        return self.get_element("app_example_name_input")

    @property
    def submit_button(self):
        """Кнопка подтверждения в формах и модалках."""
        return self.get_element("app_submit_button")

    @property
    def cancel_button(self):
        """Кнопка отмены в формах и модалках."""
        return self.get_element("app_cancel_button")

    # ------------------------------------------------------------------
    # Элементы списка (динамические идентификаторы — id сущности из API)
    # ------------------------------------------------------------------

    def item_tile(self, item_id: str):
        """Плитка конкретного элемента списка по его API-id."""
        return self.get_element(f"app_example_item_tile_{item_id}")

    def item_delete_button(self, item_id: str):
        """Кнопка удаления конкретного элемента списка."""
        return self.get_element(f"app_example_item_delete_{item_id}")
