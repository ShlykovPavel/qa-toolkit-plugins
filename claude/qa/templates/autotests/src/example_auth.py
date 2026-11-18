"""example_auth.py — ПРИМЕР клиента авторизации. Адаптируйте под свой проект.

Способ авторизации у каждого проекта свой. Этот файл показывает паттерн:

  1. Метод login() делает запрос авторизации и возвращает тело ответа.
  2. Фикстура (Tests/conftest.py) кладёт токен в HttpClient.access_folder
     под именем роли — дальше все клиенты используют access="<роль>".
  3. Имена ролей выбираете сами: "admin", "user", "manager" — фиксированного
     списка нет.

Варианты под разные схемы авторизации:

  Bearer JWT (реализовано ниже):
      токен из тела ответа → access_folder["admin"]

  Cookie-сессия:
      HttpClient.session сохраняет cookies автоматически (requests.Session) —
      после login() дополнительно ничего делать не нужно, access= не передавайте.

  API-ключ в заголовке:
      постоянный ключ из config → передавайте headers={"X-API-KEY": ...}
      или адаптируйте HttpClient._build_headers.

Короткоживущий access-токен (минуты) и сессионный логин несовместимы: съют
длиннее срока жизни токена сыплется 401 в хвосте. HttpClient обновляет токен
сам, если логин роли зарегистрировал срок и способ перевыпуска —
см. _register_refresh ниже и HttpClient._refresh_if_expired. Не JWT (нет
поля exp) — регистрация пропускается, поведение как без неё.

При форке: переименуйте класс, поправьте URL/поля под свой API, при
необходимости добавьте методы логина для других ролей (и регистрируйте
обновление каждой роли тем же вызовом).
"""

import base64
import json
from typing import Callable, Optional

import config
from src.http_methods import HttpClient


def _jwt_exp(token: Optional[str]) -> Optional[int]:
    """unix-время истечения из payload JWT (поле exp) или None, если это не JWT.

    Подпись не проверяется — нужен только срок, доверие к токену даёт сервер.
    """
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        exp = json.loads(base64.urlsafe_b64decode(payload)).get("exp")
        return int(exp) if exp else None
    except Exception:
        return None


def _register_refresh(role: str, token: Optional[str], relogin: Callable[[], object]) -> None:
    """Сообщает HttpClient срок жизни токена роли и как его перевыпустить."""
    exp = _jwt_exp(token)
    if exp is None:
        return
    HttpClient.access_expiry[role] = exp
    HttpClient.token_providers[role] = relogin


class ExampleAuth:

    @staticmethod
    def login(email: str, password: str, status_code: int = 200) -> Optional[dict]:
        """Логин. Возвращает тело ответа (например, accessToken + refreshToken).

        При ожидаемой ошибке (status_code >= 400) возвращает None —
        не разыменовывайте результат в негативных тестах.
        """
        body = {"login": email, "password": password}
        url = config.BASE_URL + "/api/accounts/login"   # замените на свой эндпоинт
        response = HttpClient.post(url, body)
        assert response.status_code == status_code, f"Логин не удался: {response.text}"
        return HttpClient.parse_json(response)

    @staticmethod
    def refresh_token(access_token: str, refresh_token: str,
                      status_code: int = 200) -> Optional[dict]:
        """Обновляет access-токен по refresh-токену."""
        body = {"refreshToken": refresh_token, "accessToken": access_token}
        url = config.BASE_URL + "/api/accounts/refresh-tokens"  # замените на свой
        response = HttpClient.post(url, body)
        assert response.status_code == status_code, f"Обновление токена не удалось: {response.text}"
        return HttpClient.parse_json(response)

    @staticmethod
    def login_as_admin() -> dict:
        """Логин админом из .env и сохранение токенов под именем 'admin'.

        Это ОБРАЗЕЦ связки login + access_folder: после вызова любой клиент
        может делать HttpClient.get(url, access="admin").
        """
        if not config.ADMIN_EMAIL or not config.ADMIN_PASSWORD:
            raise RuntimeError(
                "ADMIN_EMAIL / ADMIN_PASSWORD не заданы в .env (см. config.py)"
            )
        auth = ExampleAuth.login(config.ADMIN_EMAIL, config.ADMIN_PASSWORD) or {}
        HttpClient.access_folder['admin'] = auth.get("accessToken")
        HttpClient.access_folder['admin_refresh'] = auth.get("refreshToken")
        # Перевыпуск — повторным логином: форму refresh-запроса знает только
        # ваш API (refresh_token выше — заготовка под неё).
        _register_refresh('admin', auth.get("accessToken"), ExampleAuth.login_as_admin)
        return auth
