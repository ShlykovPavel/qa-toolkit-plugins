"""Базовый класс работы с элементами экрана: поиск по стабильным
идентификаторам, клики, ввод текста, скроллы. Все app_keys-классы
наследуются от ScreenActions.

Единый слой для нативного Android, нативного iOS и Flutter-приложений:
элемент ищется по Android `resource-id` / iOS `accessibilityIdentifier`
(Flutter >= 3.19 пробрасывает `Semantics.identifier` в эти же атрибуты).
Контракт с разработчиками приложения — docs/locator-conventions.md.
Локаторов по тексту, XPath-по-структуре и координатам в слое НЕТ.

Принцип: не найденный элемент — это ОШИБКА с понятным сообщением, а не None
(кроме явного element_expected=False). Молчаливое проглатывание ошибок
превращает падение в невнятный сбой дальше по коду.
"""

import os

from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from Appium.localization.localisation import load_localization
from logger import Logger

_localization_cache = None


def localization() -> dict:
    """Локализация приложения (JSON из LOCALIZATION_FILE_PATH), с кэшем."""
    global _localization_cache
    if _localization_cache is None:
        _localization_cache = load_localization()
    return _localization_cache


class ScreenActions:

    def __init__(self, driver):
        self.driver = driver
        # Таймаут поиска элемента, секунды
        self.timeout = float(os.getenv('MOBILE_ELEMENT_TIMEOUT', '5'))

    # ------------------------------------------------------------------
    # Поиск
    # ------------------------------------------------------------------

    def _platform(self) -> str:
        """Платформа драйвера в нижнем регистре ('android' / 'ios')."""
        return str(self.driver.capabilities.get('platformName', '')).lower()

    def _locator(self, key: str) -> tuple:
        """Платформенный локатор для стабильного идентификатора.

        Android-нюанс: нативные View отдают resource-id в полной форме
        `<package>:id/<ключ>`, Flutter Semantics — голую строку `<ключ>`.
        Обе формы матчатся ОДНИМ запросом resourceIdMatches (два
        последовательных WebDriverWait дали бы двойной таймаут на каждый
        промах). Ключи по конвенции — snake_case, поэтому regex-экранирование
        не требуется; точки в имени пакета матчат сами себя.

        iOS: accessibilityIdentifier виден в page_source как атрибут `name`
        и ищется через ACCESSIBILITY_ID — это ОДИН и тот же атрибут.
        """
        if self._platform() == 'android':
            package = os.getenv('ANDROID_APP_PACKAGE') or '[^:]+'
            return (
                AppiumBy.ANDROID_UIAUTOMATOR,
                f'new UiSelector().resourceIdMatches("(?:{package}:id/)?{key}$")',
            )
        return (AppiumBy.ACCESSIBILITY_ID, key)

    def get_element(self, key: str, element_expected: bool = True):
        """Ищет элемент по стабильному идентификатору.

        element_expected=True (по умолчанию): нашёл → вернул элемент;
        не нашёл за таймаут → ValueError с именем ключа.

        element_expected=False — это АССЕРТ ОТСУТСТВИЯ, не getter:
        дожидается исчезновения/невидимости элемента (ок → None),
        элемент видим по истечении таймаута → ValueError.
        **Элемент этот вызов не возвращает никогда** — не используйте его,
        чтобы «достать элемент, если есть».
        """
        locator = self._locator(key)
        wait = WebDriverWait(self.driver, self.timeout)

        if element_expected:
            try:
                return wait.until(EC.presence_of_element_located(locator))
            except TimeoutException:
                Logger.log_mobile_action(f"Элемент не найден: {key}")
                raise ValueError(f"Элемент не найден: {key} (таймаут {self.timeout} с)")

        try:
            wait.until(EC.invisibility_of_element_located(locator))
        except TimeoutException:
            Logger.log_mobile_action(f"Элемент присутствует, но не должен: {key}")
            raise ValueError(f"Элемент с ключом '{key}' найден, но не должен был присутствовать")
        return None

    def is_element_not_presented(self, key: str) -> bool:
        """True, если элемент отсутствует/невидим (дожидается исчезновения
        в пределах таймаута). Явный метод для проверок отсутствия."""
        try:
            WebDriverWait(self.driver, self.timeout).until(
                EC.invisibility_of_element_located(self._locator(key))
            )
            return True
        except TimeoutException:
            return False

    # ------------------------------------------------------------------
    # Действия
    # ------------------------------------------------------------------

    def click_element(self, element):
        try:
            element.click()
        except Exception as e:
            Logger.log_mobile_action(f"Не удалось нажать на элемент {element}. Ошибка: {e}")
            raise ValueError(f"Не удалось нажать на элемент. Ошибка: {e}")

    def type_text(self, element, text: str):
        """Очищает поле и вводит текст.

        Значение в лог не пишется — в поле могут быть креды.
        """
        try:
            element.clear()
            element.send_keys(text)
            Logger.log_mobile_action(f"Введён текст ({len(text)} символов)")
        except Exception as e:
            Logger.log_mobile_action(f"Не удалось ввести текст в элемент {element}. Ошибка: {e}")
            raise ValueError(f"Не удалось ввести текст. Ошибка: {e}")

    def go_back(self):
        """Возврат на предыдущий экран: Android — системный back,
        iOS — кнопка «назад» в navigation bar (XCUITest реализует back сам)."""
        Logger.log_mobile_action("Возврат на предыдущий экран")
        self.driver.back()

    # ------------------------------------------------------------------
    # Скроллы
    # ------------------------------------------------------------------

    def scroll(self, direction: str = 'down', percent: float = 0.7):
        """Прокручивает экран в заданном направлении ('up'/'down'/'left'/'right').

        :param percent: доля области прокрутки за один жест (Android)
        """
        Logger.log_mobile_action(f"Скролл экрана: {direction}")
        if self._platform() == 'android':
            size = self.driver.get_window_size()
            self.driver.execute_script('mobile: scrollGesture', {
                'left': size['width'] * 0.1,
                'top': size['height'] * 0.2,
                'width': size['width'] * 0.8,
                'height': size['height'] * 0.6,
                'direction': direction,
                'percent': percent,
            })
        else:
            self.driver.execute_script('mobile: scroll', {'direction': direction})

    def scroll_until_visible(self, key: str, direction: str = 'down', max_swipes: int = 10):
        """Скроллит, пока элемент с идентификатором не появится; возвращает его.

        Android — одним UiScrollable-запросом (нативный scrollIntoView),
        iOS — циклом «поискать → проскроллить» до max_swipes попыток.
        """
        Logger.log_mobile_action(f"Скролл до элемента: {key}")
        if self._platform() == 'android':
            package = os.getenv('ANDROID_APP_PACKAGE') or '[^:]+'
            selector = (
                'new UiScrollable(new UiSelector().scrollable(true))'
                f'.scrollIntoView(new UiSelector().resourceIdMatches("(?:{package}:id/)?{key}$"))'
            )
            try:
                return self.driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, selector)
            except Exception as e:
                Logger.log_mobile_action(f"Не удалось найти элемент по скроллу: {key}. Ошибка: {e}")
                raise ValueError(f"Не удалось найти элемент по скроллу: {key}. Ошибка: {e}")

        for _ in range(max_swipes):
            found = self.driver.find_elements(*self._locator(key))
            if found:
                return found[0]
            self.scroll(direction=direction)
        Logger.log_mobile_action(f"Не удалось найти элемент по скроллу: {key}")
        raise ValueError(f"Не удалось найти элемент по скроллу за {max_swipes} свайпов: {key}")

    # ------------------------------------------------------------------
    # Диагностика и тексты
    # ------------------------------------------------------------------

    def get_page_source(self) -> str:
        """XML-дамп текущего экрана (page_source) — «глаза» при отладке.

        Для инвентаризации идентификаторов экрана — dump_ui_tree.py.
        """
        return self.driver.page_source

    def assert_text(self, element, localization_key: str):
        """Сверяет текст элемента со строкой локализации.

        Тексты проверяются ТОЛЬКО через локализацию (Appium/localization/):
        хардкод строк ломается при смене языка. Поиска по тексту в слое нет —
        элемент находится по идентификатору, текст сверяется ассертом.
        """
        expected = localization()[localization_key]
        actual = element.text
        assert actual == expected, (
            f"Текст элемента {actual!r} не совпадает со строкой локализации "
            f"'{localization_key}' ({expected!r})"
        )
