"""qa_template.py — отрисовка шаблона под маркер репо: общее у `/qa:init` и `/qa:sync`. Модуль, не команда.

`render(templates, marker)` отдаёт, что шаблон из папки `templates` положил бы в репо с этим маркером:
файлы роли без мусора, только выбранные слои (карта `autotests-layers.json` той же папки), куски общих
файлов с разметкой «слой: <тег>» … «/слой» — вырезаны или без разметки (переводы строк в таком файле — LF,
как у `qa-init.py`), папки вики и коллекции — по `paths:` маркера. `settings.json` отдаётся как в шаблоне: подстановку каталога делает слияние, не отрисовка.

Папка шаблонов — любой версии: текущая (`templates/` рядом), старая из кэша плагина или из истории
каталога — у sync это «база» (`docs/plugin/qa-sync-draft.md`). Совпадение с тем, что выдаёт `qa-init.py
apply`, держит тест `qa-toolkit/tests/test_qa_template.py`; `qa-init.py` на модуль переведён только в
корне (`render_root`, правила корня) — у папок ролей логика там пока своя копия.
"""
import hashlib
import json
import re
from pathlib import Path

BLOCK = re.compile(r"^\s*(?:<!--|#)\s*(/?)слой:?\s*(\w*)\s*(?:-->)?\s*$")
JUNK = {"__pycache__", ".DS_Store", ".pytest_cache"}
PATH_KEYS = {"wiki": "wiki", "collection": "api_collection"}  # как в qa-paths и qa-init.py
RENAMED = {"wiki": "wiki", "api_collection": "collection"}  # папка шаблона kb → ключ `paths:` маркера
LAYER_MAP = "autotests-layers.json"


class TemplateError(Exception):
    pass


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def version_key(version):
    """Версия плагина для сравнения: «0.2.10» новее «0.2.9». Как `version_key` в `qa-init.py`."""
    return tuple(int(x) if x.isdigit() else 0 for x in version.split("."))


def read_marker(path):
    """Маркер `.qa/project.yaml`: ключи верхнего уровня строками, `layers` списком, `paths` словарём."""
    marker, paths, section = {}, {}, None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        top = re.match(r"^(\w+):\s*(.*)$", line)
        if top:
            key, value = top.groups()
            section = key if not value else None
            if value:
                marker[key] = value
            continue
        nested = re.match(r"^\s+(\w+):\s*(.*)$", line)
        if nested and section == "paths":
            paths[nested.group(1)] = nested.group(2)
    layers = marker.get("layers")
    if layers is not None:
        marker["layers"] = [x.strip() for x in layers.strip("[]").split(",") if x.strip()]
    marker["paths"] = paths
    return marker


def active_tags(marker):
    """Теги слоёв, которые остаются в репо; None — роль без слоёв (kb). API — ядро, не слой."""
    if marker["role"] != "autotests":
        return None
    layers = set(marker.get("layers") or []) - {"api"}
    tags = set(layers)
    if "frontend" in layers and marker.get("frontend_lib"):
        tags.add(marker["frontend_lib"])
    if layers:
        tags.add("ui")
    return tags


def load_layer_map(templates):
    data = json.loads((Path(templates) / LAYER_MAP).read_text(encoding="utf-8"))
    return {tag: paths for tag, paths in data.items() if not tag.startswith("_")}


def file_tags(rel, layer_map):
    return {tag for tag, paths in layer_map.items()
            for p in paths if rel == p or (p.endswith("/") and rel.startswith(p))}


def cut_blocks(text, tags, where):
    """Вырезает куски невыбранных слоёв, у выбранных снимает разметку. None — разметки нет."""
    out, keep, marked, open_tag = [], True, False, None
    for n, line in enumerate(text.splitlines(keepends=True), 1):
        m = BLOCK.match(line)
        if not m:
            if keep:
                out.append(line)
            continue
        marked = True
        if m.group(1):
            if open_tag is None:
                raise TemplateError(f"шаблон {where}:{n}: /слой без открытия")
            open_tag, keep = None, True
        else:
            if open_tag is not None:
                raise TemplateError(f"шаблон {where}:{n}: блок внутри блока «{open_tag}»")
            open_tag, keep = m.group(2), m.group(2) in tags
    if open_tag is not None:
        raise TemplateError(f"шаблон {where}: блок «{open_tag}» не закрыт")
    return "".join(out) if marked else None


