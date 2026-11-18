#!/usr/bin/env python3
"""preflight.py — проверка оснащения машины по разделу «Оснащение машины».

Источник по умолчанию — docs/toolchain.md (до 09.09.2026 раздел жил в паспорте).

Происхождение. Скрипт перенесён из репозитория `ai_manual_test_helper`
(скилл `task-recheck`, `preflight.py`, ветка main, коммит d8e0c16 от 05.09.2026)
и там же обкатан на живых заходах. Дельта под этот репозиторий ровно три пункта: раздел
паспорта адресуется ПО НАЗВАНИЮ, а не по номеру (здешний паспорт не нумерует заголовки),
функция разбора названа по смыслу, у `--passport` есть здешний дефолт (`docs/toolchain.md`). Логика проверок,
классификации и маркера не тронута — правки в оригинале переносятся сюда почти дословно.

Зачем. Проверка «чем располагает машина» была предписана текстом и держалась на дисциплине:
на второй машине проекта паспорт объявлял установленным раннер, которого нет, и называл пути,
которых нет с позапрошлого месяца, — и это не заметил никто. Правило написано, читается в
начале работы и не исполняется. Лечится механикой, а не четвёртым напоминанием. В этом
репозитории тот же класс уже записан руками: `docs/apps-repos.md` держит датированные строки
«fvm есть, yarn нет» — правду об ОДНОЙ машине в файле, который лежит в git.

Что делает:
  * читает таблицу раздела «Оснащение машины» — что проверять, чем, какой минимум версии, что
    закрывается без этого;
  * прогоняет проверки и раскладывает исход на ТРИ класса, а не два (см. classify);
  * проверяет пути ТОЛЬКО из колонки «Путь» — разбирать пути из прозы бесполезно (замерено:
    24 ложных срабатывания на 2 настоящих);
  * по колонке «Переменные» называет пустые переменные окружения/`.env` по ИМЕНИ, значений
    не печатает никогда;
  * сверяет шапку паспорта: дата «Обновлено» против последней правки файла в git, наличие
    строки «Подтверждён человеком»;
  * держит маркер, чтобы обжитая машина не платила за проверку каждый заход.

Чего НЕ делает: ничего не ставит, не чинит и не трогает систему. Печатает диагноз и команды
из колонки «Как ставить» — решает человек.

Границы измерения: проверяется НАЛИЧИЕ и РАБОТОСПОСОБНОСТЬ ЗАПУСКА, но не корректность
поведения. Инструмент, который запускается и врёт, для этого скрипта зелёный.

    preflight.py                  # команда плагина qa, в PATH; запуск из корня проекта
    preflight.py --use-marker     # гейт на входе в скилл
    preflight.py --json
    preflight.py --passport project-passport.md   # ручник: раздел «12. Оснащение машины»

Тесты измерителя: `qa-toolkit/tests/test_preflight.py` и случаи ручника в
`qa-toolkit/tests/task-recheck/run.py` — оба гоняет `qa-toolkit/check.sh`.

Коды возврата: 0 — всё на месте; 1 — есть недостачи; 2 — паспорт не разобран.
"""

import argparse
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys

VERSION = 4  # растёт при смене логики проверок: маркер со старой версией недействителен
# 2 (05.09.2026): переименована колонка рецепта и в причину добавлены слова инструмента —
# строки, донесённые из маркера версии 1, потеряли бы рецепт установки молча.
# 3 (09.09.2026): колонка «Путь» раскрывает переменные окружения и `.env`. Донесённое из
# маркера версии 2 «путь неверен» после этого может быть неверным диагнозом (переменная
# просто не была объявлена) — перепроверяем.
# 4 (29.09.2026): колонка «Переменные». Зелёное «Настройки стенда» версии 3 значило «файл
# `.env` есть» — и про пустой, скопированный из примера; перепроверяем.

