#!/usr/bin/env python3
"""Извлечение стабильных идентификаторов элементов из XML-дампа экрана —
«глаза» при написании мобильных app_keys (см. docs/mobile.md).

Три режима:

1. Разбор ГОТОВОГО дампа (без драйвера и эмулятора) — основной для случая
   «дамп снял коллега» и для проверки заготовленных фикстур:

       python ${CLAUDE_PLUGIN_ROOT}/bin/dump_ui_tree.py --from-file screen.xml

2. ПРОХОД СЦЕНАРИЯ (--walkthrough) — дефолт для написания тест-кейса:
   ОДНА Appium-сессия на весь сценарий (между шагами приложение НЕ
   перезапускается — каждый новый запуск скрипта пересоздавал бы сессию
   и терял состояние экрана), человек проходит кейс руками и после
   каждого шага жмёт Enter в терминале — скрипт снимает XML-дамп +
   скриншот шага в папку и пишет steps.json с последовательностью шагов:

       python ${CLAUDE_PLUGIN_ROOT}/bin/dump_ui_tree.py --walkthrough dumps/create_task

   2а. ПРОХОД ПО СЦЕНАРИЮ-ФАЙЛУ (--walkthrough DIR --script FILE) — агент
   за рулём без appium-mcp: шаги описаны JSON-файлом, скрипт сам выполняет
   их в той же одной сессии и снимает дамп+скриншот после каждого шага.
   Упавший шаг снимается как step_NN_<имя>_FAILED и останавливает проход
   (код выхода 2) — дамп момента падения и есть диагностика. Формат шага:

       {"name": "open_form", "tap": "<id>", "wait_for": "<id>", "timeout": 20}
       {"name": "email", "type": "<id>", "text": "..."}   # или "text_env": "ИМЯ_ПЕРЕМЕННОЙ"
       {"name": "back", "back": true}
       {"name": "start"}                                  # только снимок

   Действие — не больше одного из tap/type/back; `wait_for` — ожидание
   идентификатора ПОСЛЕ действия (по умолчанию 15 с). Шаг `type` сам
   кликает по полю перед вводом (на Android без фокуса текст молча не
   вводится) — отдельный `tap`-шаг на то же поле не нужен. Элементы ищутся
   только по стабильному идентификатору, как в тестовом слое. Введённые
   значения в steps.json не пишутся, НО XML-дамп шага хранит текст обычного
   поля в атрибуте value — секрет безопасен только в поле пароля (там
   точки). Папка прохода — рабочий артефакт, в git не идёт (dumps/).

       python ${CLAUDE_PLUGIN_ROOT}/bin/dump_ui_tree.py --walkthrough dumps/login --script login.json --reset-app

3. Один снимок (без --from-file и --walkthrough): поднимает драйвер,
   по желанию ждёт, пока человек откроет нужный экран руками, снимает
   page_source — для случая «нужен один конкретный экран»:

       python ${CLAUDE_PLUGIN_ROOT}/bin/dump_ui_tree.py --wait-manual 30 --raw-out screen.xml

Живые режимы (2, 2а и 3) берут драйвер из фабрики Appium/driver_func.py
(конфигурация — env, как у тестов). `--reset-app` перед созданием сессии
возвращает приложение в состояние чистой установки: iOS-симулятор —
`simctl uninstall` + `install` (IOS_UDID, IOS_BUNDLE_ID, IOS_APP_PATH),
Android — `adb shell pm clear` (ANDROID_APP_PACKAGE). Без него второй
проход начинается с экрана, на котором закончился первый.

Поддерживаемые стили XML (структуры РАЗНЫЕ, поэтому парсер обходит все
элементы независимо от имени тега и смотрит только атрибуты):
  - Appium UiAutomator2 page_source: теги — имена классов
    (<android.widget.Button resource-id="..."/>);
  - adb uiautomator dump: теги <node class="..." resource-id="..."/>;
  - iOS XCUITest: <XCUIElementTypeButton name="..."/>.

Что извлекается:
  - Android resource-id — и полная форма `<pkg>:id/<ключ>` (нативные View),
    и голая строка (Flutter Semantics); в выводе ключ нормализован до
    голой формы, источник помечен "resource-id";
  - iOS `name` (= accessibilityIdentifier), источник "name";
  - `content-desc` (Android accessibility-описание) — отдельным типом
    "content-desc": это НЕ идентификатор из контракта, но полезная зацепка,
    что элементу нужен нормальный id.

Выход — JSON в stdout:
    {"keys": [{"key": "app_login_submit_button", "source": "resource-id"}, ...],
     "count": N, "no_keys_found": false}
Идентификаторы уникальны по (key, source), порядок — первое вхождение.
Если идентификаторов не найдено — no_keys_found: true и код выхода 1
(экран без id = блокер, см. docs/locator-conventions.md).
"""

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET
from pathlib import Path

