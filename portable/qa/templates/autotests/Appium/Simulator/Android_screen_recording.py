import os
import subprocess
import datetime


class ScreenRecorder:
    """
    emulator_name - имя эмулятора, которому будет записано видео
    local_save_path - локальный путь, куда будет сохранено видео
    remote_path - путь на эмуляторе, куда будет сохранено видео
    process - сам процесс записи видео с которым мы можем взаимодействовать
    timestamp - текущая дата и время
    """

    def __init__(self, emulator_name, local_save_path=None):
        self.emulator_name = emulator_name
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.remote_path = os.getenv('REMOTE_PATH_IN_EMULATOR')
        self.local_path = local_save_path or f"{self.file_dir}/screenrecord_{timestamp}.mp4"
        self.process = None

    def start_recording(self):
        """
        Запускает запись экрана.
        """
        try:
            command = (["adb", "-s", self.emulator_name, "shell", "screenrecord", self.remote_path])
            self.process = subprocess.Popen(command)
            print(f"Запись экрана начата и сохраняется в {self.remote_path}.")
        except Exception as e:
            print(f"Ошибка при запуске записи экрана: {e}")

    def stop_recording(self):
        """
        Останавливает запись экрана и сохраняет файл локально.
        """
        if self.process:
            try:
                self.process.terminate()
                self.process.wait()
                command = (["adb", "-s", self.emulator_name, "pull", self.remote_path, self.local_path])
                subprocess.run(command, check=True)
                print(f"Видео сохранено локально в {self.local_path}.")
            except Exception as e:
                print(f"Ошибка при остановке записи экрана: {e}")
        else:
            print("Процесс записи не был запущен.")