# Раздел адресуется по НАЗВАНИЮ: здешний паспорт заголовки не нумерует, а порядок разделов
# в нём меняется от итерации к итерации. Номер принимается тоже — чтобы паспорт,
# принесённый из нумерованного шаблона, читался без правки.
SECTION_RE = re.compile(r"^##\s*(?:\d+\.\s*)?Оснащение машины", re.M)
# Источник таблицы. 09.09.2026 раздел уехал из паспорта в отдельный файл: паспорт скиллы
# читают целиком, а таблицу оснащения не читает НИКТО — её разбирает этот скрипт, и он же
# печатает «без неё»/«ставить». 17.9 КБ машинно-читаемой таблицы ехали в контекст восьми
# скиллов как проза (docs/skills-context-audit.md). Файл несёт СВОЮ шапку «Обновлено»/
# «Подтверждён человеком» — check_passport_header сверяет её с git-историей ЭТОГО файла.
# Дефолт и место таблицы обязаны сходиться: тест test_default_source_actually_holds_the_section.
DEFAULT_SOURCE = "docs/toolchain.md"
UPDATED_RE = re.compile(r"Обновлено:\s*(\d{4}-\d{2}-\d{2})")
CONFIRMED_RE = re.compile(r"Подтверждён человеком:\s*\*{0,2}(\S+)")
VERSION_TOKEN_RE = re.compile(r"(\d+(?:\.\d+)*)")
EMPTY = {"?", "—", "-", "", "–"}


def blank(cell):
    """Незаполненная ячейка. Конвенция шаблона: «Поля со `?` считаются незаполненными», причём
    `?` в нём стоит с подсказкой следом («? одна команда с аргументами»). Сравнение на точное
    равенство эту конвенцию не ловит — проверено контролем на шаблонном паспорте, где скрипт
    выдал ложное «бинаря `?` не найдено» вместо «оснащение не объявлено»."""
    c = (cell or "").strip()
    return c in EMPTY or c.startswith("?")

COLUMNS = ["что", "как проверить", "путь", "минимум", "без неё", "как ставить", "переменные"]
# «Переменные» — необязательная колонка (29.09.2026, разбор лаборатории P-2): `.env` агенту
# закрыт настройками доступа, а скиллы велят убедиться, что он «живой», — агент бился в отказы
# в ~10 сессиях. Прогон отвечает за него: какие из названных переменных пусты, по имени.
# Колонки «Сейчас» в этом наборе нет намеренно: паспорт лежит в git и едет на другие машины,
# а записанная версия — состояние ОДНОЙ машины. На второй она врёт ровно так же, как враньё,
# которое этот скрипт заведён ловить, и вдобавок меняет хеш таблицы всем остальным. Замеренная
# версия печатается прогоном и живёт в маркере, привязанном к хосту.
INSTALL_KEYS = ("как ставить", "как ставили здесь")  # второе — имя колонки до 05.09.2026


def install_hint(row):
    """Рецепт установки. Старое имя колонки читается тоже: паспорт форка мог остаться со
    старой шапкой, и молча потерять единственную подсказку «чем это ставят» — хуже, чем
    прочитать два имени."""
    for key in INSTALL_KEYS:
        if not blank(row.get(key, "?")):
            return row.get(key, "")
    return ""


# --- разбор паспорта ---------------------------------------------------------

def split_row(line):
    """Строка markdown-таблицы → список ячеек без обрамляющих пайпов."""
    line = line.strip()
    if not line.startswith("|"):
        return None
    cells = [c.strip() for c in line.strip("|").split("|")]
    return cells


def is_separator(cells):
    return all(set(c) <= set("-: ") and c for c in cells)


def unwrap(cell):
    """Снимает markdown-обвязку: `код`, **жирный**. Значение, а не оформление."""
    cell = cell.strip()
    cell = re.sub(r"^\*\*(.*)\*\*$", r"\1", cell).strip()
    if cell.startswith("`") and cell.endswith("`") and len(cell) > 1:
        cell = cell[1:-1]
    return cell.strip()


