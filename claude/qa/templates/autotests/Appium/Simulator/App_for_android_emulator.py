import os
import subprocess
from logger import Logger
# apk_path = os.getenv("APK_PATH")
apk_package_name = os.getenv("ANDROID_APP_PACKAGE")
def install_apk_with_adb(apk_path, emulator_name):
    """
    Устанавливает APK на эмулятор с помощью adb install.

    :param apk_path: Путь к APK файлу.
    :param emulator_name: Имя эмулятора, если необходимо выбрать конкретный.
    """
    try:
        # Формируем команду
        command = ["adb"]
        command.extend(["-s", emulator_name, "install", apk_path])

        # Выполняем команду и собираем вывод
        result = subprocess.run(command, capture_output=True, text=True, check=True)

        # Проверяем вывод на успешную установку
        if "Success" in result.stdout:
            Logger.log_android_emulator("APK успешно установлен!")
            return "Success"
        else:
            Logger.log_android_emulator(f"Неожиданный вывод: {result.stdout}")
            return result.stdout
    except subprocess.CalledProcessError as e:
        # Выводим ошибки, если установка не удалась
        Logger.log_android_emulator(f"Ошибка установки APK: {e.stderr.strip()}")
        return e.stderr.strip()



def launch_apk_with_adb(apk_package_name, emulator_name):
    """
    Запускает APK на эмулятор с помощью adb shell.

    :param apk_package_name: Имя пакета приложения (например, com.example.app).
    :param emulator_name: Имя устройства/эмулятора (опционально).
    :return: True, если приложение успешно запустилось, иначе False.
    """
    try:
        # Формируем команду для запуска приложения
        command = ["adb"]
        command.extend(["-s", emulator_name, "shell", "monkey", "-p", apk_package_name, "-c", "android.intent.category.LAUNCHER", "1"])
        # Выполняем команду
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        # Проверяем, есть ли ошибки в выводе
        if "Events injected: 1" in result.stdout:
            Logger.log_android_emulator(f"Приложение {apk_package_name} успешно запустилось.")
            return True
        else:
            Logger.log_android_emulator(f"Не удалось запустить приложение {apk_package_name}.")
            return False
    except subprocess.CalledProcessError as e:
        Logger.log_android_emulator(f"Ошибка при запуске: {e}")
        return False