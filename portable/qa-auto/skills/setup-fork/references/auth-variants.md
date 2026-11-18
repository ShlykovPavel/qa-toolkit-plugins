# Варианты реализации src/auth.py

Выбери вариант по схеме авторизации из интервью и адаптируй: эндпоинт,
поля тела, имена полей токенов, набор ролей. Общие правила:

- Класс называй `Auth`, файл — `src/auth.py`.
- Докстринги на русском; у методов — `status_code=` для негативных тестов.
- Метод `login_as_<роль>()` на каждую роль из паспорта: читает креды из
  config, логинится, кладёт токен в `HttpClient.access_folder['<роль>']`.
- Проверяй наличие кредов с понятной ошибкой («X не задан в .env»).

## Вариант A — Bearer JWT (самый частый)

```python
"""Клиент авторизации проекта. Сгенерирован /setup-fork, правится руками."""

from typing import Optional

import config
from src.http_methods import HttpClient


class Auth:

    @staticmethod
    def login(email: str, password: str, status_code: int = 200) -> Optional[dict]:
        """Логин. Возвращает тело ответа с токенами."""
        body = {"email": email, "password": password}      # ← поля из паспорта
        url = config.BASE_URL + "/api/auth/login"          # ← эндпоинт из паспорта
        response = HttpClient.post(url, body)
        assert response.status_code == status_code, f"Логин не удался: {response.text}"
        return HttpClient.parse_json(response)

    @staticmethod
    def login_as_admin() -> dict:
        """Логин админом из .env; токены → access_folder['admin']."""
        if not config.ADMIN_EMAIL or not config.ADMIN_PASSWORD:
            raise RuntimeError("ADMIN_EMAIL / ADMIN_PASSWORD не заданы в .env")
        auth = Auth.login(config.ADMIN_EMAIL, config.ADMIN_PASSWORD) or {}
        HttpClient.access_folder['admin'] = auth.get("accessToken")     # ← поле из паспорта
        HttpClient.access_folder['admin_refresh'] = auth.get("refreshToken")
        return auth

    # login_as_<роль>() — по одному методу на каждую роль из паспорта
```

Если есть refresh-эндпоинт — добавь `refresh_token()` по образцу
`src/example_auth.py`.

## Вариант B — Cookie-сессия

`HttpClient.session` — это `requests.Session()`: cookies сохраняются
автоматически после логина. Токены в `access_folder` не нужны,
`access=` в клиентах не передаётся.

```python
class Auth:

    @staticmethod
    def login(email: str, password: str, status_code: int = 200) -> None:
        """Логин: сервер ставит сессионную cookie, Session сохраняет её сам."""
        body = {"email": email, "password": password}
        url = config.BASE_URL + "/api/auth/login"
        response = HttpClient.post(url, body)
        assert response.status_code == status_code, f"Логин не удался: {response.text}"
        # cookies уже в HttpClient.session — больше ничего делать не нужно

    @staticmethod
    def login_as_admin() -> None:
        if not config.ADMIN_EMAIL or not config.ADMIN_PASSWORD:
            raise RuntimeError("ADMIN_EMAIL / ADMIN_PASSWORD не заданы в .env")
        Auth.login(config.ADMIN_EMAIL, config.ADMIN_PASSWORD)
```

ВАЖНО: одна Session = одна активная роль. Если тестам нужны параллельные
роли — обсуди с пользователем: отдельные Session-объекты на роль
(потребуется доработка HttpClient) или переключение логином.

## Вариант C — API-ключ в заголовке

Постоянный ключ, логина нет. Два способа:

1. **Через access_folder** (если ключ передаётся как Bearer):
   `HttpClient.access_folder['service'] = config.API_KEY` прямо в initialize.
2. **Свой заголовок** (X-API-KEY и т.п.): передавай headers в клиентах
   ресурсов ИЛИ адаптируй `HttpClient._build_headers` — добавь ветку,
   которая для `access="service"` ставит `X-API-KEY` вместо `Authorization`.
   Второй способ лучше, если ключ нужен почти во всех запросах.

## Адаптация Tests/conftest.py

Во всех вариантах `initialize` сводится к:

```python
@pytest.fixture(scope='session', autouse=True)
def initialize(app_data):
    """Бутстрап: авторизация всех ролей проекта (см. docs/project-profile.md)."""
    app_data['admin_auth'] = Auth.login_as_admin()
    # + по вызову на каждую роль из паспорта, если она нужна всем тестам;
    # редкие роли — отдельными function-scoped фикстурами
```

Импорт `ExampleAuth` замени на `from src.auth import Auth`.