def parse_equipment_section(text):
    """Возвращает (rows, raw_table_text). rows — список dict по COLUMNS.

    Незаполненные строки шаблона (всё «?») пропускаются: шаблон — не оснащение.
    """
    m = SECTION_RE.search(text)
    if not m:
        return None, ""
    tail = text[m.end():]
    # Раздел кончается СЛЕДУЮЩИМ ЗАГОЛОВКОМ, а не первой попавшейся оградой ```: внутри
    # раздела законно стоит блок с примером вызова, и обрыв на его закрывающей ограде съедал
    # всю таблицу ниже — скрипт отвечал «раздел есть, но не заполнен» на заполненном паспорте.
    # Строки, не похожие на строку таблицы, разбор и так пропускает, поэтому ограды безвредны.
    stop = re.search(r"^##\s", tail, re.M)
    body = tail[: stop.start()] if stop else tail

    rows, raw, header = [], [], None
    for line in body.splitlines():
        cells = split_row(line)
        if cells is None:
            continue
        if header is None:
            header = [c.strip().lower() for c in cells]
            raw.append(line.strip())
            continue
        if is_separator(cells):
            raw.append(line.strip())
            continue
        raw.append(line.strip())
        row = {}
        for i, name in enumerate(header):
            row[name] = unwrap(cells[i]) if i < len(cells) else ""
        if all(blank(row.get(c, "?")) for c in ("что", "как проверить", "путь", "переменные")):
            continue  # незаполненная строка шаблона
        rows.append(row)
    return rows, "\n".join(raw)


# --- проверки ----------------------------------------------------------------