# Корень проекта в sys.path: Python кладёт туда только папку скрипта (bin/ плагина),
# и живые режимы падали бы на `import Appium`. Скрипт запускают из корня проекта.
sys.path.insert(0, str(Path.cwd()))

#: Ожидание `wait_for` в сценарии, если у шага не задан `timeout`, секунды.
DEFAULT_WAIT_TIMEOUT = 15

SCENARIO_ACTIONS = ('tap', 'type', 'back')
SCENARIO_KEYS = {'name', 'tap', 'type', 'back', 'text', 'text_env', 'wait_for', 'timeout'}


def extract_keys(xml_text: str, pattern: str = None) -> list:
    """Извлекает идентификаторы из XML-дампа экрана.

    Обходит ВСЕ элементы (root.iter()) и смотрит только атрибуты — так
    парсер переживает все три стиля дампа (page_source / adb / XCUITest).

    :param xml_text: сырой XML дампа
    :param pattern: regex-фильтр по значению ключа (например r'app_task')
    :return: список {"key": ..., "source": "resource-id"|"name"|"content-desc"}
             без дублей, в порядке первого вхождения
    """
    root = ET.fromstring(xml_text)
    compiled = re.compile(pattern) if pattern else None

    seen = set()
    keys = []
    for node in root.iter():
        for attr, source in (('resource-id', 'resource-id'),
                             ('name', 'name'),
                             ('content-desc', 'content-desc')):
            value = (node.get(attr) or '').strip()
            if not value:
                continue
            if source == 'resource-id':
                # Нормализация: полная форма <pkg>:id/<ключ> → голый ключ
                value = value.split(':id/', 1)[-1]
            if compiled and not compiled.search(value):
                continue
            if (value, source) in seen:
                continue
            seen.add((value, source))
            keys.append({"key": value, "source": source})
    return keys


def _sanitize_step_name(name: str) -> str:
    """Имя шага → безопасный кусок имени файла (кириллица сохраняется)."""
    return re.sub(r'[^\w-]+', '_', name.strip()).strip('_')[:40]


def _snapshot(driver, out_dir: str, base: str, pattern: str = None) -> dict:
    """Дамп + скриншот текущего экрана в out_dir под именем base."""
    xml_text = driver.page_source
    with open(os.path.join(out_dir, base + '.xml'), 'w', encoding='utf-8') as f:
        f.write(xml_text)

    screenshot = None
    try:
        png = driver.get_screenshot_as_png()
        screenshot = base + '.png'
        with open(os.path.join(out_dir, screenshot), 'wb') as f:
            f.write(png)
    except Exception as e:
        print(f"Скриншот {base} не снялся (не страшно): {e}", file=sys.stderr)

    keys = extract_keys(xml_text, pattern=pattern)
    return {"xml": base + '.xml', "screenshot": screenshot, "keys": keys, "count": len(keys)}


def load_scenario(path: str) -> list:
    """Читает и проверяет сценарий-файл ДО создания сессии.

    Ошибка формата или незаданная переменная `text_env` — ValueError сразу:
    упасть на пятом шаге живого прохода из-за опечатки в файле дороже.
    Значение `text_env` подставляется в поле `text` (в файле его нет).
    """
    with open(path, 'r', encoding='utf-8') as f:
        steps = json.load(f)
    if not isinstance(steps, list) or not steps:
        raise ValueError("сценарий — непустой JSON-список шагов")

    for number, step in enumerate(steps, 1):
        where = f"шаг {number}"
        if not isinstance(step, dict):
            raise ValueError(f"{where}: ожидается объект")
        unknown = set(step) - SCENARIO_KEYS
        if unknown:
            raise ValueError(f"{where}: неизвестные поля {sorted(unknown)}")
        if not str(step.get('name', '')).strip():
            raise ValueError(f"{where}: нужно поле name")
        actions = [a for a in SCENARIO_ACTIONS if step.get(a)]
        if len(actions) > 1:
            raise ValueError(f"{where}: не больше одного действия из tap/type/back, а тут {actions}")
        if 'timeout' in step and not isinstance(step['timeout'], (int, float)):
            raise ValueError(f"{where}: timeout — число секунд")
        if step.get('type'):
            if 'text_env' in step:
                value = os.getenv(step['text_env'])
                if value is None:
                    raise ValueError(f"{where}: переменная окружения {step['text_env']} не задана")
                step['text'] = value
            if 'text' not in step:
                raise ValueError(f"{where}: для type нужно text или text_env")
    return steps