def project_path(rel, paths):
    """Путь файла шаблона в репо: папки вики и коллекции — как в `paths:` маркера."""
    key = RENAMED.get(rel.parts[0])
    if key is None:
        return rel
    return Path(paths.get(key, PATH_KEYS[key]), *rel.parts[1:])


def render(templates, marker):
    """{путь в репо: байты} — что шаблон из папки `templates` кладёт в репо с этим маркером."""
    src = Path(templates) / marker["role"]
    tags = active_tags(marker)
    layer_map = load_layer_map(templates) if tags is not None else {}
    paths = marker.get("paths") or {}
    out = {}
    for p in sorted(src.rglob("*")):
        rel = p.relative_to(src)
        if JUNK.intersection(rel.parts) or not p.is_file():
            continue
        key = rel.as_posix()
        if tags is not None and not file_tags(key, layer_map) <= tags:
            continue
        data = p.read_bytes()
        if tags is not None:
            try:  # как `qa-init.py`: режет по `read_text` — CRLF и CR там становятся LF; без разметки — байты
                text = data.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
            except UnicodeDecodeError:
                text = None
            cut = cut_blocks(text, tags, key) if text is not None else None
            if cut is not None:
                data = cut.encode("utf-8")
        out[project_path(rel, paths).as_posix()] = data
    return out


LOCAL_NAME = re.compile(r"(?m)(^|`)(" + "|".join(RENAMED) + ")/")


def localize(rendered, marker):
    """Имена папок проекта в ТЕКСТЕ шаблона (решение человека 2026-10-02): `render` кладёт файлы в папки из
    `paths:` маркера, а текст шаблона по-прежнему пишет `wiki/…`, `api_collection/…`. У принятого проекта со
    своими папками из-за этого вся таблица путей считалась правкой человека, а «взять шаблон» писал пути
    несуществующих папок. Заменяем имя в начале пути — после обратной кавычки или в начале строки — в `.md`
    вне самих этих папок: внутри папки вики `wiki/` — её подпапка. Имена по шаблону — ничего не меняется."""
    paths = marker.get("paths") or {}
    names = {folder: paths[key] for folder, key in RENAMED.items() if paths.get(key, folder) != folder}
    if not names:
        return rendered
    out = {}
    for rel, data in rendered.items():
        out[rel] = data
        if not rel.endswith(".md") or Path(rel).parts[0] in names.values():
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        out[rel] = LOCAL_NAME.sub(lambda m: m.group(1) + names.get(m.group(2), m.group(2)) + "/", text).encode("utf-8")
    return out


# --- корень проекта ------------------------------------------------------------------------
# Шаблон корня `templates/root/`: карта `CLAUDE.md`, `.gitignore`, `allow.json` — разрешения корня сверх
# разрешений автотестов (по тегам ролей). Отрисовку зовут `qa-init.py` (кладёт корень) и `qa-sync.py` (база —
# шаблоны старой версии, новый — текущие); у старой версии без `allow.json` своих правил корня нет.

ROOT_FILES = ("CLAUDE.md", ".gitignore")  # что шаблон корня кладёт в корень
ROOT_ALLOW = "allow.json"
ROLES = ("kb", "autotests")
LAYERS = {"frontend", "mobile"}  # API — ядро шаблона, слоем не считается
FRONTEND_ONLY = {"mcp__playwright"}  # разрешение слоя frontend — без фронта в корень и в папку не идёт
LAYER_WORDS = {"frontend": "фронт ({lib})", "mobile": "мобильные (Appium)"}
LIB_NAMES = {"selenium": "Selenium", "playwright": "Playwright"}
PATH_RULE = re.compile(r"(Read|Edit|Write|MultiEdit|NotebookEdit)\((.+)\)")


def root_tags(repos, git_root):
    """Теги разметки шаблона корня: роли, `both` при обеих, слои автотестов (`ui` — при любом), где git."""
    by_role = {r["role"]: r for r in repos}
    layers = set(by_role.get("autotests", {}).get("layers") or [])
    tags = set(by_role) | layers | ({"both"} if set(ROLES) <= set(by_role) else set()) | ({"ui"} if layers else set())
    tags.add("git_root" if git_root else "git_repos")
    return tags