def normalize(name):
    """`Node 20+` и `node` — одно и то же имя для сравнения «что» с бинарём."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def classify(subject, command):
    """Три класса исхода, а не два. Замерено:

        bru --version           -> команда не найдена   : инструмента нет
        node --versionx         -> код 9                : команда проверки не та
        python3 -c "import PIL" -> код 1                : инструмент есть, возможности нет

    Различить два последних по коду возврата нельзя — коды произвольны (9, 2, 129, 1).
    Различаются они по СМЫСЛУ строки паспорта: если строка проверяет сам инструмент
    («что» и бинарь — одно и то же), то присутствующий инструмент обязан ответить на своё же
    базовое обращение, и отказ означает неверную команду в паспорте. Если строка проверяет
    возможность ВНУТРИ другого инструмента (Pillow через python3), отказ означает отсутствие
    возможности.
    """
    # shlex, а не split(): путь с пробелом в кавычках наивный split рвёт пополам, и
    # установленный инструмент отчитывается отсутствующим — ложное «нет» хуже пропуска,
    # оно посылает человека ставить то, что уже стоит.
    try:
        argv = shlex.split(command)
    except ValueError as e:
        return "команда не та", f"строка проверки не разбирается: {e}", None
    if not argv:
        return "нет команды", "строка паспорта не несёт проверки", None
    binary = argv[0]
    if shutil.which(binary) is None:
        return "нет", f"бинарь `{binary}` не найден", None
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError) as e:
        return "нет", f"`{binary}` не запустился: {e}", None
    out = (p.stdout or "") + (p.returncode and (p.stderr or "") or "")
    if p.returncode == 0:
        return "есть", "", (p.stdout or p.stderr or "").strip().splitlines()[:1]
    if normalize(subject) and normalize(subject) == normalize(binary):
        return ("команда не та",
                f"`{binary}` установлен, но проверка вернула {p.returncode} — "
                f"неверна строка паспорта, а не машина", None)
    # Последняя строка вывода — показания самого инструмента. Отличить кривую команду от
    # настоящей нехватки скрипт по конструкции не может (класс «команда не та» опознаётся
    # совпадением «что» с бинарём, а здесь бинарь чужой), поэтому вместо классификации —
    # цитата: `SyntaxError` и `ModuleNotFoundError` человек различает с одного взгляда.
    said = next((l.strip() for l in reversed(((p.stderr or "") + (p.stdout or "")).splitlines())
                 if l.strip()), "")
    return ("возможности нет",
            f"`{binary}` установлен, но {subject} через него недоступен (код {p.returncode})"
            + (f": {said}" if said else ""),
            None)


def version_tuple(s):
    m = VERSION_TOKEN_RE.search(s or "")
    return tuple(int(x) for x in m.group(1).split(".")) if m else None


def check_version(minimum, observed_lines):
    """Минимум — гейт. Замеренная версия печатается прогоном, в паспорте её нет."""
    if blank(minimum) or not observed_lines:
        return None
    want, got = version_tuple(minimum), version_tuple(observed_lines[0])
    if not want or not got:
        return None
    return "ниже минимума" if got < want[: len(got)] and got < want else None


# Колонка «Путь» раскрывает переменные: `$VAR`, `${VAR}` и `${VAR:-запасной путь}`.
# Зачем. Путь до клона чужого репозитория — факт МАШИНЫ, а не проекта: паспорт лежит в git
# и приезжает туда, где каталога с таким именем нет вообще (замерено на второй машине —
# «таких папок нет»). Канон в ячейке лечил одну машину и врал остальным; симлинк лечил её же
# руками. Теперь паспорт объявляет ПЕРЕМЕННУЮ и запасное значение по канону: машина, которая
# следует канону, не объявляет ничего, машина с клоном на внешнем диске объявляет одну строку.
VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}"
                    r"|\$([A-Za-z_][A-Za-z0-9_]*)")
DOTENV_CACHE = {}


def dotenv_values(repo):
    """Машинно-локальные значения из `<repo>/.env` — штатное место таких путей в этом
    репозитории (там уже живут `APK_PATH` и `IOS_APP_PATH`). Файл в `.gitignore`, то есть
    именно «состояние одной машины», которому в паспорте места нет.

    Читается лениво и целиком, но НАРУЖУ отдаются только переменные, названные в колонке
    «Путь» (раскрытым путём), и ИМЕНА пустых из колонки «Переменные»: рядом в том же файле
    лежат пароли стенда и БД, и в диагноз они попасть не должны.
    """
    if repo in DOTENV_CACHE:
        return DOTENV_CACHE[repo]
    values = {}
    try:
        with open(os.path.join(repo, ".env"), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
    except OSError:
        pass
    DOTENV_CACHE[repo] = values
    return values


def expand_vars(path, repo):
    """(раскрытая строка, список незаданных переменных). Живое окружение старше `.env`:
    разовый прогон с клоном из другого места не должен требовать правки файла.

    Пустое значение считается незаданным — `.env.example` приезжает с пустой строкой
    `APPS_ROOT=`, и она обязана означать «беру канон», а не «путь — пустая строка»."""
    missing = []

    def sub(m):
        name = m.group(1) or m.group(3)
        default = m.group(2)
        value = os.environ.get(name) or dotenv_values(repo).get(name)
        if value:
            return value
        if default is not None:
            return default
        missing.append(name)
        return m.group(0)

    return VAR_RE.sub(sub, path), missing


def check_path(path, repo):
    if blank(path):
        return None
    expanded, missing = expand_vars(path, repo)
    if missing:
        names = ", ".join(f"`{n}`" for n in dict.fromkeys(missing))
        return (f"путь нечем проверить: переменная {names} не задана ни в окружении, "
                f"ни в `.env` этого репозитория")
    full = os.path.expanduser(expanded)
    if not os.path.isabs(full):
        full = os.path.join(repo, full)
    if os.path.exists(full):
        return None
    # Раскрытый путь в диагнозе обязателен: `${VAR}/mobile-app` в сообщении посылает искать
    # каталог с таким именем, а смотреть надо туда, куда переменная реально указала.
    shown = path if expanded == path else f"{path} → {full}"
    return f"путь не существует: {shown}"


VAR_NAME_RE = re.compile(r"\b[A-Z_][A-Z0-9_]*\b")


def variable_names(cell):
    """`PLATFORM`, `IOS_UDID` → ['PLATFORM', 'IOS_UDID']. Прочерк и «?» — пусто."""
    return [] if blank(cell) else list(dict.fromkeys(VAR_NAME_RE.findall(cell)))


def check_variables(cell, repo):
    """Какие из названных переменных пусты — ни в окружении, ни в `.env`. Только имена."""
    empty = [n for n in variable_names(cell)
             if not (os.environ.get(n) or dotenv_values(repo).get(n))]
    if not empty:
        return None
    return ("не заданы ни в окружении, ни в `.env`: "
            + ", ".join(f"`{n}`" for n in empty))


def check_passport_header(text, passport, repo):
    """Два сигнала устаревания, которые стоят ноль и которых никто не смотрит."""
    notes = []
    m = CONFIRMED_RE.search(text)
    if not m or blank(m.group(1)):
        notes.append("нет строки «Подтверждён человеком» — границы выставлены агентом себе сам")
    m = UPDATED_RE.search(text)
    if m:
        try:
            r = subprocess.run(
                ["git", "log", "-1", "--format=%ad", "--date=short", "--", passport],
                capture_output=True, text=True, cwd=repo, timeout=20)
            last = r.stdout.strip()
            if last and last > m.group(1):
                notes.append(f"шапка говорит «Обновлено: {m.group(1)}», "
                             f"последняя правка файла — {last}")
        except (OSError, subprocess.SubprocessError):
            pass
    return notes


# --- маркер ------------------------------------------------------------------

def host_id():
    return platform.node() or "unknown-host"


def table_hash(raw):
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def marker_verdict(marker, raw):
    """Зачем маркер отзывает исход В ОБЕ СТОРОНЫ.

    Клон этого репозитория лежит на внешнем диске и ездит между машинами. Маркер,
    привязанный к клону, приносил бы на новую машину кэш «раннер есть» — то есть ломался бы
    ровно на том сценарии, ради которого всё писалось. Поэтому в маркере идентификатор хоста,
    и смена хоста делает недействительными и положительные строки тоже.
    """
    if not marker:
        return "маркера нет"
    if marker.get("host") != host_id():
        return "другая машина"
    if marker.get("script_version") != VERSION:
        return "сменилась версия проверки"
    if marker.get("table_hash") != table_hash(raw):
        return "таблица оснащения изменилась"
    if any(r.get("status") != "есть" for r in marker.get("rows", [])):
        return "перепроверка недостающего"
    return None


# --- прогон ------------------------------------------------------------------

def run(rows, repo, only=None):
    out = []
    for row in rows:
        subject = row.get("что", "?")
        if only and subject not in only:
            continue
        command = row.get("как проверить", "?")
        res = {"что": subject, "без неё": row.get("без неё", ""),
               "как ставить": install_hint(row)}
        bad_path_early = check_path(row.get("путь", "—"), repo)
        declared = variable_names(row.get("переменные", "—"))
        if blank(command):
            # Строка может нести только путь — тогда путь и есть её проверка.
            if not blank(row.get("путь", "—")):
                res["status"] = "путь неверен" if bad_path_early else "есть"
                res["почему"] = bad_path_early or ""
            elif declared:  # или только переменные — тогда проверка они
                res["status"], res["почему"] = "есть", ""
            else:
                res["status"], res["почему"] = "не объявлено", "нет команды проверки"
        else:
            status, why, observed = classify(subject, command)
            res["status"], res["почему"] = status, why
            if status == "есть":
                low = check_version(row.get("минимум", "?"), observed)
                res["версия"] = (observed or [""])[0]
                if low:
                    res["status"] = low
                    res["почему"] = f"нужно ≥ {row.get('минимум')}, стоит {res['версия']}"
        if bad_path_early:
            res["путь"] = bad_path_early
            if res["status"] == "есть":
                res["status"] = "путь неверен"
                res["почему"] = bad_path_early
        bad_vars = check_variables(row.get("переменные", "—"), repo)
        if bad_vars:
            res["переменные"] = bad_vars
            if res["status"] == "есть":
                res["status"] = "переменные пусты"
                res["почему"] = bad_vars
        out.append(res)
    return out


def main():
    ap = argparse.ArgumentParser(description="проверка оснащения машины по разделу «Оснащение машины» паспорта")
    ap.add_argument("--passport", default=DEFAULT_SOURCE,
                    help=f"файл с разделом «Оснащение машины» (по умолчанию {DEFAULT_SOURCE})")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--marker", default=None, help="по умолчанию <repo>/.preflight-ok")
    ap.add_argument("--use-marker", action="store_true",
                    help="режим фазы 0: молчать, пока маркер действителен")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    repo = os.path.abspath(a.repo)
    marker_path = a.marker or os.path.join(repo, ".preflight-ok")
    try:
        text = open(a.passport, encoding="utf-8").read()
    except OSError as e:
        print(f"источник оснащения не прочитан: {e}", file=sys.stderr)
        return 2

    rows, raw = parse_equipment_section(text)
    if rows is None:
        print(f"в {a.passport} нет раздела «Оснащение машины» — проверять нечего.\n"
              "Это не стоп: оснащение определяется по ходу вручную, и строка об этом идёт "
              "в отчёт вместе с объявленным объёмом.", file=sys.stderr)
        return 2
    if not rows:
        print("раздел «Оснащение машины» есть, но не заполнен — оснащение не объявлено.",
              file=sys.stderr)
        return 2

    marker = None
    if os.path.exists(marker_path):
        try:
            marker = json.load(open(marker_path, encoding="utf-8"))
        except (OSError, ValueError):
            marker = None

    only = None
    if a.use_marker:
        reason = marker_verdict(marker, raw)
        if reason is None:
            msg = f"оснащение проверено {marker.get('checked_at', '?')}, изменений нет"
            print(json.dumps({"skipped": True, "почему": msg}, ensure_ascii=False)
                  if a.json else msg)
            return 0
        if reason == "перепроверка недостающего":
            only = {r["что"] for r in marker.get("rows", []) if r.get("status") != "есть"}

    results = run(rows, repo, only)
    if only and marker:  # добираем несмотренное из маркера, чтобы картина была целой
        seen = {r["что"] for r in results}
        results += [r for r in marker.get("rows", []) if r["что"] not in seen]

    notes = check_passport_header(text, a.passport, repo)
    missing = [r for r in results if r["status"] != "есть"]

    json.dump({"host": host_id(), "script_version": VERSION, "table_hash": table_hash(raw),
               "checked_at": __import__("datetime").date.today().isoformat(),
               "rows": results}, open(marker_path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    payload = {"оснащение": results, "источник": notes,
               "граница": "проверено наличие и работоспособность запуска, не корректность поведения"}
    if a.json:
        print(json.dumps(payload, ensure_ascii=False, indent=1))
    else:
        for r in results:
            mark = "ok " if r["status"] == "есть" else "НЕТ"
            # Замеренная версия печатается здесь и только здесь: в паспорте её нет (см. COLUMNS).
            print(f"{mark} {r['что']}: {r['status']}"
                  + (f" — {r['почему']}" if r.get("почему") else "")
                  + (f" — {r['версия']}" if r["status"] == "есть" and r.get("версия") else ""))
            if r["status"] != "есть":
                if r.get("без неё"):
                    print(f"      без неё: {r['без неё']}")
                if not blank(r.get("как ставить")):
                    print(f"      ставить: {r['как ставить']}")
        for n in notes:
            print(f"ИСТОЧНИК {n}")
        print("\nпроверено наличие и работоспособность запуска, не корректность поведения.")
        if missing:
            print("устанавливает человек — сам ничего не ставлю.")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