class ScreenScenarioActions:
    """Действия сценария поверх ScreenActions: только стабильные идентификаторы."""

    def __init__(self, driver, screen=None):
        if screen is None:
            from Appium.app_keys.screen_actions import ScreenActions

            screen = ScreenActions(driver)
        self.screen = screen

    def tap(self, key):
        self.screen.click_element(self.screen.get_element(key))

    def type(self, key, text):
        """Кликает по полю и вводит текст.

        Клик обязателен: на Android `send_keys` без фокуса молча ничего не
        вводит — шаг отчитывается `status: "ok"`, а поле остаётся пустым, и
        падает уже следующий шаг. На iOS клик по полю безвреден. Локатор
        перезапрашивается после клика: узел под одним идентификатором
        меняет класс и свойства по ходу взаимодействия.
        """
        self.screen.click_element(self.screen.get_element(key))
        self.screen.type_text(self.screen.get_element(key), text)

    def back(self):
        self.screen.go_back()

    def wait_for(self, key, timeout):
        from src.wait_utils import wait_until

        wait_until(lambda: self.screen.get_element(key), timeout=timeout, interval=1,
                   message=f"Не дождались элемента {key}")


def run_scripted_walkthrough(driver, out_dir: str, steps: list, pattern: str = None,
                             actions=None) -> list:
    """Проход по сценарию-файлу: действие → ожидание → дамп, шаг за шагом.

    :param steps: результат load_scenario
    :param actions: объект с tap/type/back/wait_for (подменяется в тестах)
    :return: список шагов (то же, что уходит в steps.json); у упавшего шага
             status=failed и error, после него проход не продолжается
    """
    os.makedirs(out_dir, exist_ok=True)
    actions = actions or ScreenScenarioActions(driver)
    done = []
    for number, step in enumerate(steps, 1):
        base = f"step_{number:02d}_{_sanitize_step_name(step['name'])}"
        record = {"step": number, "name": step['name'],
                  "action": next((a for a in SCENARIO_ACTIONS if step.get(a)), None),
                  "target": step.get('tap') or step.get('type'),
                  "wait_for": step.get('wait_for'), "status": "ok"}
        try:
            if step.get('tap'):
                actions.tap(step['tap'])
            elif step.get('type'):
                actions.type(step['type'], step['text'])
            elif step.get('back'):
                actions.back()
            if step.get('wait_for'):
                actions.wait_for(step['wait_for'], step.get('timeout', DEFAULT_WAIT_TIMEOUT))
        except Exception as e:
            record.update(status="failed", error=str(e)[:500])
            record.update(_snapshot(driver, out_dir, base + '_FAILED', pattern))
            done.append(record)
            print(f"Шаг {number} «{step['name']}» упал: {e}. Проход остановлен, "
                  f"дамп момента падения — {base}_FAILED.xml", file=sys.stderr)
            break
        record.update(_snapshot(driver, out_dir, base, pattern))
        done.append(record)
        print(f"Шаг {number} снят: {base}.xml ({record['count']} идентификаторов)",
              file=sys.stderr)

    with open(os.path.join(out_dir, 'steps.json'), 'w', encoding='utf-8') as f:
        json.dump(done, f, ensure_ascii=False, indent=2)
    return done


def open_session():
    """Живая Appium-сессия так же, как у фикстуры `driver` тестов.

    Сразу после создания закрывается системный алерт разрешений: после чистой
    установки iOS показывает его поверх приложения, он глотает тапы, а в
    page_source приложения его нет — проход падал на первом же тапе при
    нормальных границах кнопки. Нет алерта — вызов ничего не делает.
    """
    from Appium.driver_func import DriverFunctions

    driver = DriverFunctions.driver()
    DriverFunctions.allow_notifications(driver)
    return driver


