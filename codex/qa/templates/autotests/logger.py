"""Файловый логгер: каждый HTTP-запрос/ответ и каждое мобильное действие
пишутся в logs/log_<время>_<pid>.log.

PID в имени файла нужен для параллельного запуска (pytest-xdist):
каждый воркер — отдельный процесс и отдельный файл, без гонок за запись.
"""

import datetime
import os
from requests import Response


class Logger:
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    _stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    file_name = f"logs/log_{_stamp}_{os.getpid()}.log"
    appium_log = f"logs/appium_log_{_stamp}_{os.getpid()}.log"

    @classmethod
    def write_log_to_file(cls, data: str):
        with open(cls.file_name, 'a', encoding='utf-8') as logger_file:
            logger_file.write(data)

    @staticmethod
    def _mask_headers(headers) -> dict:
        """Маскирует Authorization, чтобы токены не лежали в логах открытым текстом."""
        if not isinstance(headers, dict):
            return headers
        masked = dict(headers)
        auth = masked.get('Authorization')
        if auth:
            # Оставляем только схему (Bearer/Basic), сам токен не логируем
            scheme = auth.split(' ')[0] if ' ' in auth else ''
            masked['Authorization'] = f"{scheme} <скрыто>".strip()
        return masked

    @classmethod
    def add_request(cls, url: str, method: str, headers, body):
        test_name = os.environ.get('PYTEST_CURRENT_TEST')
        data_to_add = "\n-----\n"
        data_to_add += f"Test: {test_name}\n"
        data_to_add += f"Time: {datetime.datetime.now()}\n"
        data_to_add += f"Request method: {method}\n"
        data_to_add += f"Request URL: {url}\n"
        data_to_add += f"Request Headers: {cls._mask_headers(headers)}\n"
        data_to_add += f"Request Body: {body}\n"
        data_to_add += "\n"
        cls.write_log_to_file(data_to_add)

    @classmethod
    def add_response(cls, result: Response):
        cookies_as_dict = dict(result.cookies)
        headers_as_dict = dict(result.headers)
        data_to_add = f"Response code: {result.status_code}\n"
        data_to_add += f"Response text: {result.text}\n"
        data_to_add += f"Response headers: {headers_as_dict} \n"
        data_to_add += f"Response cookies: {cookies_as_dict}\n"
        data_to_add += "\n-----\n"
        cls.write_log_to_file(data_to_add)

    @classmethod
    def log_mobile_action(cls, message):
        test_name = os.environ.get('PYTEST_CURRENT_TEST')
        data_to_add = f"Mobile Action in test: {test_name}\n"
        data_to_add += f"Time: {datetime.datetime.now()}\n"
        data_to_add += f"Action: {message}\n\n"
        cls.write_log_to_file(data_to_add)

    @classmethod
    def log_appium_server(cls, message):
        data_to_add = f"Appium Server: {message}\n"
        print(data_to_add)
        cls.write_log_to_file(data_to_add)

    @classmethod
    def log_android_emulator(cls, message):
        data_to_add = f"Android Emulator: {message}\n"
        print(data_to_add)
        cls.write_log_to_file(data_to_add)
