#!/usr/bin/env python3
"""qa-machine — чего не хватает на этой машине для QA-проекта: коротко при старте сессии и опись для установки.

    qa-machine.py hook-start                  # хук SessionStart: вход — JSON хука в stdin, вывод — в контекст агента
    qa-machine.py survey [--cwd <папка>]      # /qa:setup-machine: полный прогон preflight + опись недостачи, JSON
    qa-machine.py venv <папка> [--python P] [--recreate]   # собрать `.venv` папки и поставить зависимости

Зачем. Проект клонируют на вторую машину (или диск с ним приезжает на другой ноутбук), а что нет `.venv`
автотестов, нет `.env` и оснащение здесь не проверялось, выясняется посреди задачи. Хук говорит это в первые
секунды сессии и отправляет к `/qa:setup-machine`; скилл ставит недостающее по одному, с апрувом человека.

Хук проверяет только файлы, быстро: без сети, без запуска инструментов из таблицы (это работа `preflight.py`,
он гоняет каждую строку и стоит секунды). По каждой папке-роли проекта:
  * автотесты: нет `.venv/bin/python` — «нет `.venv`»; ссылка есть, но ведёт в никуда (venv собран на другой
    машине) — «не запускается на этой машине»;
  * нет `.env`, а таблица оснащения его требует (колонка «Переменные» или строка с путём `.env`) — имена
    переменных, которых нет и в окружении. Значения `.env` хук не читает вовсе: файл есть — про него молчит,
    пустые переменные в нём ловит `preflight.py` и кладёт в маркер;
  * маркер `.preflight-ok`: нет, с другой машины, таблица или проверка сменились — «не проверено». Действительный
    маркер этой машины с недостачей хук не пересказывает (ревью): намеренно отсутствующее печаталось бы каждый
    старт, а устаревшая строка — после того, как человек сам поставил `.venv`/`.env`; это забота скиллов
    (`preflight --use-marker` на входе).
Отдельно — версия плагина (разбор лаборатории 2026-10-02, P-17). Проект приезжает по git, плагин — нет: на
второй машине карта проекта звала скилл, которого в старом плагине не было, и агент молча делал его работу
руками. Хук сравнивает версию `qa` этой машины с версией шаблона проекта (`plugin_version` маркеров и учёта
корня `.qa/root.json`) и с клоном каталога на машине (каталог при старте обновляется, плагин — не всегда);
плагин старее — называет версии и команды обновления для включённых плагинов каталога. Плагин не из кэша
(`--plugin-dir`) с каталогом не сверяется. Версия не читается — молчание.
Говорит только на старте сессии (`source` — `startup` или `clear`), не после `resume`/`compact`: посреди
задачи повтор сбивал бы агента. Агенту — упомянуть человеку одной строкой и предложить `/qa:setup-machine`,
сам скилл не запускать.
Всё на месте — ничего не печатает: вывод `SessionStart` ложится в контекст каждой сессии, и строка «всё в
порядке» — это шум, который учит пропускать блок. Своя ошибка — тоже молчание; код всегда 0.

`survey` — опись для одного сообщения человеку: в каждой папке с таблицей прогоняет `preflight.py --json` (он же
пишет маркер этой машины) и сводит итог в пункты `items`: `venv` (строки таблицы про `.venv/` — внутри него),
`tool` (рецепт — колонка «Как ставить»), `env` (только имена; команды нет — `.env` заполняет человек). Значения
переменных наружу не отдаёт. Коды: 0 — всё на месте, 1 — есть пункты, 2 — не QA-проект.

`venv` — `python -m venv .venv` и `pip install -r requirements.txt` (плюс `requirements-playwright.txt`, если в
маркере `frontend_lib: playwright`). Python ниже минимума таблицы — отказ до сборки. Битый `.venv` пересобирает
только с `--recreate` (старая папка очищается). Коды: 0 — готово, 1 — pip упал, 2 — отказ, причина в stderr.

Таблица оснащения — `docs/toolchain.md` (автотесты) или `project-passport.md` (база знаний), раздел «Оснащение
машины»; разбор и правила маркера — из `preflight.py`, второй копии правил нет.
Где QA-проект: от папки вверх до маркера `.qa/project.yaml` — эта папка-роль и её сосед (`sibling:`); маркера
выше нет — папки-роли среди подпапок (корень проекта).
Тест — `qa-toolkit/tests/test_qa_machine.py`.
"""
import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