def reset_app(run=subprocess.run) -> None:
    """Возвращает приложение в состояние чистой установки (до создания сессии).

    Нужные переменные проверяются до первой команды: наполовину выполненный
    сброс (удалили, но не поставили) хуже, чем никакого.
    """
    platform = (os.getenv('PLATFORM') or '').lower()
    if platform == 'ios':
        names = ('IOS_UDID', 'IOS_BUNDLE_ID', 'IOS_APP_PATH')
    elif platform == 'android':
        names = ('ANDROID_APP_PACKAGE',)
    else:
        raise ValueError(f"--reset-app: неподдерживаемая платформа {os.getenv('PLATFORM')!r}")
    env = {n: os.getenv(n) for n in names}
    missing = [n for n, v in env.items() if not v]
    if missing:
        raise ValueError(f"--reset-app: не заданы {', '.join(missing)} в .env")

    if platform == 'ios':
        commands = [
            ['xcrun', 'simctl', 'uninstall', env['IOS_UDID'], env['IOS_BUNDLE_ID']],
            ['xcrun', 'simctl', 'install', env['IOS_UDID'], env['IOS_APP_PATH']],
        ]
    else:
        commands = [['adb', 'shell', 'pm', 'clear', env['ANDROID_APP_PACKAGE']]]

    for cmd in commands:
        result = run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"--reset-app: {' '.join(cmd)} → {result.stderr.strip()}")
    print("Приложение сброшено до чистой установки.", file=sys.stderr)


def run_walkthrough(driver, out_dir: str, pattern: str = None,
                    input_fn=input) -> list:
    """Проход сценария: на каждый шаг человека — дамп + скриншот в out_dir.

    Одна живая сессия на весь проход. Человек делает шаг на устройстве,
    возвращается в терминал, вводит имя шага (или пустую строку) и Enter —
    снимается XML-дамп и скриншот текущего состояния. `q` — закончить.

    :param driver: живой Appium-драйвер (или совместимый объект в тестах)
    :param out_dir: папка результатов (step_NN_*.xml/.png + steps.json)
    :param pattern: regex-фильтр ключей для steps.json
    :param input_fn: источник ввода (подменяется в смоуке без эмулятора)
    :return: список шагов (то же, что уходит в steps.json)
    """
    os.makedirs(out_dir, exist_ok=True)
    print(
        "Проход сценария начат — приложение запущено, сессия одна на весь "
        "проход.\n"
        "Доведи приложение руками до НАЧАЛА сценария, затем по циклу:\n"
        "  1) сделай очередной шаг на устройстве;\n"
        "  2) вернись сюда, введи короткое имя шага (например: "
        "otkryl_formu) и нажми Enter — сниму дамп и скриншот.\n"
        "     Пустой Enter — тоже снимет (имя будет step_NN).\n"
        "Когда сценарий пройден — введи q и Enter.",
        file=sys.stderr,
    )
    steps = []
    while True:
        try:
            line = input_fn()
        except EOFError:
            break
        if line.strip().lower() in ('q', 'quit', 'exit'):
            break

        number = len(steps) + 1
        suffix = _sanitize_step_name(line)
        base = f"step_{number:02d}" + (f"_{suffix}" if suffix else "")

        shot = _snapshot(driver, out_dir, base, pattern)
        steps.append({"step": number, "name": line.strip() or base, **shot})
        print(f"Шаг {number} снят: {base}.xml "
              f"({shot['count']} идентификаторов). Следующий шаг или q.",
              file=sys.stderr)

    with open(os.path.join(out_dir, 'steps.json'), 'w', encoding='utf-8') as f:
        json.dump(steps, f, ensure_ascii=False, indent=2)
    print(f"Готово: {len(steps)} шагов в {out_dir} (+ steps.json). "
          f"Отдай агенту папку целиком.", file=sys.stderr)
    return steps


def read_dump_from_file(path: str) -> str:
    """Читает готовый XML-дамп из файла."""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def read_dump_from_device(wait_manual: int = 0) -> str:
    """Живой режим: снимает page_source через Appium-драйвер (env-конфиг).

    :param wait_manual: пауза в секундах — человек руками открывает нужный
                        экран (навигация не автоматизируется намеренно)
    """
    driver = open_session()
    try:
        if wait_manual:
            print(f"Открой нужный экран на устройстве — снимаю дамп через "
                  f"{wait_manual} с...", file=sys.stderr)
            # Осознанный sleep: ждём ЧЕЛОВЕКА, а не асинхронное событие
            time.sleep(wait_manual)
        return driver.page_source
    finally:
        driver.quit()


