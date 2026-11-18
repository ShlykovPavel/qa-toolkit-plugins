"""conftest.py — фикстуры мобильных Appium-тестов (ШАБЛОН).

Необходимые переменные окружения — docs/mobile.md, раздел «Env-переменные».

При форке:
  1. Добавьте фикстуру логина в ВАШЕ приложение (образец закомментирован ниже).
  2. Если тестам нужны предусловия через API — авторизуйтесь в initialize
     (образец закомментирован).
"""

import os
import signal
import subprocess

import pytest

from Appium.Appium_launcher.launcher import ensure_appium_running, stop_appium_server, graceful_shutdown
from Appium.Simulator.Android_emulator import launch_emulator, stop_emulator, get_adb_devices
from Appium.Simulator.App_for_android_emulator import install_apk_with_adb
from Appium.Simulator.Android_screen_recording import ScreenRecorder
from Appium.driver_func import DriverFunctions
from src.teardown_utils import report_teardown_failure


# ---------------------------------------------------------------------------
# Сессионный контейнер мобильных данных
# ---------------------------------------------------------------------------

@pytest.fixture(scope='session')
def mobile_data():
    """Сессионные данные мобильных тестов (креды, данные окружения)."""
    return {}


# ---------------------------------------------------------------------------
# Пример: авторизация через API для подготовки данных
# ---------------------------------------------------------------------------
# Если мобильным тестам нужны предусловия через API (создать данные, получить
# код приглашения и т.п.) — раскомментируйте и адаптируйте:
#
# from src.example_auth import ExampleAuth
#
# @pytest.fixture(scope='session', autouse=True)
# def initialize(mobile_data):
#     """Переопределяет родительский initialize: авторизация для API-предусловий."""
#     mobile_data['admin_auth'] = ExampleAuth.login_as_admin()


# ---------------------------------------------------------------------------
# Жизненный цикл Appium-сервера
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def launch_appium_server():
    """Запускает Appium-сервер до сессии и останавливает после."""
    ensure_appium_running()
    yield
    stop_appium_server()


@pytest.fixture(scope="session", autouse=True)
def register_signals():
    """Обработчики SIGINT/SIGTERM для корректной остановки Appium."""
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)
    yield


# ---------------------------------------------------------------------------
# Жизненный цикл Android-эмулятора
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def launch_android_emulator(mobile_data):
    """Запускает эмулятор, ставит APK, после сессии останавливает эмулятор."""
    launch_emulator(os.getenv("ANDROID_DEVICE_NAME"), no_data_save=True)
    mobile_data['emulator_name'] = get_adb_devices()
    yield
    stop_emulator(mobile_data['emulator_name'])


@pytest.fixture()
def install_apk(mobile_data):
    """Устанавливает APK на запущенный эмулятор."""
    install_apk_with_adb(os.getenv("APK_PATH"), mobile_data['emulator_name'])


# ---------------------------------------------------------------------------
# Установка приложения на iOS-симулятор
# ---------------------------------------------------------------------------

