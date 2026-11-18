"""Фабрика Appium-драйвера (нативные UiAutomator2 / XCUITest) и
низкоуровневые действия с устройством.

Как найти appPackage и appActivity через adb:
    adb shell dumpsys window windows | grep -E 'mCurrentFocus'
Вывод вида: mCurrentFocus=Window{460e5ae u0 com.example/.MainActivity}
    com.example    — appPackage
    .MainActivity  — appActivity

Установка приложения — НЕ здесь: APK ставит фикстура install_apk
(Appium/Simulator/), поэтому capability `app` в caps отсутствует намеренно.
"""

import os

import allure
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.options.ios import XCUITestOptions
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from logger import Logger
from src.wait_utils import wait_until


def _env_flag(name: str, default: str = 'false') -> bool:
    """Читает булеву переменную окружения ('true'/'false' — строки!).

    os.getenv возвращает строку: непустая строка 'False' — truthy,
    поэтому наивный bool(os.getenv(...)) всегда даёт True.
    """
    return os.getenv(name, default).strip().lower() in ('true', '1', 'yes')


def _platform_of(driver) -> str:
    """Имя платформы драйвера в нижнем регистре ('android' / 'ios')."""
    return str(driver.capabilities.get('platformName', '')).lower()


class DriverFunctions:

    @staticmethod
    def find_webview_context(driver):
        """Возвращает имя WEBVIEW-контекста или None, если его нет.

        Контексты после старта приложения появляются не мгновенно —
        поллинг вместо слепого sleep (правило фреймворка).
        """
        try:
            return wait_until(
                lambda: next((x for x in driver.contexts if x.startswith('WEBVIEW')), None),
                timeout=10, interval=1,
                message="WEBVIEW-контекст не появился",
            )
        except TimeoutError:
            return None

    @staticmethod
    def allow_notifications(driver):
        """Закрывает системный диалог разрешений (уведомления и т.п.)."""
        platform = _platform_of(driver)
        try:
            if platform == 'android':
                # Кнопка "Allow" в системном диалоге Android
                allow_button = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((AppiumBy.XPATH, "//*[@text='Allow']"))
                )
                allow_button.click()
                Logger.log_mobile_action("Уведомления разрешены на Android")
            elif platform == 'ios':
                # Системный алерт iOS
                WebDriverWait(driver, 5).until(EC.alert_is_present())
                driver.switch_to.alert.accept()
                Logger.log_mobile_action("Уведомления разрешены на iOS")
        except Exception as e:
            Logger.log_mobile_action(f"Не удалось найти и кликнуть кнопку уведомлений на {platform}: {e}")

    @staticmethod
    def tap_on_coordinates(driver, x_ratio, y_ratio):
        """Тап по координатам в долях экрана (0..1).

        Только жест (свернуть шторку, закрыть оверлей) — НЕ локатор:
        поиск элементов по координатам запрещён.
        """
        size = driver.get_window_size()
        x = size['width'] * x_ratio
        y = size['height'] * y_ratio

        Logger.log_mobile_action(f'Тап по координатам ({x}, {y})')
        driver.tap([(x, y)])

    @staticmethod
    def swipe_on_coordinates(driver, start_x_ratio, start_y_ratio, end_x_ratio, end_y_ratio):
        """Свайп между точками, заданными в долях экрана (0..1)."""
        size = driver.get_window_size()
        start_x = size['width'] * start_x_ratio
        start_y = size['height'] * start_y_ratio
        end_x = size['width'] * end_x_ratio
        end_y = size['height'] * end_y_ratio
        Logger.log_mobile_action(f'Свайп: ({start_x}, {start_y}) -> ({end_x}, {end_y})')

        driver.swipe(start_x=start_x, start_y=start_y, end_x=end_x, end_y=end_y)

    @staticmethod
    def keep_alive(driver):
        """Периодическое обращение к драйверу, чтобы сессия не протухла."""
        try:
            driver.page_source
        except Exception as e:
            Logger.log_mobile_action(f"Ошибка поддержания сессии: {e}")

    @staticmethod
    def close_app(driver):
        try:
            platform = _platform_of(driver)
            if platform == 'ios':
                driver.terminate_app(os.getenv('IOS_BUNDLE_ID'))
            elif platform == 'android':
                driver.terminate_app(os.getenv('ANDROID_APP_PACKAGE'))
            Logger.log_mobile_action("Приложение закрыто")
        except Exception as e:
            Logger.log_mobile_action(f'Ошибка закрытия приложения: {e}')

    @staticmethod
    def open_app(driver):
        """Выводит установленное приложение на передний план.

        Установка — за фикстурой install_apk; здесь только activate_app.
        """
        try:
            platform = _platform_of(driver)
            if platform == 'ios':
                driver.activate_app(os.getenv('IOS_BUNDLE_ID'))
            elif platform == 'android':
                driver.activate_app(os.getenv('ANDROID_APP_PACKAGE'))
            Logger.log_mobile_action("Приложение открыто")
        except Exception as e:
            Logger.log_mobile_action(f'Ошибка открытия приложения: {e}')

    @staticmethod
    def attach_failure_diagnostics(driver):
        """Прикладывает диагностику упавшего теста в Allure: скриншот + page_source.

        Каждый артефакт в своём try: падение одного не мешает снять остальные.
        Метод НИКОГДА не бросает исключений — он вызывается из hook'а
        pytest_runtest_makereport и не должен ронять сбор отчёта.
        """
        try:
            allure.attach(
                driver.get_screenshot_as_png(),
                name="screenshot",
                attachment_type=allure.attachment_type.PNG,
            )
        except Exception as e:
            Logger.log_mobile_action(f"Не удалось снять скриншот: {e}")
        try:
            allure.attach(
                driver.page_source,
                name="page_source",
                attachment_type=allure.attachment_type.XML,
            )
        except Exception as e:
            Logger.log_mobile_action(f"Не удалось снять page_source: {e}")

    @staticmethod
    def driver(noReset=False):
        """Создаёт Appium-драйвер по переменной окружения PLATFORM (iOS | Android)."""
        platform = (os.getenv('PLATFORM') or '').lower()

        if platform == 'ios':
            capabilities = dict(
                platformName='iOS',
                deviceName=os.getenv('IOS_DEVICE_NAME'),
                platformVersion=os.getenv('IOS_PLATFORM_VERSION'),
                automationName='XCUITest',
                udid=os.getenv('IOS_UDID'),
                bundleId=os.getenv('IOS_BUNDLE_ID'),
                usePrebuiltWDA=True,
                useNewWDA=_env_flag('IOS_useNewWDA'),  # перезапуск WDA перед каждым тестом
                xcodeOrgId=os.getenv('xcodeOrgId'),
                xcodeSigningId=os.getenv('xcodeSigningId'),
            )
            capabilities_options = XCUITestOptions().load_capabilities(caps=capabilities)
        elif platform == 'android':
            capabilities = dict(
                platformName="Android",
                deviceName=os.getenv('ANDROID_DEVICE_NAME'),
                appPackage=os.getenv('ANDROID_APP_PACKAGE'),
                appActivity=os.getenv('ANDROID_APP_ACTIVITY'),
                automationName="UiAutomator2",
                noReset=noReset
            )
            capabilities_options = UiAutomator2Options().load_capabilities(caps=capabilities)
        else:
            raise ValueError(
                f"Неподдерживаемая платформа: {os.getenv('PLATFORM')!r}. "
                f"Задайте PLATFORM=Android или PLATFORM=iOS в .env"
            )

        return webdriver.Remote('http://localhost:4723', options=capabilities_options)