MARKER = Path(".qa") / "project.yaml"
SOURCES = (Path("docs") / "toolchain.md", Path("project-passport.md"))
PREFLIGHT_MARKER = ".preflight-ok"
PREFLIGHT = Path(__file__).resolve().parent / "preflight.py"
VENV_PYTHON = Path(".venv") / "bin" / "python"
NAME_IN_TICKS = re.compile(r"`([A-Z_][A-Z0-9_]*)`")
PLUGIN_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JSON = Path(".claude-plugin") / "plugin.json"
ROOT_RECORD = Path(".qa") / "root.json"
SETTINGS = Path(".claude") / "settings.json"
DEFAULT_CATALOG = "qa-toolkit"


def read_marker(path):
    """Маркер проекта; модуль рядом в bin/ — импорт здесь, чтобы его отсутствие ловил `try` хука (ревью)."""
    from qa_template import read_marker as read  # noqa: PLC0415
    return read(path)


def preflight():
    """Разбор таблицы и правила маркера — те же, что у `preflight.py`: второй копии правил не заводим."""
    import preflight as pf  # рядом в bin/; импорт здесь — вне QA-проекта не платим за него
    return pf


def role_folders(cwd):
    """Папки-роли проекта, видные из `cwd`: [(папка, маркер)]. Пусто — не QA-проект."""
    cwd = Path(cwd)
    own = next((d for d in [cwd, *cwd.parents] if (d / MARKER).is_file()), None)
    if own is not None:
        found = [(own, read_marker(own / MARKER))]
        sibling = found[0][1].get("sibling", "none")
        if sibling != "none":
            other = (own / sibling).resolve()
            if (other / MARKER).is_file() and other != own:
                found.append((other, read_marker(other / MARKER)))
        return found
    found = []
    for c in sorted(cwd.iterdir()):
        if c.is_dir() and (c / MARKER).is_file():
            try:  # битый маркер одной папки не прячет соседнюю (ревью)
                found.append((c, read_marker(c / MARKER)))
            except Exception:  # noqa: BLE001
                continue
    return found


def equipment(folder, pf):
    """(строки, сырой текст таблицы, источник) первого файла с заполненным разделом; ([], "", None) — нет."""
    for source in SOURCES:
        path = folder / source
        if path.is_file():
            rows, raw = pf.parse_equipment_section(path.read_text(encoding="utf-8"))
            if rows:
                return rows, raw, source
    return [], "", None


def mentions(row, prefix):
    """Строка таблицы проверяет что-то внутри `prefix` (`.venv/`) или сам файл (`.env`)."""
    cells = (row.get("как проверить", ""), row.get("путь", ""))
    return any(c == prefix.rstrip("/") or c.startswith(prefix) for c in cells)


def venv_state(folder, marker, rows):
    """None — `.venv` не нужен или на месте; "missing" — нет; "broken" — python по ссылке не найден."""
    if marker.get("role") != "autotests" and not any(mentions(r, ".venv/") for r in rows):
        return None
    python = folder / VENV_PYTHON
    if not os.path.lexists(python):
        return "missing"
    return None if python.exists() else "broken"


def missing_env(folder, rows, pf):
    """Нет `.env`, а таблица его требует: (нужен ли, имена, которых нет и в окружении). Файл есть — (False, [])."""
    if (folder / ".env").exists():
        return False, []
    names = list(dict.fromkeys(n for r in rows for n in pf.variable_names(r.get("переменные", "—"))))
    empty = [n for n in names if not os.environ.get(n)]
    wants_file = any(mentions(r, ".env") for r in rows)
    return bool(empty) or (wants_file and not names), empty


def row_without(rows, prefix, default):
    row = next((r for r in rows if mentions(r, prefix)), None)
    return (row or {}).get("без неё") or default


# --- хук -----------------------------------------------------------------------

VENV_LINES = {"missing": "нет `.venv` — ни pytest, ни `make verify`",
              "broken": "`.venv` не запускается на этой машине (собран на другой: его python ведёт в никуда)"}