def main():
    parser = argparse.ArgumentParser(
        description="Извлечение стабильных идентификаторов элементов из "
                    "XML-дампа экрана (Appium page_source / adb uiautomator "
                    "dump / XCUITest). Режимы: --from-file — разбор готового "
                    "дампа; --walkthrough — проход сценария (одна сессия, "
                    "дамп+скриншот на каждый шаг человека); без обоих — один "
                    "снимок с живого устройства (env-конфигурация как у тестов).",
        epilog='Выход: JSON {"keys": [{"key", "source"}], "count", '
               '"no_keys_found"} (в --walkthrough вместо keys — список шагов; '
               'подробности по шагам — в <папка>/steps.json); source: '
               'resource-id (Android, ключ нормализован до голой формы) | '
               'name (iOS accessibilityIdentifier) | content-desc (не id из '
               'контракта, а зацепка). Нет идентификаторов -> '
               'no_keys_found=true, код выхода 1.',
    )
    parser.add_argument('--from-file', metavar='PAGE_SOURCE_XML',
                        help='разобрать готовый XML-дамп вместо снятия с устройства')
    parser.add_argument('--walkthrough', metavar='DIR',
                        help='проход сценария: одна сессия, на каждый шаг человека '
                             '(Enter в терминале) дамп+скриншот в DIR + steps.json')
    parser.add_argument('--script', metavar='SCENARIO_JSON',
                        help='с --walkthrough: шаги выполняет скрипт по файлу сценария '
                             '(агент за рулём без appium-mcp), дамп после каждого шага')
    parser.add_argument('--reset-app', action='store_true',
                        help='живые режимы: до сессии вернуть приложение к чистой установке '
                             '(iOS — simctl uninstall+install, Android — pm clear)')
    parser.add_argument('--pattern', metavar='REGEX',
                        help='фильтр ключей по regex (например app_task)')
    parser.add_argument('--wait-manual', type=int, default=0, metavar='SEC',
                        help='режим одного снимка: пауза, чтобы человек открыл нужный экран руками')
    parser.add_argument('--raw-out', metavar='FILE',
                        help='режим одного снимка: сохранить сырой XML дампа в файл')
    args = parser.parse_args()

    if args.walkthrough and args.from_file:
        parser.error('--walkthrough и --from-file несовместимы')
    if args.walkthrough and (args.wait_manual or args.raw_out):
        parser.error('--wait-manual/--raw-out — только для режима одного '
                     'снимка (в --walkthrough паузами управляет человек, '
                     'файлы шагов пишутся в папку сами)')
    if args.script and not args.walkthrough:
        parser.error('--script задаёт шаги прохода — нужен и --walkthrough DIR (куда писать дампы)')
    if args.reset_app and args.from_file:
        parser.error('--reset-app — только для живых режимов, не для --from-file')

    if not args.from_file:
        import config  # noqa: F401 — загружает .env: драйвер и --reset-app читают env

    if args.reset_app:
        reset_app()

    if args.script:
        steps = load_scenario(args.script)  # до сессии: опечатка в файле не стоит прохода
        driver = open_session()
        try:
            done = run_scripted_walkthrough(driver, args.walkthrough, steps, pattern=args.pattern)
        finally:
            driver.quit()
        failed = [s for s in done if s["status"] == "failed"]
        total = sum(s["count"] for s in done)
        print(json.dumps({
            "mode": "scripted_walkthrough",
            "dir": args.walkthrough,
            "steps": [{k: s.get(k) for k in ("step", "name", "status", "error", "xml", "count")}
                      for s in done],
            "planned": len(steps),
            "count": total,
            "no_keys_found": total == 0,
        }, ensure_ascii=False, indent=2))
        return 2 if failed else (1 if total == 0 else 0)

    if args.walkthrough:
        from Appium.driver_func import DriverFunctions

        driver = open_session()
        stop_ping = threading.Event()

        def _ping():
            # Человек между шагами думает дольше newCommandTimeout
            # Appium-сервера — пингуем сессию, чтобы не протухла
            while not stop_ping.wait(30):
                DriverFunctions.keep_alive(driver)

        threading.Thread(target=_ping, daemon=True).start()
        try:
            steps = run_walkthrough(driver, args.walkthrough, pattern=args.pattern)
        finally:
            stop_ping.set()
            driver.quit()

        total = sum(s["count"] for s in steps)
        result = {
            "mode": "walkthrough",
            "dir": args.walkthrough,
            "steps": [{"step": s["step"], "name": s["name"], "xml": s["xml"],
                       "screenshot": s["screenshot"], "count": s["count"]}
                      for s in steps],
            "count": total,
            "no_keys_found": total == 0,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if total == 0 else 0

    if args.from_file:
        xml_text = read_dump_from_file(args.from_file)
    else:
        xml_text = read_dump_from_device(wait_manual=args.wait_manual)
        if args.raw_out:
            with open(args.raw_out, 'w', encoding='utf-8') as f:
                f.write(xml_text)
            print(f"Сырой дамп сохранён: {args.raw_out}", file=sys.stderr)

    keys = extract_keys(xml_text, pattern=args.pattern)
    result = {
        "keys": keys,
        "count": len(keys),
        "no_keys_found": not keys,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if not keys else 0


if __name__ == '__main__':
    sys.exit(main())
