import os
import subprocess
import time
from logger import Logger
"""Для запуска эмулятора в PATH должны быть пути ANDROID_HOME(Она должна указывать на каталог Android SDK.) и emulator и adb(export PATH=$ANDROID_HOME/emulator:$ANDROID_HOME/platform-tools:$PATH)"""


def set_android_env():
    android_home = os.getenv("ANDROID_HOME_FOR_SIM_LAUNCH")
    os.environ["ANDROID_HOME"] = android_home
    os.environ["PATH"] = f"{android_home}/emulator:{android_home}/platform-tools:" + os.environ["PATH"]


def launch_emulator(emulator_name, no_window=False, no_data_save=False, wipe_data=False):
    try:

        # set_android_env()

        Logger.log_android_emulator(f"ANDROID_HOME: {os.environ.get('ANDROID_HOME')}")
        Logger.log_android_emulator(f"PATH: {os.environ.get('PATH')}")
        command = ["emulator", "-avd", emulator_name]
        # Запуск эмулятора без отображения окна с ui
        if no_window == True:
            command.extend(["-no-window"])
        # Запуск эмулятрова без сохранения состояния (что б эмулятор запускался не в состоянии после прошлого выключения)
        if no_data_save == True:
            command.extend(["-no-snapshot-save"])
        # Эта настройка сбрасывает данные эмулятора к первоначальному состоянию (эмулятор будет запускаться дольше)
        if wipe_data == True:
            command.extend(["-wipe-data"])
        # Запуск симулятора
        subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Ожидание запуска симулятора
        is_emulator_ready()
    except Exception as e:
        Logger.log_android_emulator(f"Ошибка при запуске симулятора: {e}")


def is_emulator_ready(timeout=120):
    emulator_name = await_adb_devices()
    if not emulator_name:
        Logger.log_android_emulator("Эмулятор не найден. Прервано ожидание.")
        return False
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # Проверяем состояние устройства
            result = subprocess.run(
                ["adb", "-s", emulator_name, "shell", "getprop", "sys.boot_completed"],
                capture_output=True,
                text=True,
            )
            if result.stdout.strip() == "1":
                Logger.log_android_emulator("Эмулятор готов!")
                return True
        except Exception as e:
            Logger.log_android_emulator(f"Ошибка: {e}")
        time.sleep(5)  # Ждем 5 секунд перед следующей проверкой
    Logger.log_android_emulator("Эмулятор не успел запуститься.")
    return False


def get_adb_devices():
    try:

        get_emulator_name = subprocess.run(["adb", "devices"], capture_output=True, text=True)
        device_lines = get_emulator_name.stdout.strip().split("\n")[
                       1:]

        # Фильтруем устройства с "emulator" в названии
        emulator_names = [line.split("\t")[0] for line in device_lines if "emulator" in line and "\t" in line]
        Logger.log_android_emulator(f"Список устройств: {emulator_names}")

        if emulator_names:  # Если хотя бы одно устройство найдено
            return emulator_names[0]  # Возвращаем первый найденный эмулятор

        return None

    except Exception as e:
        Logger.log_android_emulator(f"Ошибка при получении списка устройств: {e}")
        return None


def await_adb_devices():
    try:
        for _ in range(20):
            emulator_name = get_adb_devices()
            if emulator_name:
                return emulator_name

            time.sleep(5)  # Ждем 5 секунд перед повторной проверкой

        Logger.log_android_emulator("Эмулятор не появился в списке устройств.")
        return None
    except Exception as e:
        Logger.log_android_emulator(f"Ошибка при получении списка устройств: {e}")
        return None


def stop_emulator(emulator_name):
    try:
        if not emulator_name:
            Logger.log_android_emulator("Эмулятор не указан. Остановка невозможна.")
            return

        # Команда остановки эмулятора
        stop_command = subprocess.run(
            ["adb", "-s", emulator_name, "emu", "kill"],
            check=True,
            capture_output=True,
            text=True
        )
        stop_response = stop_command.stdout.strip().split("\n")[0]
        Logger.log_android_emulator(f"Симулятор остановлен: {stop_response}")

        # Проверяем ответ команды остановки
        if "OK: killing emulator, bye bye" not in stop_response:
            raise ValueError("Эмулятор не подтвердил остановку.")

        wait_for_emulator_kill(emulator_name)

    except Exception as e:
        Logger.log_android_emulator(f"Ошибка при остановке симулятора: {e}")

def wait_for_emulator_kill(emulator_name):
    # Цикл проверки остановки эмулятора
    for attempt in range(10):  # Проверяем до 10 раз с паузой в 10 секунд
        devices = get_adb_devices()
        if devices and emulator_name in devices:
            Logger.log_android_emulator(f"Попытка {attempt + 1}: Эмулятор ещё работает, ожидаем...")
            time.sleep(10)
        else:
            Logger.log_android_emulator("Эмулятор успешно остановлен.")
            return

    # Если цикл завершился, но устройство не остановилось
    raise TimeoutError("Эмулятор не успел остановиться в установленное время.")