def folder_findings(folder, marker, pf):
    """Строки недостачи одной папки-роли — без имени папки."""
    rows, raw, _ = equipment(folder, pf)
    lines = []
    venv = venv_state(folder, marker, rows)
    if venv:
        lines.append(VENV_LINES[venv])
    need, names = missing_env(folder, rows, pf)
    if need:
        what = f"нужны {', '.join(names)}" if names else "его требует таблица оснащения"
        example = "; образец — `.env.example`" if (folder / ".env.example").is_file() else ""
        lines.append(f"нет `.env` — {what}{example}, значения заполняет человек")
    if rows:
        lines.extend(marker_findings(folder, raw, pf))
    return lines


def marker_findings(folder, raw, pf):
    try:
        state = json.loads((folder / PREFLIGHT_MARKER).read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            state = None
    except (OSError, ValueError):
        state = None
    reason = pf.marker_verdict(state, raw)
    date = (state or {}).get("checked_at", "?")
    if reason == "маркера нет":
        return ["оснащение на этой машине не проверено"]
    if reason == "другая машина":
        return [f"оснащение проверяли на другой машине ({state.get('host', '?')}), на этой — нет"]
    if reason == "сменилась версия проверки":
        return [f"проверка оснащения от {date} сделана старой версией `preflight` — перепроверить"]
    if reason == "таблица оснащения изменилась":
        return [f"таблица оснащения изменилась после проверки {date} — перепроверить"]
    return []  # действительный маркер этой машины — недостачу в нём скажут скиллы на входе (см. докстринг)


def load_json(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def version_key(version):
    from qa_template import version_key as key  # noqa: PLC0415 — рядом в bin/, как `read_marker`
    return key(version) if isinstance(version, str) else (0,)


def installed_from():
    """(каталог, папка плагинов Claude), если плагин стоит из кэша `<plugins>/cache/<каталог>/qa/<версия>`."""
    parents = PLUGIN_ROOT.parents
    if len(parents) > 3 and parents[2].name == "cache":
        return parents[1].name, parents[2].parent
    return None, None


def catalog_version(plugins, catalog, name):
    """Версия плагина в клоне каталога на этой машине или None."""
    clone = plugins / "marketplaces" / catalog
    for entry in load_json(clone / ".claude-plugin" / "marketplace.json").get("plugins") or []:
        if isinstance(entry, dict) and entry.get("name") == name and isinstance(entry.get("source"), str):
            return load_json(clone / entry["source"] / PLUGIN_JSON).get("version")
    return None


def version_findings(cwd, folders):
    """Строки «плагин старее проекта или каталога» или []."""
    own = load_json(PLUGIN_ROOT / PLUGIN_JSON)
    name, here = own.get("name"), own.get("version")
    if not isinstance(name, str) or not isinstance(here, str):
        return []
    roots = list(dict.fromkeys([Path(cwd), *(folder.parent for folder, _ in folders)]))
    project = [marker.get("plugin_version") for _, marker in folders]
    project += [load_json(root / ROOT_RECORD).get("plugin_version") for root in roots]
    catalog, plugins = installed_from()
    newer = {"проект уже на": max(project, key=version_key, default=None),
             "в каталоге на этой машине уже": catalog_version(plugins, catalog, name) if catalog else None}
    newer = {words: v for words, v in newer.items() if version_key(v) > version_key(here)}
    if not newer:
        return []
    enabled = {}
    for root in roots:
        enabled.update(load_json(root / SETTINGS).get("enabledPlugins") or {})
    if not catalog:
        catalog = next((key.split("@", 1)[1] for key in enabled if key.startswith(name + "@")), DEFAULT_CATALOG)
    ours = sorted(key for key, on in enabled.items() if on and key.endswith("@" + catalog)) or [f"{name}@{catalog}"]
    return [
        f"- `{name}` здесь — {here}, " + ", ".join(f"{words} {v}" for words, v in newer.items())
        + ": скиллов и команд, которые называет карта проекта, здесь может не быть",
        f"- обновить из корня проекта: `claude plugin marketplace update {catalog}`, затем "
        + ", ".join(f"`claude plugin update {key} --scope project`" for key in ours)
        + "; новая версия заработает со следующей сессии",
    ]


def report(cwd):
    """Текст для контекста агента или "" — всё на месте либо не QA-проект."""
    folders = role_folders(cwd)
    if not folders:
        return ""
    try:  # версия не читается — молчание, оснащение скажем всё равно
        stale = version_findings(cwd, folders)
    except Exception:  # noqa: BLE001
        stale = []
    head = []
    if stale:
        head = ["QA: плагин на этой машине устарел.", *stale,
                "Скажи это человеку первой строкой ответа. Если скилла или команды из карты проекта здесь нет — "
                "не делай его работу руками: назови обновление и спроси, обновить ли сейчас."]
    pf = preflight()
    lines = []
    for folder, marker in folders:
        try:  # одна битая папка не глушит другую (ревью)
            lines += [f"- {folder.name}: {line}" for line in folder_findings(folder, marker, pf)]
        except Exception:  # noqa: BLE001
            continue
    if not lines:
        return "\n".join(head)
    return "\n".join([
        *head,
        "QA: на этой машине проект готов не целиком.",
        *lines,
        "Скажи это человеку первой строкой ответа — одной строкой, с предложением `/qa:setup-machine` (ставит "
        "недостающее по одному, с вопросом на каждое); сам его не запускай и ответа не жди — продолжай задачу "
        "человека.",
    ])


def hook_start():
    try:
        data = json.loads(sys.stdin.read() or "{}")
        cwd = data.get("cwd") if isinstance(data, dict) else None
        if not isinstance(cwd, str) or not Path(cwd).is_dir():
            return
        if data.get("source", "startup") not in ("startup", "clear"):  # resume/compact — посреди задачи
            return
        text = report(cwd)
    except Exception:  # noqa: BLE001 — хук не должен ни падать, ни шуметь в сессии
        return
    if text:
        print(text)


# --- survey --------------------------------------------------------------------

def run_preflight(folder, source):
    """Полный прогон `preflight.py --json` в папке (команды таблицы относительны к ней). Пишет маркер."""
    p = subprocess.run([sys.executable, str(PREFLIGHT), "--json", "--passport", str(source)], cwd=folder,
                       capture_output=True, text=True)
    if p.returncode in (0, 1):
        data = json.loads(p.stdout)
        return {"code": p.returncode, "notes": data.get("источник", [])}, data.get("оснащение", [])
    return {"code": p.returncode, "error": (p.stderr or p.stdout).strip()}, []


def folder_items(folder, marker, pf):
    rows, _, source = equipment(folder, pf)
    entry = {"folder": folder.name, "path": str(folder), "role": marker.get("role"),
             "source": str(source) if source else None, "preflight": None}
    results = []
    if source:
        entry["preflight"], results = run_preflight(folder, source)

    items = []
    venv = venv_state(folder, marker, rows)
    if venv:
        items.append({"kind": "venv", "what": "`.venv`",
                      "why": "нет" if venv == "missing" else "собран на другой машине: его python ведёт в никуда",
                      "without": row_without(rows, ".venv/", "ни pytest, ни `make verify`"),
                      "install": f"qa-machine.py venv {shlex.quote(str(folder))}"
                                 + (" --recreate" if venv == "broken" else "")})

    need_env, env_names = missing_env(folder, rows, pf)
    by_name = {r.get("что"): r for r in rows}
    for r in results:
        env_names += NAME_IN_TICKS.findall(r.get("переменные", ""))  # только имена: значений preflight не отдаёт
        row = by_name.get(r.get("что"), {})
        if r.get("status") in ("есть", "переменные пусты") or mentions(row, ".env"):
            continue
        if venv and mentions(row, ".venv/"):
            continue
        items.append({"kind": "tool", "what": r.get("что"), "status": r.get("status"), "why": r.get("почему", ""),
                      "without": r.get("без неё", ""), "install": r.get("как ставить") or None})
    env_names = list(dict.fromkeys(env_names))
    if need_env or env_names:
        items.append({"kind": "env", "what": "`.env`",
                      "why": "нет файла" if not (folder / ".env").exists() else "переменные пусты",
                      "names": env_names, "example": (folder / ".env.example").is_file(),
                      "without": row_without(rows, ".env", ""), "install": None})
    return entry, [{"folder": folder.name, **i} for i in items]


def survey(cwd):
    folders = role_folders(Path(cwd).resolve())
    if not folders:
        print(f"{cwd}: ни здесь и выше, ни в подпапках нет маркера {MARKER.as_posix()} — это не QA-проект, "
              "его разворачивает /qa:init", file=sys.stderr)
        return 2
    pf = preflight()
    entries, items = [], []
    for folder, marker in folders:
        entry, found = folder_items(folder, marker, pf)
        entries.append(entry)
        items += found
    print(json.dumps({"folders": entries, "items": items}, ensure_ascii=False, indent=1))
    return 1 if items else 0


# --- venv ----------------------------------------------------------------------

def fail(text):
    print(text, file=sys.stderr)
    return 2


def build_venv(folder, python, recreate):
    folder = Path(folder).resolve()
    if not (folder / "requirements.txt").is_file():
        return fail(f"{folder}: нет requirements.txt — ставить в `.venv` нечего")
    venv_python = folder / VENV_PYTHON
    broken = os.path.lexists(venv_python) and not venv_python.exists()
    if recreate and os.path.islink(folder / ".venv"):  # `venv --clear` по симлинку очищает его цель (ревью)
        return fail(f"{folder.name}: `.venv` — симлинк на {os.readlink(folder / '.venv')}; пересборка очистила бы "
                    "ту папку. Убери ссылку сам (или собери общий venv заново там), потом этот вызов без --recreate")
    if recreate and not broken:
        return fail(f"{folder.name}: `.venv` исправен — пересобирать нечего; --recreate только для битого")
    if broken and not recreate:
        return fail(f"{folder.name}: `.venv` битый (собран на другой машине). Пересобрать — тот же вызов с "
                    "--recreate: папка `.venv` очищается и собирается заново")
    pf = preflight()
    rows, _, _ = equipment(folder, pf)
    minimum = next((r.get("минимум", "") for r in rows if r.get("путь") == VENV_PYTHON.as_posix()), "")

    if recreate or not os.path.lexists(venv_python):
        try:
            got = subprocess.run([python, "-c", "import sys; print('%d.%d.%d' % sys.version_info[:3])"],
                                 capture_output=True, text=True, check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError) as e:
            return fail(f"`{python}` не запускается: {e} — укажи другой --python")
        want = pf.version_tuple(minimum) if not pf.blank(minimum) else None
        if want and pf.version_tuple(got) < want:
            return fail(f"`{python}` — Python {got}, таблица оснащения требует ≥ {minimum}: "
                        "укажи другой --python (например, python3.12)")
        p = subprocess.run([python, "-m", "venv", *(["--clear"] if recreate else []), ".venv"], cwd=folder,
                           capture_output=True, text=True)
        if p.returncode:
            return fail(f"`{python} -m venv .venv` упал:\n{(p.stderr or p.stdout).strip()}")

    marker = read_marker(folder / MARKER) if (folder / MARKER).is_file() else {}
    files = ["requirements.txt"]
    if marker.get("frontend_lib") == "playwright" and (folder / "requirements-playwright.txt").is_file():
        files.append("requirements-playwright.txt")
    for name in files:
        p = subprocess.run([str(venv_python), "-m", "pip", "install", "-q", "-r", name], cwd=folder,
                           capture_output=True, text=True)
        if p.returncode:
            tail = "\n".join((p.stderr + p.stdout).strip().splitlines()[-20:])
            print(f"pip install -r {name} упал (код {p.returncode}):\n{tail}")
            return 1
    version = subprocess.run([str(venv_python), "--version"], capture_output=True, text=True).stdout.strip()
    print(f"{folder.name}: `.venv` готов ({version}), поставлено: {', '.join(files)}")
    if "requirements-playwright.txt" in files:
        print("браузер для playwright ставится отдельно и скачивается из сети: "
              "`.venv/bin/playwright install chromium` — отдельным пунктом, с вопросом человеку")
    return 0


def main():
    if sys.argv[1:] == ["hook-start"]:
        hook_start()
        return 0
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("hook-start", help="хук SessionStart: недостачи — в контекст агента")
    p_survey = sub.add_parser("survey", help="полный прогон preflight и опись недостачи, JSON")
    p_survey.add_argument("--cwd", default=".")
    p_venv = sub.add_parser("venv", help="собрать .venv папки и поставить зависимости")
    p_venv.add_argument("folder")
    p_venv.add_argument("--python", default="python3")
    p_venv.add_argument("--recreate", action="store_true", help="битый .venv очистить и собрать заново")
    args = parser.parse_args()
    if args.cmd == "survey":
        return survey(args.cwd)
    return build_venv(args.folder, args.python, args.recreate)


if __name__ == "__main__":
    sys.exit(main())
