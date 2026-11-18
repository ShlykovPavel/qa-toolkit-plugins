"""Все настройки читаются из переменных окружения (.env) — хардкод запрещён.

Это форкаемый шаблон: рабочий минимум — BASE_URL и DB_PRIMARY.
Дополнительные сервисы/базы добавляйте по закомментированным примерам.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# --- Базовый URL тестируемого сервиса ---
BASE_URL = os.getenv('BASE_URL')

# Пример: второй сервис (микросервисная архитектура) — раскомментируйте при необходимости
# BASE_URL_SECOND_SERVICE = os.getenv('BASE_URL_SECOND_SERVICE')

# слой: frontend
# --- Базовый URL веб-интерфейса (фронтенд-тесты, Tests/Frontend_tests) ---
FRONTEND_BASE_URL = os.getenv('FRONTEND_BASE_URL')
# /слой

# Пример: API-ключ для внутренних эндпоинтов
# INTERNAL_API_KEY = os.getenv('INTERNAL_API_KEY')

# --- База данных (строка подключения SQLAlchemy) ---
DB_PRIMARY = os.getenv('DB_PRIMARY')    # напр. postgresql+psycopg2://user:pass@host:5432/dbname

# Вторая БД (опционально): задайте DB_SECONDARY в .env —
# db_config.secondary_session() заработает автоматически
DB_SECONDARY = os.getenv('DB_SECONDARY')

# --- Учётные данные тестового администратора ---
# Способ авторизации у каждого проекта свой — см. src/example_auth.py
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')

# --- HTTP ---
# Таймаут запросов в секундах (защита от зависшего стенда)
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '30'))
