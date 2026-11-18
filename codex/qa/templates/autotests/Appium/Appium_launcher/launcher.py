import subprocess
import requests
import time
import shutil
import psutil
from logger import Logger


def ensure_appium_running(host="http://localhost", port=4723, appium_command="appium"):
    """
    Проверяет, запущен ли Appium сервер. Если нет, пытается запустить его и пишет логи в файл.

    :param host: Хост Appium сервера.
    :param port: Порт Appium сервера.
    :param appium_command: Команда для запуска Appium. Можно указать путь к appium, если он не в PATH.
    """
    appium_url = f"{host}:{port}/status"

    try:
        response = requests.get(appium_url, timeout=3)
        if response.status_code == 200:
            Logger.log_appium_server("Appium сервер уже запущен.")
            return
    except (requests.ConnectionError, requests.Timeout):
        Logger.log_appium_server("Appium сервер не запущен. Запускаем...")

    try:
        if not shutil.which(appium_command):
            raise RuntimeError(f"Appium не найден. Проверьте PATH или укажите полный путь к '{appium_command}'.")

        # Используем лог-файл из Logger
        with open(Logger.appium_log, 'a', encoding='utf-8') as log_file:
            process = subprocess.Popen(
                [appium_command],
                stdout=log_file,
                stderr=log_file,
                shell=True
            )
            Logger.log_appium_server(f"Appium сервер запускается... Логи записываются в '{Logger.appium_log}'.")

            # Ожидание запуска сервера
            for _ in range(10):
                try:
                    response = requests.get(appium_url, timeout=3)
                    if response.status_code == 200:
                        Logger.log_appium_server("Appium сервер успешно запущен.")
                        return
                except (requests.ConnectionError, requests.Timeout):
                    time.sleep(1)
                    Logger.log_appium_server("Неудачная попытка запуска Appium сервера.")

        raise RuntimeError("Не удалось запустить Appium сервер.")
    except Exception as e:
        Logger.log_appium_server(f"Ошибка при запуске Appium: {e}")
        raise



def stop_appium_server():
    """
    Завершает процессы Appium сервера.
    """
    try:
        # Список процессов, которые нужно найти и остановить
        appium_processes = ['node', 'adb']

        for process in psutil.process_iter(attrs=["pid", "name"]):
            if process.info["name"] in appium_processes:
                Logger.log_appium_server(
                    f"Завершаем процесс {process.info['name']} (PID: {process.info['pid']})..."
                )
                process.terminate()
                process.wait(timeout=5)
                Logger.log_appium_server(
                    f"Процесс {process.info['name']} (PID: {process.info['pid']}) успешно завершен."
                )
                appium_processes.remove(process.info["name"])

        # Логируем оставшиеся незавершённые процессы
        if appium_processes:  # Проверяем, есть ли в списке не найденные процессы
            for a in appium_processes:
                Logger.log_appium_server(f"Процесс {a} не найден или не завершен.")
    except Exception as e:
        Logger.log_appium_server(f"Ошибка при остановке Appium серверов: {e}")


def graceful_shutdown(signum, frame):
    """
    Обработчик сигналов, который завершает Appium сервер и корректно завершает процесс.

    :param signum: Номер полученного сигнала (например, SIGINT или SIGTERM).
    :param frame: Текущая точка выполнения (используется редко, но автоматически передается).
    """
    Logger.log_appium_server(f"Получен сигнал {signum}. Завершаем Appium сервер...")
    stop_appium_server()  # Завершение работы Appium сервера
    exit(0)  # Завершаем текущий процесс с кодом 0 (успех)