@pytest.fixture()
def install_ios_app():
    """Устанавливает .app на уже ЗАПУЩЕННЫЙ iOS-симулятор (IOS_UDID).

    Не срабатывает, если PLATFORM не iOS (Android-прогон не задаёт
    IOS_APP_PATH — фикстура тогда просто ничего не делает, а не скипает
    тест: `install_ios_app` не должна решать судьбу тестов другой
    платформы).

    В отличие от Android-эмулятора, здесь нет фикстуры запуска симулятора —
    `xcrun simctl boot` делается человеком/CI до прогона (рецепт сборки
    приложения под симулятор — в docs/apps-repos.md форка). Сама установка — через
    `xcrun simctl install`, не через Appium: `bundleId`-capability в
    driver_func.py только активирует уже стоящее приложение.

    ВАЖНО: фикстура сама по себе не гарантирует порядок относительно
    `driver` (autouse) — приложение должно быть установлено ДО создания
    Appium-сессии. Явная зависимость `driver(install_ios_app)` ниже
    заставляет pytest выполнить установку первой.
    """
    if (os.getenv("PLATFORM") or "").lower() != "ios":
        return

    udid = os.getenv("IOS_UDID")
    app_path = os.getenv("IOS_APP_PATH")
    if not udid or not app_path:
        pytest.fail("PLATFORM=iOS, но IOS_UDID/IOS_APP_PATH не заданы в .env")

    result = subprocess.run(
        ["xcrun", "simctl", "install", udid, app_path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        pytest.fail(f"Не удалось установить приложение на симулятор {udid}: {result.stderr.strip()}")


# ---------------------------------------------------------------------------
# Запись экрана
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def screen_recording(mobile_data):
    """Начинает запись экрана до тестов, останавливает после."""
    recorder = ScreenRecorder(mobile_data['emulator_name'])
    recorder.start_recording()
    yield
    recorder.stop_recording()


# ---------------------------------------------------------------------------
# Appium-драйвер
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function", autouse=True)
def driver(install_ios_app):
    """Свежий Appium-драйвер на каждый тест; после теста закрывается.

    Зависит от `install_ios_app`: на iOS приложение должно быть
    установлено на симулятор ДО создания сессии (`bundleId`-capability
    только активирует уже стоящее приложение, не ставит его). На
    Android-прогонах `install_ios_app` — no-op (см. её тело).

    Сброс состояния между тестами делает отдельная фикстура
    `reset_app_after_test` — её тест запрашивает явно, когда довёл
    приложение до состояния, переживающего перезапуск.

    `allow_notifications` — ПОСЛЕ создания сессии, ДО того как тест начнёт
    искать элементы приложения: на первом запуске после чистой установки
    iOS показывает системный алерт «запрашивает разрешение на отправку
    уведомлений», который перекрывает первый экран приложения и делает
    недоступным (по факту, не по ошибке в коде) любой элемент экрана, пока
    не закрыт. Метод сам не падает, если алерта нет (см. его реализацию) —
    безопасно вызывать безусловно на каждом тесте, не только на «первом».
    """
    drv = DriverFunctions.driver()
    DriverFunctions.allow_notifications(drv)
    yield drv
    drv.quit()


@pytest.fixture()
def reset_app_after_test(driver):
    """Сбрасывает данные приложения ПОСЛЕ теста — до чистой установки.

    Запрашивается тестом ЯВНО, автоматически не применяется: переустановка
    стоит секунд, и платить её каждому тесту незачем.

    Зачем. Тест, доводящий приложение до состояния, которое переживает
    перезапуск (регистрация, заданный PIN, живая сессия), оставляет это
    состояние следующему прогону: общий `driver` данные приложения не чистит
    (в capabilities нет `fullReset`), а повторная установка поверх ничего не
    стирает. Второй прогон такого теста падает не по своей вине — на чужом
    экране. Симптом узнаваемый: тест зелёный ровно один раз после ручной
    переустановки.

    Как. iOS — `remove_app` + `install_app` той же сессией: порядок teardown
    LIFO, фикстура зависит от `driver`, поэтому успевает отработать ДО
    `drv.quit()`. Android — `mobile: clearApp` драйвера UiAutomator2
    (эквивалент `adb shell pm clear`): чистит данные без переустановки.

    Отказ уборки тест не роняет, но и не молчит — `report_teardown_failure`
    (pytest глотает print прошедших тестов, warning виден в сводке).
    """
    yield
    platform = str(driver.capabilities.get("platformName", "")).lower()
    try:
        if platform == "ios":
            bundle_id, app_path = os.getenv("IOS_BUNDLE_ID"), os.getenv("IOS_APP_PATH")
            if not bundle_id or not app_path:
                report_teardown_failure(
                    "IOS_BUNDLE_ID/IOS_APP_PATH не заданы — приложение не сброшено, "
                    "следующий прогон стартует с состоянием этого теста"
                )
                return
            driver.remove_app(bundle_id)
            driver.install_app(app_path)
        else:
            package = os.getenv("ANDROID_APP_PACKAGE")
            if not package:
                report_teardown_failure(
                    "ANDROID_APP_PACKAGE не задан — данные приложения не очищены, "
                    "следующий прогон стартует с состоянием этого теста"
                )
                return
            driver.execute_script("mobile: clearApp", {"appId": package})
    except Exception as e:
        report_teardown_failure(f"приложение не сброшено до чистой установки: {e}")


@pytest.fixture()
def driver_second_session():
    """Второй драйвер с noReset=True (для тестов с сохранённой сессией)."""
    drv = DriverFunctions.driver(noReset=True)
    yield drv
    drv.quit()


# ---------------------------------------------------------------------------
# Диагностика при падении: скриншот + page_source в Allure
# ---------------------------------------------------------------------------

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Прикладывает скриншот и XML-дамп экрана к упавшему тесту.

    Guard'ы обязательны: тест мог упасть в setup ДО создания драйвера
    (тогда прикладывать нечего) или после drv.quit() в teardown — хук
    не должен ронять прогон сам (attach_failure_diagnostics не бросает).
    # слой: selenium
    Стиль — как во фронтенд-хуке Tests/Frontend_tests/conftest.py.
    # /слой
    """
    outcome = yield
    rep = outcome.get_result()
    if rep.when in ("call", "setup") and rep.failed:
        drv = getattr(item, "funcargs", {}).get("driver")
        if drv is not None:
            DriverFunctions.attach_failure_diagnostics(drv)


# ---------------------------------------------------------------------------
# Пример: фикстура логина в приложение
# ---------------------------------------------------------------------------
# Реализуйте модуль логина своего приложения (Appium/Modules/, образец —
# example_module.py) и подключите его фикстурой:
#
# from Appium.Modules.your_login_module import YourLoginModule
#
# @pytest.fixture()
# def login_in_app(mobile_data, driver):
#     """Логинится в приложение перед тестом."""
#     YourLoginModule(driver).login(
#         mobile_data['user'], mobile_data['password'])
#     DriverFunctions.allow_notifications(driver)