def root_inputs(title, repos, git_root):
    """Из чего рисуется корень: название, папки (роль, слои, библиотека фронта, пути вики и коллекции), где git.
    Пишется в учёт корня: sync рисует базу с ними, а не с сегодняшними папками (ревью 2026-09-30) — иначе
    папка или слой, добавленные после учёта, считались бы «было и в базе»."""
    norm = []
    for r in repos:
        repo = {"role": r["role"], "dir": r["dir"]}
        if r["role"] == "autotests":
            repo["layers"] = sorted(x for x in (r.get("layers") or []) if x in LAYERS)
            if r.get("frontend_lib") and "frontend" in repo["layers"]:
                repo["frontend_lib"] = r["frontend_lib"]
        paths = {k: v for k, v in (r.get("paths") or {}).items() if k in PATH_KEYS}
        if paths:
            repo["paths"] = paths
        norm.append(repo)
    return {"title": title, "repos": sorted(norm, key=lambda r: r["dir"]), "git_root": bool(git_root)}


def render_root(templates, title, repos, git_root):
    """Файлы шаблона корня под эти репо: {имя: текст}. Куски ролей и слоёв, которых в проекте нет, вырезаны
    разметкой «слой: <тег>», как у шаблона автотестов; теги — `root_tags`. `{{…}}` — название, имена папок,
    вики и коллекции (у принятого ручника — свои). repos — [{role, dir, layers?, frontend_lib?, paths?}].
    Файла нет в шаблонах этой версии (корень до 0.2.21) — его нет и в отрисовке."""
    by_role = {r["role"]: r for r in repos}
    kb, auto = by_role.get("kb", {}), by_role.get("autotests", {})
    layers = set(auto.get("layers") or [])
    lib = auto.get("frontend_lib") or ""
    paths = {**PATH_KEYS, **(kb.get("paths") or {})}
    names = {"title": title, "kb": kb.get("dir", ""), "autotests": auto.get("dir", ""),
             "wiki": paths["wiki"], "collection": paths["collection"],
             "layers": ", ".join(["API (pytest)"] + [LAYER_WORDS[x].format(lib=LIB_NAMES.get(lib, lib))
                                                     for x in ("frontend", "mobile") if x in layers])}
    tags = root_tags(repos, git_root)
    out = {}
    for name in ROOT_FILES:
        path = Path(templates) / "root" / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        text = cut_blocks(text, tags, f"root/{name}") or text
        out[name] = re.sub(r"\{\{(\w+)\}\}", lambda m: names[m.group(1)], text)
    return out


def root_rule(rule, folder):
    """Разрешение папки — для settings корня: путь правила — от корня, как у FPS (`Edit(.claude/skills/**)` →
    `Edit(autotests-fps/.claude/skills/**)`). Абсолютный (`//`) и домашний (`~`) путь — как был. Команды Bash
    — как есть: из корня их зовут `cd <папка> && …`."""
    m = PATH_RULE.fullmatch(rule)
    if not m or m.group(2).startswith(("//", "~")):
        return rule
    tool, path = m.groups()
    if path.startswith("/"):
        return f"{tool}(/{folder}{path})"
    return f"{tool}({folder}/{path.removeprefix('./')})"


def root_extra_allow(templates, repos):
    """Правила корня сверх разрешений автотестов — из `root/allow.json` этой версии шаблонов, по тегам ролей
    (`kb`, `autotests`, `both`). Нет файла — старая версия, своих правил у корня не было."""
    path = Path(templates) / "root" / ROOT_ALLOW
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    tags = root_tags(repos, False)
    return [rule for tag, rules in data.items() if not tag.startswith("_") and tag in tags for rule in rules]


def root_template_allow(templates, repos):
    """Разрешения, которые шаблон этой версии даёт корню: автотестов — из settings шаблона роли (без
    `mcp__playwright`, если нет фронта), пути — от корня; плюс `root_extra_allow`. Правила, которые человек
    дописал в settings папки, сюда не входят — это не шаблон."""
    rules = []
    for repo in repos:
        if repo["role"] != "autotests":
            continue
        path = Path(templates) / "autotests" / ".claude" / "settings.json"
        allow = json.loads(path.read_text(encoding="utf-8")).get("permissions", {}).get("allow", [])
        skip = set() if "frontend" in (repo.get("layers") or []) else FRONTEND_ONLY
        rules += [root_rule(rule, repo["dir"]) for rule in allow if rule not in skip]
    return rules + [r for r in root_extra_allow(templates, repos) if r not in rules]
