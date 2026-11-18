"""Фабрика Selenium-драйвера для фронтенд-тестов.

Все настройки — из переменных окружения (docs/frontend.md, «Driver-фабрика и env»):
    BROWSER      — chrome | firefox (дефолт chrome)
    HEADLESS     — true | false (дефолт true; строка, не bool!)
    WINDOW_SIZE  — <ширина>x<высота> (дефолт 1920x1080)

Базовый URL приложения фабрика НЕ знает — тесты берут его из config.py
(FRONTEND_BASE_URL). Selenium Manager (selenium >= 4.6) сам скачивает
драйвер браузера при первом запуске — отдельная установка chromedriver
не нужна, но нужен установленный браузер и доступ в сеть при первом запуске.
"""

import os

from selenium import webdriver


def _env_flag(name: str, default: str = 'false') -> bool:
    """Читает булеву переменную окружения ('true'/'false' — строки!).

    os.getenv возвращает строку: непустая строка 'False' — truthy,
    поэтому наивный bool(os.getenv(...)) всегда даёт True.
    """
    return os.getenv(name, default).strip().lower() in ('true', '1', 'yes')


def _window_size() -> str:
    """Размер окна из WINDOW_SIZE в формате '1920x1080'."""
    return os.getenv('WINDOW_SIZE', '1920x1080').strip().lower()


def get_driver():
    """Создаёт Selenium-драйвер по переменной окружения BROWSER.

    :return: webdriver.Chrome | webdriver.Firefox (headless по умолчанию)
    """
    browser = (os.getenv('BROWSER') or 'chrome').strip().lower()
    headless = _env_flag('HEADLESS', default='true')
    width, _, height = _window_size().partition('x')

    if browser == 'chrome':
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-gpu')
        options.add_argument(f'--window-size={width},{height}')
        return webdriver.Chrome(options=options)

    if browser == 'firefox':
        options = webdriver.FirefoxOptions()
        if headless:
            options.add_argument('-headless')
        options.add_argument(f'--width={width}')
        options.add_argument(f'--height={height}')
        return webdriver.Firefox(options=options)

    raise ValueError(
        f"Неподдерживаемый браузер: {os.getenv('BROWSER')!r}. "
        f"Задайте BROWSER=chrome или BROWSER=firefox в .env"
    )
