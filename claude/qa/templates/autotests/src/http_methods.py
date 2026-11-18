"""Центральный HTTP-клиент.

Правила:
  - Токены никогда не передаются вручную — только через параметр access:
        HttpClient.get(url, access="admin")
    берёт токен из HttpClient.access_folder["admin"] и добавляет заголовок
    Authorization: Bearer <токен>.
  - Имена токенов ("admin", "user", ...) определяет ВАШ проект: фикстуры
    авторизации кладут токены в access_folder под выбранными именами
    (см. src/example_auth.py и Tests/conftest.py). Фиксированного списка нет.
  - Каждый запрос логируется (см. logger.py) и оборачивается в шаг Allure.
  - У каждого запроса есть таймаут (config.REQUEST_TIMEOUT) — зависший стенд
    не должен вешать прогон.
  - Отсутствие запрошенного токена — немедленная ошибка, а не запрос без
    авторизации (иначе тест упадёт с 401 в другом месте и запутает разбор).
  - Протухший токен обновляется САМ, до отправки запроса (см.
    _refresh_if_expired): access-токен часто живёт минуты, а логин —
    сессионная фикстура. Механизм включается, только если auth-клиент форка
    зарегистрировал срок и провайдера роли (access_expiry / token_providers).

Если авторизация вашего проекта не Bearer-токен (cookie, api-key заголовок,
Basic) — адаптируйте _build_headers под свой способ; остальное не трогайте.
"""

import json
import time
from typing import Optional
from urllib.parse import urlencode

import allure
import requests

import config
from logger import Logger

#: За сколько секунд до истечения токена его пора обновлять.
TOKEN_REFRESH_SKEW = 30


class HttpClient:
    #: Хранилище токенов сессии: {"имя_роли": "токен", ...}.
    #: Заполняется фикстурами авторизации (см. Tests/conftest.py).
    access_folder = {}

    #: Срок жизни токенов: {"имя_роли": unix-время истечения}. Заполняет
    #: auth-клиент форка при логине — сам HttpClient сюда ничего не пишет.
    access_expiry = {}

    #: Как перевыпустить протухший токен: {"имя_роли": вызываемый объект}.
    #: Регистрирует auth-клиент форка (эталон — src/example_auth.py); роль без
    #: записи здесь просто не обновляется.
    token_providers = {}

    #: Одна HTTP-сессия на процесс: переиспользование соединений (keep-alive).
    #: При pytest-xdist каждый воркер — отдельный процесс со своей сессией.
    session = requests.Session()

    @staticmethod
    def parse_url_for_host(url: str) -> str:
        return url.split("//")[1].split("/")[0]

    @classmethod
    def _refresh_if_expired(cls, access: str) -> None:
        """Перевыпускает токен роли, если он вот-вот истечёт.

        Нужно потому, что access-токен стенда часто живёт МИНУТЫ, а
        сессионная фикстура авторизации отрабатывает один раз за прогон:
        без обновления любой съют длиннее срока жизни токена разваливался бы
        на 401 в хвосте, причём в произвольных тестах — «плавающее» падение,
        которое легко списать на баг теста.

        Обновление ПРОАКТИВНОЕ (по времени), а не по ответу 401: повторять
        запрос после 401 нельзя — тест, который сам ожидает 401, получил бы
        совсем не то, что проверяет, а мутирующий запрос выполнился бы дважды.
        Роли без зарегистрированного провайдера (см. token_providers) просто
        пропускаются — поведение как раньше.
        """
        expiry = cls.access_expiry.get(access)
        provider = cls.token_providers.get(access)
        if not expiry or not provider:
            return
        if time.time() < expiry - TOKEN_REFRESH_SKEW:
            return
        provider()

    @classmethod
    def _build_headers(cls, url: str, headers: Optional[dict], access: Optional[str]) -> dict:
        """Собирает заголовки: Host всегда, Authorization — если задан access."""
        headers = dict(headers) if headers else {}
        headers['Host'] = cls.parse_url_for_host(url)

        if access is not None:
            cls._refresh_if_expired(access)
            token = cls.access_folder.get(access)
            if not token:
                raise RuntimeError(
                    f"Токен '{access}' отсутствует в HttpClient.access_folder. "
                    f"Проверьте, что фикстура авторизации отработала и положила "
                    f"токен под этим именем. "
                    f"Сейчас доступны: {list(cls.access_folder) or 'ни одного'}"
                )
            headers['Authorization'] = "Bearer " + token
        return headers

    @staticmethod
    def parse_json(response: requests.Response):
        """Безопасно разбирает тело ответа: JSON → объект, иначе None.

        Нужен для негативных сценариев: тело 404/500 может быть пустым или
        HTML — тест не должен умирать с JSONDecodeError вместо внятной ошибки.
        """
        if not response.text:
            return None
        try:
            return response.json()
        except (json.JSONDecodeError, ValueError):
            return None

    @classmethod
    def get(cls, url, headers=None, access: Optional[str] = None, query_params=None):
        """GET. Query-параметры — только через `query_params` (dict):
        requests сам кодирует значения (пробелы, кириллица, спецсимволы).
        Не собирайте query-строку руками через f-строки."""
        with allure.step("GET"):
            headers = cls._build_headers(url, headers, access)
            log_url = url
            if query_params:
                log_url += ("&" if "?" in url else "?") + urlencode(query_params, doseq=True)
            Logger.add_request(log_url, method="GET", headers=headers, body="None")
            result = cls.session.get(
                url, headers=headers, params=query_params,
                timeout=config.REQUEST_TIMEOUT,
            )
            Logger.add_response(result)
            return result

    @classmethod
    def post(cls, url, body, headers=None, access: Optional[str] = None, file=None):
        with allure.step("POST"):
            headers = cls._build_headers(url, headers, access)
            Logger.add_request(url, method="POST", headers=headers, body=body)
            result = cls.session.post(
                url, json=body, headers=headers, files=file,
                timeout=config.REQUEST_TIMEOUT,
            )
            Logger.add_response(result)
            return result

    @classmethod
    def put(cls, url, body, headers=None, access: Optional[str] = None):
        with allure.step("PUT"):
            headers = cls._build_headers(url, headers, access)
            Logger.add_request(url, method="PUT", headers=headers, body=body)
            result = cls.session.put(
                url, json=body, headers=headers,
                timeout=config.REQUEST_TIMEOUT,
            )
            Logger.add_response(result)
            return result

    @classmethod
    def patch(cls, url, body, headers=None, access: Optional[str] = None):
        with allure.step("PATCH"):
            headers = cls._build_headers(url, headers, access)
            Logger.add_request(url, method="PATCH", headers=headers, body=body)
            result = cls.session.patch(
                url, json=body, headers=headers,
                timeout=config.REQUEST_TIMEOUT,
            )
            Logger.add_response(result)
            return result

    @classmethod
    def delete(cls, url, body=None, headers=None, access: Optional[str] = None):
        """DELETE. `body` — опционально: часть API принимает тело у DELETE
        (например, массовое удаление по списку id) — RFC это не запрещает,
        requests поддерживает через json=."""
        with allure.step("DELETE"):
            headers = cls._build_headers(url, headers, access)
            Logger.add_request(url, method="DELETE", headers=headers,
                               body=body if body is not None else "None")
            result = cls.session.delete(
                url, json=body, headers=headers,
                timeout=config.REQUEST_TIMEOUT,
            )
            Logger.add_response(result)
            return result
