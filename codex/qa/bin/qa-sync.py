#!/usr/bin/env python3
"""qa-sync.py — механика `/qa:sync`: довести скопированное из шаблона до новой версии плагина.

Поведение и решения человека — `docs/plugin/qa-sync-draft.md` ветки `plugin-sync`. Здесь только то, что
проверяется тестом (`qa-toolkit/tests/test_qa_sync.py`); показать diff, спросить и закоммитить — у скилла.

    qa-sync.py plan <репо>     # опись → JSON: группы файлов, склейки, settings, report_lines; ничего не пишет
    qa-sync.py diff <репо> <файл>
                               # что показать по файлу перед вопросом, по группе: правка шаблона (старая →
                               #   новая версия), у склейки ещё и «ваш файл станет таким»; у молчаливого, нового,
                               #   удалённого — сейчас → шаблон; у убранного — что удалится или что остаётся
    qa-sync.py diff <репо> <файл> --text <собранный файл>
                               # файл, собранный с человеком: каким станет
    qa-sync.py draft <репо> <файл> <файл вне проекта>
                               # основа «собрать вместе»: файл человека с тем, что из правки шаблона встало само;
                               #   `left` — куски, которые не встали (их ставят на место с человеком → `text`)
    qa-sync.py apply <репо> [решения.json]
                               # по свежей описи: нетронутое → новый шаблон, settings — новые разрешения и
                               #   плагины; манифест (отпечатки, версия; убранное шаблоном — вон) и версия в
                               #   маркере. Правленое, новое, убранное, удалённое — только по решениям.
                               #   Нет ответа — не отказ (решение человека 2026-09-28): склейка (merge,
                               #   own_changed) и убранное (removed) без решения — файл как был, в манифесте
                               #   у него `base` (версия шаблона, с которой спросили), следующий sync спросит
                               #   снова; отказ — только `keep`. Удалённое без ответа — тоже спросим снова.
                               #   Новое в шаблоне без ответа — сказано один раз (вопрос 7 PLAN.md, открыт).
                               #   Коммит — у скилла; байты те же — не пишем, нечего коммитить — git_add null
    qa-sync.py plan-root <корень>
    qa-sync.py diff-root <корень> [--text <карта>]
    qa-sync.py draft-root <корень> <файл вне проекта>
                               # основа «собрать вместе»: карта шаблона целиком (unknown; own_lines — строки
                               #   человека не из шаблона) или, при конфликте склейки (merge), карта человека с
                               #   тем, что встало само, и `left` — куски правки шаблона, которые не встали
    qa-sync.py apply-root <корень> [решения.json]
                               # корень проекта — отдельно от папок (карта зависит от обеих): разрешения
                               #   корня по шаблону, карта CLAUDE.md, .gitignore, учёт `.qa/root.json`.
                               #   `--text` — карта, собранная с человеком: какой станет. Ниже, «Корень проекта»

Решения (`apply`), JSON — любые ключи из этих, файл только из своей группы свежей описи, иначе ничего не пишется:
    {"merge": {"<файл>": "merge" | "template"},        # merge — склейка; с конфликтом — перенос правки шаблона в
                                                      #   файл человека (`carry` описи), если встаёт вся (left 0)
     "own_changed": {"<файл>": "merge" | "template"},  # своё: склеенное или взятое из шаблона — всё равно своё
     "add": ["<файл>"],        # new — из шаблона, issued; new_occupied — файл как есть, own
     "delete": ["<файл>"],     # removed
     "keep": ["<файл>"],       # merge, own_changed, removed: оставить как есть — ответ, больше не спрашиваем
     "text": {"<файл>": "<собранный файл>"},           # merge, own_changed: собрано с человеком (основа — `draft`)
     "restore": ["<файл>"], "decline": ["<файл>"],    # deleted: вернуть из шаблона / declined — дальше молчим
     "drop_allow": ["<разрешение>"],                  # шаблон убрал — убрать
     "offer_allow": ["<разрешение>"], "offer_plugins": ["<плагин>"],
     "offer_market": ["<поле каталога>"],             # без базы — добавить
     "keep_allow": ["<разрешение>"], "no_offer": ["<разрешение, плагин, поле>"]}
                                                      # ответы «оставить» / «не добавлять»; нет ответа по
                                                      #   settings — в `pending` манифеста, спросим снова

Каждый файл сравнивается в четырёх видах: «проект» (сейчас), «выдано» (отпечаток в манифесте), «база»
(шаблон версии из манифеста; у файла, ждущего ответа, — версии из его `base`) и «новый» (шаблон этого плагина) — оба отрисованы `qa_template.render` под
маркер репо, в тексте — имена папок проекта из `paths:` маркера (`qa_template.localize`, решение человека
2026-10-02): иначе у принятого проекта со своими папками вся таблица путей — «правка человека». Группы:
    same            проект = новый
    update          нетронуто (проект = выдано), шаблон поменял — обновить молча
    edited          правлено человеком, шаблон файл не менял — не трогаем
    merge           правлено человеком и шаблоном — склейка; число конфликтов — в `merge` (и для own_changed);
                    с конфликтом — `carry`: {moved, same, left} — сколько кусков правки шаблона встаёт в файл
                    человека само, сколько у него уже есть, сколько не встаёт (решение человека 2026-10-02:
                    основа — файл человека, шаблон только добавляет); `loss` — сколько своих строк пропадёт
                    при «заменить шаблоном»
    binary          как merge или own_changed, но файл двоичный — склеить нельзя, только сказать
    skill_text      текст скилла (`filled`, не повторяется из базы), шаблон поменял — только сказать
    same_template   текст скилла, шаблон не менял
    own             свой файл принятого репо, шаблон его не менял
    own_changed     свой файл, шаблон поменял — показать правку шаблона, предложить склейку
    unknown         базы нет, а файл правлен или `filled` — поменял ли его шаблон, не узнать
    new             новый файл шаблона (в базе его не было) — предложить добавить
    new_occupied    новый файл шаблона, на его месте свой — показать разницу
    removed         убран из шаблона, в проекте нетронут (`issued` или вырезка слоёв, повторённая из базы) —
                    предложить удалить
    removed_edited  убран из шаблона, в проекте правлен, свой или текст скилла (`filled`, не повторяется из
                    базы; без базы — любой `filled`) — сказать, из манифеста убрать
    outside         не про этот репо — молчим: в манифесте есть, а шаблон под слои репо его не выдаёт ни в
                    базе, ни сейчас; или был в базе, но репо его не взял (в манифесте нет)
    deleted         удалён человеком — один раз спросить «вернуть?»
    declined        человек отказался возвращать — молчим
    unsafe          путь абсолютный, с `..`, через симлинк или за пределы репо — не трогаю: не читаю, не пишу,
                    не удаляю, решения по нему apply отвергает, запись в манифесте — как была
`settings.json` — отдельно: `add_allow`, `add_plugins`, `add_market` (поля записи каталога, кроме `source`)
— новое в шаблоне относительно базы — молча; убранное человеком, что было и в базе, не возвращаем;
`drop_allow` (шаблон убрал — спросить); `offer_allow`, `offer_plugins`, `offer_market` (базы нет: в шаблоне
есть, у человека нет — спросить).

`settings.json` корня (папка над репо; там каталог и плагины корня, их пишет `qa-init.py apply`) —
`root` в описи: тем же правилом, но только плагины и поля каталога из settings шаблона роли этого репо;
решения — `{"root": {"offer_plugins": [...], "offer_market": [...]}}`. Корнем считается папка над репо с
settings, где есть наш каталог, и не домашняя папка; иначе `root` — null. Пишем только молчаливое новое и
принятое (корень без git откатить нечем; один git в корне — едет коммитом sync, см. `git_add`); settings корня — симлинк — не трогаем, строка в отчёте.

База ищется так: версия та же, что у плагина, — его же шаблоны; иначе кэш плагина
`~/.claude/plugins/cache/<каталог>/qa/<версия>/templates`, если он повторяет всё выданное (`issued`) в
манифесте; иначе лучший по числу совпадений из кэша и клона каталога `~/.claude/plugins/marketplaces/<каталог>`
(коммиты этой версии; битый коммит пропускается); ни одного совпадения — «без базы» (нетронутое обновляется как
обычно, остальное — `unknown`). Клон sync не докачивает.

Корень проекта (решение человека 2026-09-30) — `plan-root` / `apply-root`. Учёт — `.qa/root.json` (пишет
`qa-init.py`): версия шаблона корня и отпечаток карты, отрисованной из шаблона. Разрешения корня — что шаблон
даёт корню (`qa_template.root_template_allow`: автотесты с путями от корня и `templates/root/allow.json`):
новое относительно базы — молча, убранное шаблоном — спросить (`drop_allow`), своё человека не трогаем; учёта
нет (корень собран до шаблона, FPS и Shooting) — шаблон корню раньше ничего не давал: недостающее молча;
учёт есть, а его версии шаблонов нет — спросить (`offer_allow`). Карта — как файл шаблона, группа в `map`:
`same`, `update` (молча), `edited`, `merge` (склейка, число конфликтов), `unknown` (учёта нет — чьи правки, не
узнать), `new` (карты нет, учёта нет — молча), `deleted`, `declined`. В учёт после ответа — отпечаток шаблонной
карты этой версии: файл от неё отличается — правка человека, следующая правка шаблона склеивается поверх
(решение человека 2026-09-30). Без ответа — как была, спросим снова. `.gitignore` — недостающие строки шаблона
дописываются молча (`gitignore`), как у init. Решения — `{"drop_allow": [...], "offer_allow": [...],
"map": "merge" | "template" | "keep" | "restore" | "decline", "map_text": "<файл карты, собранной с человеком>"}`. Корень в своём git — файлы корня чисты и индекс пуст, иначе стоп; `git_add` —
записанное, нечего — null. Корень не git — пишем, `git_add` — null (`git` в выводе — false). Плагины и каталог корня ведёт `apply` папок (`root`).

Выжимки лаборатории (`.qa/labs/sessions/`, пишет хук после каждой сессии) sync не замечает: грязь в них — не стоп,
в коммит sync они не идут — вывод `apply` отдаёт готовую команду `git_add` без них.

Коды возврата: 0 — готово; 2 — стоп (схема маркера не та — нужен `/qa:migrate`; грязный git (кроме выжимок) или репо не корень своего git; нет маркера; маркер, манифест
или settings.json — симлинк или за пределами репо;
проект на шаблоне новее плагина — обновить плагин; `apply`: нет прав на запись хоть одной цели — до первой
записи; запись упала посреди — записанное откачено).
"""
import argparse
import difflib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qa_template  # noqa: E402

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = PLUGIN_ROOT / "templates"
SCHEMA = 1
MARKER = Path(".qa") / "project.yaml"
MANIFEST = Path(".qa") / "manifest.json"
SETTINGS = ".claude/settings.json"
LAB_SESSIONS = ".qa/labs/sessions"  # выжимки сессий пишет хук после каждой сессии — едут обычным коммитом, не sync
GIT_ADD = ["git", "add", "-A", "--", ".", f":(exclude){LAB_SESSIONS}"]
FRONTEND_ONLY = {"mcp__playwright"}  # разрешение слоя frontend — как у qa-init.py


CONFLICT_MARK = re.compile(r"^(<{7}|>{7}) ", re.M)


class Stop(Exception):
    pass


def dump_json(data):
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"  # как у qa-init.py


def plugin_version():
    return json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]


def catalog_name():
    data = json.loads((TEMPLATES / "kb" / SETTINGS).read_text(encoding="utf-8"))
    (name,) = data["extraKnownMarketplaces"]
    return name


def issued_of(files, version=None):
    """Выданное из шаблона: {файл: отпечаток} — по нему узнаём, какая сборка шаблонов была базой. version=None
    — для версии манифеста (файлы, ждущие ответа, со своей `base`, не в счёт); иначе — ждущие этой версии."""
    return {rel: e["sha256"] for rel, e in files.items() if e["state"] == "issued" and e.get("base") == version}


def match_score(templates, render, issued):
    """Сколько выданных файлов шаблоны из папки повторяют байт в байт; None — шаблоны битые (нет карты слоёв,
    кривая разметка, нет папки роли) — такую сборку базой не берём. render(папка) → {файл: байты}: папка роли
    под маркер или корень под его папки."""
    try:
        rendered = render(templates)
    except (qa_template.TemplateError, OSError, ValueError):
        return None
    return sum(1 for rel, sha in issued.items() if rel in rendered and qa_template.sha256(rendered[rel]) == sha)


def find_base(version, issued, render, tmp):
    """Папка шаблонов версии из манифеста: (папка, откуда, коммит). Откуда — current | cache | clone | none.
    Кэш и клон сверяются с выданным в манифесте одним счётом: кэш сошёлся весь — он; нет — лучший из кэша и
    клона; ни один выданный файл не сошёлся (при непустом выданном) — это не та база, без базы."""
    if version == plugin_version():
        return TEMPLATES, "current", None
    cached = Path.home() / ".claude" / "plugins" / "cache" / catalog_name() / "qa" / version / "templates"
    cache_score = match_score(cached, render, issued) if cached.is_dir() else None
    if cache_score is not None and cache_score == len(issued):
        return cached, "cache", None
    clone_score, templates, commit = from_clone(version, render, issued, tmp)
    if clone_score is not None and (cache_score is None or clone_score > cache_score):
        if clone_score or not issued:
            return templates, "clone", commit
    elif cache_score is not None and (cache_score or not issued):
        return cached, "cache", None
    return None, "none", None


def from_clone(version, render, issued, tmp):
    """Шаблоны версии из клона каталога: (счёт, папка, коммит). Под одной версией бывает несколько коммитов
    (починки после выпуска до следующего) — берём тот, чьи шаблоны сходятся с выданным (`issued`); поровну —
    новее; битый коммит пропускаем. Клон неглубокий: коммитов версии может не оказаться — (None, None, None)."""
    clone = Path.home() / ".claude" / "plugins" / "marketplaces" / catalog_name()
    try:
        market = json.loads((clone / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        (source,) = [p["source"] for p in market["plugins"] if p["name"] == "qa"]
    except (OSError, ValueError, KeyError):
        return None, None, None
    plugin = source.removeprefix("./").rstrip("/")

    def git(*args):
        return subprocess.run(["git", *args], cwd=clone, capture_output=True)

    log = git("log", "--format=%H", "--", f"{plugin}/.claude-plugin/plugin.json", f"{plugin}/templates")
    best = (None, None, None)
    for commit in log.stdout.decode().split():
        meta = git("show", f"{commit}:{plugin}/.claude-plugin/plugin.json")
        try:
            if json.loads(meta.stdout)["version"] != version:
                continue
        except (ValueError, KeyError, TypeError):
            continue
        dest = Path(tmp) / commit
        dest.mkdir(exist_ok=True)
        archive = git("archive", commit, f"{plugin}/templates")
        if archive.returncode != 0:
            continue  # в коммите нет шаблонов
        if subprocess.run(["tar", "-x", "-C", str(dest)], input=archive.stdout, capture_output=True).returncode:
            continue
        templates = dest / plugin / "templates"
        score = match_score(templates, render, issued)
        if score is not None and (best[0] is None or score > best[0]):  # лог — от новых к старым: поровну — новее
            best = (score, templates, commit)
    return best


def binary(data):
    """Двоичный — как считает git: нулевой байт в первых 8000 байтах."""
    return data is not None and b"\0" in data[:8000]


def merge_file(base, ours, theirs):
    """Трёхсторонняя склейка `git merge-file`: (число конфликтов, склеенные байты); файлы не пишутся."""
    with tempfile.TemporaryDirectory() as tmp:
        paths = []
        for name, data in (("ours", ours), ("base", base), ("theirs", theirs)):
            path = Path(tmp) / name
            path.write_bytes(data)
            paths.append(str(path))
        labels = ["-L", "сейчас", "-L", "база", "-L", "шаблон"]  # в маркерах конфликта — не пути временных файлов
        res = subprocess.run(["git", "merge-file", "-p", *labels, *paths], capture_output=True)
    if res.returncode < 0 or res.returncode > 127:
        raise Stop(f"git merge-file упал: {res.stderr.decode(errors='replace')}")
    return res.returncode, res.stdout


def text_lines(data):
    """Строки текста без концов строк; None — не текст для переноса: двоичный, не UTF-8 или с CR (перенос
    собирает файл заново, концы строк CRLF он бы переписал)."""
    if data is None or binary(data) or b"\r" in data:
        return None
    try:
        return data.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return None


ANCHOR_REACH = 5  # сколько строк от места правки ищем якорь


def carry(base, ours, new):
    """Перенос правки шаблона (база → новый) в файл человека, когда `git merge-file` дал конфликт (решение
    человека 2026-10-02: основа — файл человека, шаблон только добавляет). Каждый кусок правки — отдельно:
    вставка встаёт по якорю — ближайшей строке базы, которая и в базе, и у человека одна, если между ней и
    местом вставки у человека то же, что в базе; замена и удаление — только если строки базы стоят у человека
    целым куском и один раз, и в базе этот кусок один. Что человек уже внёс сам — не трогаем (`same`). Остальное — `left`: решать
    человеку. → {data, moved, same, left: [{old, new}], added, removed, total} или None — не текст."""
    b, o, n = text_lines(base), text_lines(ours), text_lines(new)
    if b is None or o is None or n is None:
        return None
    have = set(o)

    def once(line):
        return b.count(line) == 1 and o.count(line) == 1

    def place(at):
        for k in range(at - 1, max(-1, at - 1 - ANCHOR_REACH), -1):  # якорь выше места вставки
            if once(b[k]):
                pos, gap = o.index(b[k]), b[k + 1:at]
                if o[pos + 1:pos + 1 + len(gap)] == gap:
                    return pos + 1 + len(gap)
                break
        for k in range(at, min(len(b), at + ANCHOR_REACH)):  # якорь ниже
            if once(b[k]):
                pos, gap = o.index(b[k]), b[at:k]
                if pos >= len(gap) and o[pos - len(gap):pos] == gap:
                    return pos - len(gap)
                break
        return None

    ops, left, same = [], [], 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, b, n, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        old, add = b[i1:i2], n[j1:j2]
        said = [line for line in add if line.strip()]
        already = all(line in have for line in said)
        if tag == "insert":
            pos = None if said and already else place(i1)
            if said and already:
                same += 1
            elif pos is None:
                left.append({"old": old, "new": add})
            else:
                ops.append((pos, 0, add, old))
            continue
        hits = [k for k in range(len(o) - len(old) + 1) if o[k:k + len(old)] == old]
        twins = sum(1 for k in range(len(b) - len(old) + 1) if b[k:k + len(old)] == old)
        if len(hits) == 1 and twins == 1:  # в базе кусок один: иначе у человека нашлось бы не то место (`---`)
            ops.append((hits[0], len(old), add, old))
        elif not hits and already:  # заменённого или удалённого у человека уже нет, а нового — нечего добавить
            same += 1
        else:
            left.append({"old": old, "new": add})
    done, floor = [], len(o) + 1
    for order, (pos, cut, add, old) in sorted(enumerate(ops), key=lambda x: (x[1][0], x[0]), reverse=True):
        if pos + cut > floor:  # куски наехали друг на друга — не гадаем
            left.append({"old": old, "new": add})
            continue
        floor = pos
        done.append((pos, cut, add))
    total = len(o)
    for pos, cut, add in done:  # снизу вверх: позиции выше не сдвигаются
        o[pos:pos + cut] = add
    data = "\n".join(o).encode("utf-8") + (b"\n" if ours.endswith(b"\n") or not ours else b"")
    return {"data": data if done else ours, "moved": len(done), "same": same, "left": left,
            "added": sum(len(add) for _, _, add in done), "removed": sum(cut for _, cut, _ in done), "total": total}


def loss(project, new):
    """Что пропадёт при «заменить шаблоном»: сколько непустых строк человека нет в новом шаблоне, из скольких."""
    mine, theirs = text_lines(project), text_lines(new)
    if mine is None or theirs is None:
        return None
    known = set(theirs)
    said = [line for line in mine if line.strip()]
    return {"own": sum(1 for line in said if line not in known), "total": len(said)}


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8")) if path and path.is_file() else {}


def market(data):
    """Запись каталога плагинов в settings: `extraKnownMarketplaces.<каталог>`; нет — {}."""
    entry = data.get("extraKnownMarketplaces", {}).get(catalog_name())
    return entry if isinstance(entry, dict) else {}


def settings_delta(project, new, base, known, skip=()):
    """Что settings шаблона добавил или убрал против settings человека. project/new/base — словари, known —
    есть ли старая версия шаблона (base). Молча — только новое в шаблоне относительно старой версии: чего нет у
    человека, но было и в старом шаблоне, он убрал сам — не возвращаем. Без старой версии этого не отличить —
    предлагаем, не молча. Поля каталога — все, кроме `source` (его подставляет init, не трогаем), и только если
    запись каталога у человека есть."""
    def allow(data):
        return data.get("permissions", {}).get("allow", [])

    def plugins(data):
        return list(data.get("enabledPlugins", {}))

    missing_allow = [a for a in allow(new) if a not in set(allow(project)) and a not in skip]
    missing_plugins = [p for p in plugins(new) if p not in plugins(project)]
    has_market = catalog_name() in project.get("extraKnownMarketplaces", {})
    missing_market = [k for k in market(new) if k != "source" and has_market and k not in market(project)]
    return {
        "add_allow": [a for a in missing_allow if known and a not in allow(base)],
        "drop_allow": [a for a in allow(base) if a not in allow(new) and a in allow(project)],
        "add_plugins": [p for p in missing_plugins if known and p not in plugins(base)],
        "offer_allow": [] if known else missing_allow,
        "offer_plugins": [] if known else missing_plugins,
        "add_market": [k for k in missing_market if known and k not in market(base)],
        "offer_market": [] if known else missing_market,
    }


PENDING_KEYS = ("drop_allow", "offer_allow", "offer_plugins", "offer_market")


def with_pending(delta, pending, project, new, skip=()):
    """Вопросы прошлого sync по settings, оставшиеся без ответа, — снова, если ещё к месту (решение человека
    2026-09-30, ревью: нет ответа — не отказ и у разрешений). Без этого убранное шаблоном и предложенное без
    базы после перехода учёта на новую версию больше не спрашивалось бы."""
    allow_p, allow_n = project.get("permissions", {}).get("allow", []), new.get("permissions", {}).get("allow", [])
    plug_p, plug_n = list(project.get("enabledPlugins", {})), list(new.get("enabledPlugins", {}))
    has_market = catalog_name() in project.get("extraKnownMarketplaces", {})
    valid = {
        "drop_allow": lambda x: x in allow_p and x not in allow_n,
        "offer_allow": lambda x: x not in allow_p and x in allow_n and x not in skip,
        "offer_plugins": lambda x: x not in plug_p and x in plug_n,
        "offer_market": lambda x: has_market and x not in market(project) and x in market(new),
    }
    silent = set(delta.get("add_allow", [])) | set(delta.get("add_plugins", [])) | set(delta.get("add_market", []))
    for key, ok in valid.items():
        if key in delta:
            delta[key] = delta[key] + [x for x in pending.get(key, [])
                                       if ok(x) and x not in delta[key] and x not in silent]
    return delta


def next_pending(delta, decisions):
    """Что спросили и не получили ответа — в учёт, спросим снова. Ответ: «убрать» (`drop_allow`) или «оставить»
    (`keep_allow`); «добавить» (`offer_*`) или «не добавлять» (`no_offer`)."""
    answered = set(decisions.get("no_offer", []))
    out = {}
    for key in PENDING_KEYS:
        done = set(decisions.get(key, [])) | (set(decisions.get("keep_allow", [])) if key == "drop_allow" else answered)
        left = [x for x in delta.get(key, []) if x not in done]
        if left:
            out[key] = left
    return out


def repo_settings_delta(repo, marker, base_tpl):
    role = marker["role"]
    tags = qa_template.active_tags(marker)
    skip = FRONTEND_ONLY if tags is not None and "frontend" not in tags else set()
    base = load_json(base_tpl / role / SETTINGS) if base_tpl else {}
    return settings_delta(load_json(repo / SETTINGS), load_json(TEMPLATES / role / SETTINGS), base,
                          base_tpl is not None, skip)


def role_part(data):
    """Что от settings шаблона роли идёт в корень: плагины и запись каталога (так пишет корень `qa-init.py`)."""
    return {"enabledPlugins": data.get("enabledPlugins", {}), "extraKnownMarketplaces": data.get("extraKnownMarketplaces", {})}


def root_settings(repo, marker, base_tpl):
    """settings.json корня — папки над репо, где `qa-init.py` пишет каталог и плагины. Пишем только молчаливое
    новое и принятое человеком (корень без git откатить нечем; один git в корне — едет коммитом sync). None — над репо не QA-корень: нет settings,
    в них нет нашего каталога, или это домашняя папка (там settings пользователя, не проекта)."""
    root = repo.parent
    path = root / SETTINGS
    if root == Path.home().resolve() or not (path.is_file() or path.is_symlink()):
        return None
    if unsafe(root, SETTINGS):
        return {"path": str(path), "skipped": "симлинк или путь за пределы корня — не трогаю"}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    name = catalog_name()
    if not isinstance(data, dict) or not (name in data.get("extraKnownMarketplaces", {}) or any(
            p.endswith(f"@{name}") for p in data.get("enabledPlugins", {}))):
        return None
    role = marker["role"]
    base = role_part(load_json(base_tpl / role / SETTINGS)) if base_tpl else {}
    return {"path": str(path), "settings": settings_delta(data, role_part(load_json(TEMPLATES / role / SETTINGS)),
                                                          base, base_tpl is not None)}


def unsafe(repo, rel):
    """Путь из манифеста или шаблона, куда писать нельзя: абсолютный, с `..`, через симлинк (сам файл или
    папка по пути) или за пределы репо. `repo` — уже `resolve()`: путь без симлинков разрешается в себя."""
    p = Path(rel)
    if p.is_absolute() or ".." in p.parts:
        return True
    return (repo / p).resolve() != repo / p


def classify(rel, entry, project, new, base, has_base):
    """Группа файла. entry — запись манифеста или None; project/new/base — байты или None."""
    if entry is None:
        if has_base and base is not None:
            return "outside"  # был в шаблоне и при выдаче, но репо его не взял (приём: не было в проекте)
        return "new_occupied" if project is not None else "new"
    state = entry["state"]
    if state == "declined":
        return "declined"
    if project is None:
        return "deleted" if new is not None else None  # и там, и там нет — просто убрать из манифеста
    touched = qa_template.sha256(project) != entry["sha256"]
    if new is None and has_base and base is None:
        return "outside"  # не из шаблона под слои репо и не убран (приём пишет `own` без учёта слоёв)
    if new is None and state == "own":
        return "removed_edited" if has_base else "unknown"  # свой файл sync не удаляет
    if new is None:  # удалить предлагаем только то, что повторяется из шаблона: текст скилла — данные проекта
        reproduced = state == "issued" or (
            state == "filled" and has_base and qa_template.sha256(base) == entry["sha256"])
        return "removed" if reproduced and not touched else "removed_edited"
    if project == new:
        return "same"
    if state == "own":
        if not has_base:
            return "unknown"
        return "own_changed" if base != new else "own"
    if state == "filled" and not has_base:
        return "unknown"  # без базы вырезку слоёв от текста скилла не отличить — текст скилла не затираем
    # `filled` бывает двух видов: вырезка слоёв (база повторяет выданное) и текст скилла (не повторяет)
    skill_text = state == "filled" and has_base and (base is None or qa_template.sha256(base) != entry["sha256"])
    if skill_text:
        return "skill_text" if base != new else "same_template"
    if not touched:
        return "update"
    if not has_base:
        return "unknown"
    return "merge" if base != new else "edited"


def settings_lines(settings, where):
    lines, parts = [], []
    for key, text in (("add_allow", "разрешения"), ("add_plugins", "плагины"), ("add_market", "поля каталога")):
        if settings[key]:
            parts.append(f"{text} +{len(settings[key])}")
    if parts:
        lines.append(f"{where} молча: {', '.join(parts)}")
    if settings["drop_allow"]:
        lines.append(f"{where} — шаблон убрал разрешения, убрать?: {', '.join(settings['drop_allow'])}")
    offered = settings["offer_allow"] + settings["offer_plugins"] + [
        f"поле каталога {k}" for k in settings["offer_market"]]
    if offered:
        lines.append(f"{where} — в шаблоне есть, у вас нет; убирали ли вы сами, не узнать — старой версии "
                     f"шаблона нет; добавить?: {', '.join(offered)}")
    return lines


def report_lines(frm, to, source, groups, merges, settings, root=None, carried=None):
    names = {"current": "шаблоны этого плагина", "cache": "кэш плагина", "clone": "история каталога",
             "none": "не найдена"}
    lines = [f"шаблон {frm} → {to}; старая версия шаблона: {names[source]}"]

    def listed(key, text):
        if groups.get(key):
            lines.append(f"{text}: {', '.join(groups[key])}")

    if groups.get("update"):
        lines.append(f"обновлю молча: {len(groups['update'])} (список — по запросу)")
    lines += settings_lines(settings, "settings.json")
    if root and root.get("skipped"):
        lines.append(f"settings.json корня: {root['skipped']}")
    elif root:
        lines += settings_lines(root["settings"], "settings.json корня")
    def how(rel):
        if merges[rel] == 0:
            return "без конфликта"
        left = (carried or {}).get(rel, {}).get("left", merges[rel])
        return "добавка шаблона встаёт в ваш файл сама" if not left else f"не встаёт само: кусков {left} — покажу и спрошу"

    def merged(key, text):
        if groups.get(key):
            lines.append(f"{text}: " + ", ".join(f"{rel} ({how(rel)})" for rel in groups[key]))

    merged("merge", "правили и вы, и шаблон — добавить правку шаблона в ваш файл?")
    listed("skill_text", "в шаблоне поменялось, правьте сами, если нужно")
    listed("binary", "двоичный файл поменяли и вы, и шаблон — склеить нельзя, правьте сами")
    merged("own_changed", "своё, шаблон поменял — показать правку и добавить в ваш файл?")
    listed("new", "новое в шаблоне — добавить?")
    listed("new_occupied", "новое в шаблоне на месте вашего файла — показать разницу?")
    listed("removed", "убрано из шаблона — удалить?")
    listed("removed_edited", "убрано из шаблона, у вас правлено или заполнено — остаётся вашим")
    listed("deleted", "удалено вами — вернуть?")
    listed("unknown", "поменял ли шаблон, не узнать — старой версии шаблона нет, сравните сами")
    listed("unsafe", "путь за пределы репо или через симлинк — не трогаю, проверьте .qa/manifest.json и ссылки")
    quiet = sum(len(groups.get(k, [])) for k in ("same", "edited", "own", "same_template", "declined", "outside"))
    if quiet:
        lines.append(f"без изменений: {quiet}")
    return lines


def porcelain_paths(out):
    """Пути из `git status --porcelain -z`: у переименования и копии — оба пути (новый, потом старый)."""
    parts, paths = out.split("\0"), []
    i = 0
    while i < len(parts) and parts[i]:
        code, path = parts[i][:2], parts[i][3:]
        paths.append(path)
        if code[0] in "RC":
            i += 1
            paths.append(parts[i])
        i += 1
    return paths


def one_git_checks(repo):
    """Один git в корне (ревью 0.2.20): коммит sync — коммит общего репо. Папка роли должна быть в git корня
    (М1); индекс вне неё — пуст, иначе `git commit` унёс бы чужое (В2); settings.json корня, который sync может
    дописать, — чист, иначе в коммит sync уехала бы правка человека (В3)."""
    def git(*args):
        return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True).stdout
    if not git("ls-files", "--", ".").strip():
        raise Stop(f"{repo.name}: git корня не отслеживает эту папку (она в .gitignore или не добавлена) — "
                   "коммитить записанное нечем; добавьте её в git корня и закоммитьте, потом sync")
    staged = [rel for rel in git("diff", "--cached", "--name-only", "-z").split("\0")
              if rel and not rel.startswith(repo.name + "/")]
    if staged:
        raise Stop(f"{repo.name}: в индексе git корня чужие правки — {', '.join(staged)}: коммит sync унёс бы их; "
                   "закоммить или убери из индекса (`git restore --staged`), потом sync")
    if git("status", "--porcelain", "--", f"../{SETTINGS}").strip():
        raise Stop(f"{repo.name}: в git незакоммиченные правки {SETTINGS} корня — закоммить или отложи их: "
                   "sync может его дописать и кладёт всё одним коммитом")


def survey(repo):
    """Опись с тем, что нужно и `plan`, и `apply`: маркер, манифест, отрисовка нового шаблона."""
    repo = Path(repo).resolve()
    for rel in (MARKER, MANIFEST, SETTINGS):  # их sync пишет сам — сквозь симлинк запись ушла бы наружу
        if unsafe(repo, rel):
            raise Stop(f"{repo.name}: {Path(rel).as_posix()} — симлинк или путь за пределы репо; sync сквозь него "
                       "не пишет — положите в репо настоящий файл, потом sync")
    if not (repo / MARKER).is_file() or not (repo / MANIFEST).is_file():
        raise Stop(f"{repo.name}: нет маркера или манифеста — это не QA-репо, sync не для него (нужен /qa:init)")
    marker = qa_template.read_marker(repo / MARKER)
    if marker.get("schema") != str(SCHEMA):
        raise Stop(f"{repo.name}: схема данных {marker.get('schema')}, плагин ждёт {SCHEMA} — сначала /qa:migrate")
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=repo, capture_output=True, text=True)
    toplevel = Path(top.stdout.strip()).resolve() if top.returncode == 0 else None
    # Свой git репо или один git в корне проекта (решение 2026-09-29) — иначе откатить запись нечем
    if toplevel not in (repo, repo.parent):
        raise Stop(f"{repo.name}: не в git проекта — sync пишет только туда, где его можно откатить одним "
                   "коммитом: git в корне проекта (или в самом репо); сделайте `git init` и закоммитьте, потом sync")
    status = subprocess.run(["git", "status", "--porcelain", "-z", "--untracked-files=all", "--", "."], cwd=repo,
                            capture_output=True, text=True)
    if status.returncode != 0:
        raise Stop(f"{repo.name}: git status не прошёл: {status.stderr.strip()}")
    prefix = "" if toplevel == repo else repo.name + "/"  # пути `git status` — от корня git
    if any(not rel.removeprefix(prefix).startswith(LAB_SESSIONS + "/") for rel in porcelain_paths(status.stdout)):
        raise Stop(f"{repo.name}: в git незакоммиченные правки — закоммить или отложи их: sync кладёт всё одним коммитом")
    if prefix:
        one_git_checks(repo)
    manifest = json.loads((repo / MANIFEST).read_text(encoding="utf-8"))
    frm, to = manifest["plugin_version"], plugin_version()
    newer = [v for v in (frm, marker.get("plugin_version", frm)) if qa_template.version_key(v) >
             qa_template.version_key(to)]
    if newer:  # иначе sync откатил бы шаблоны к старой версии и понизил её в маркере
        raise Stop(f"{repo.name}: проект уже на шаблоне {max(newer, key=qa_template.version_key)}, а плагин "
                   f"старее — {to}. Сначала обновите плагин (claude plugin update qa@{catalog_name()}), потом sync")
    files = manifest["files"]
    with tempfile.TemporaryDirectory() as tmp:
        # текст шаблона — с именами папок проекта (`localize`): и база, и новый, и то, что сверяется с выданным
        render = lambda templates: qa_template.localize(qa_template.render(templates, marker), marker)  # noqa: E731
        base_tpl, source, commit = find_base(frm, issued_of(files), render, tmp)
        main_base = render(base_tpl) if base_tpl else {}
        settings = repo_settings_delta(repo, marker, base_tpl)
        pending = manifest.get("pending", {})
        role_new = load_json(TEMPLATES / marker["role"] / SETTINGS)
        tags = qa_template.active_tags(marker)
        with_pending(settings, pending.get("settings", {}), load_json(repo / SETTINGS), role_new,
                     FRONTEND_ONLY if tags is not None and "frontend" not in tags else ())
        root = root_settings(repo, marker, base_tpl)
        if root and not root.get("skipped"):
            with_pending(root["settings"], pending.get("root", {}), load_json(Path(root["path"])), role_part(role_new))
        # файл, по которому человек не ответил, сравнивается со своей базой — той версией, с которой его спросили
        waiting = {}
        for version in sorted({e["base"] for e in files.values() if e.get("base") and e["base"] != frm}):
            tpl = find_base(version, issued_of(files, version), render, tmp)[0]
            waiting[version] = render(tpl) if tpl else None
    new = render(TEMPLATES)
    base, base_version = {}, {}  # у каждого файла своя база: версии манифеста или та, с которой ждём ответа
    groups, merges, carried, losses = {}, {}, {}, {}
    for rel in sorted(set(files) | set(new)):
        if rel == SETTINGS:
            continue
        if unsafe(repo, rel):  # ни читать, ни писать, ни удалять
            groups.setdefault("unsafe", []).append(rel)
            continue
        path = repo / rel
        project = path.read_bytes() if path.is_file() else None
        version = (files.get(rel) or {}).get("base") or frm
        rendered = waiting.get(version) if version != frm else (main_base if base_tpl else None)
        base_version[rel] = version
        if rendered is not None and rel in rendered:
            base[rel] = rendered[rel]
        group = classify(rel, files.get(rel), project, new.get(rel), base.get(rel), rendered is not None)
        if group is None:
            continue
        if group in ("merge", "own_changed") and any(binary(x) for x in (base.get(rel), project, new[rel])):
            group = "binary"  # git merge-file двоичное не склеивает — только сказать
        groups.setdefault(group, []).append(rel)
        if group in ("merge", "own_changed"):  # число конфликтов — заранее, чтобы не предлагать невозможное
            merges[rel] = merge_file(base.get(rel, b""), project, new[rel])[0]
            losses[rel] = loss(project, new[rel])
            if merges[rel]:  # конфликт — пробуем перенести правку шаблона в файл человека
                carried[rel] = carry(base.get(rel, b""), project, new[rel]) or {
                    "data": project, "moved": 0, "same": 0, "left": None, "added": 0, "removed": 0, "total": 0}
    return {"repo": repo, "marker": marker, "manifest": manifest, "new": new, "base": base, "from": frm, "to": to,
            "base_version": base_version, "source": source, "commit": commit, "groups": groups, "merges": merges,
            "carried": carried, "losses": losses,
            "settings": settings, "root": root, "one_git": toplevel != repo}


def carry_counts(s):
    """Перенос правки шаблона по файлам с конфликтом склейки: {файл: {moved, same, left}} — `left` числом
    (не текст для переноса — столько, сколько конфликтов)."""
    return {rel: {"moved": c["moved"], "same": c["same"],
                  "left": s["merges"][rel] if c["left"] is None else len(c["left"])}
            for rel, c in s["carried"].items()}


def plan(repo):
    s = survey(repo)
    counts = carry_counts(s)
    return {"repo": str(s["repo"]), "role": s["marker"]["role"], "from": s["from"], "to": s["to"],
            "base": {"source": s["source"], "commit": s["commit"]},
            "groups": s["groups"], "merge": s["merges"], "carry": counts, "loss": s["losses"],
            "settings": s["settings"], "root": s["root"],
            "report_lines": report_lines(s["from"], s["to"], s["source"], s["groups"], s["merges"], s["settings"],
                                         s["root"], counts)}


def settings_change(delta, decisions, new):
    """Что записать в settings: молчаливое из описи и принятое человеком из предложенного. new — settings
    шаблона (значения полей каталога)."""
    def chosen(key):
        return [x for x in delta[f"offer_{key}"] if x in decisions.get(f"offer_{key}", [])]

    fields = delta["add_market"] + chosen("market")
    return {"add_allow": delta["add_allow"] + chosen("allow"), "add_plugins": delta["add_plugins"] + chosen("plugins"),
            "drop_allow": sorted(set(decisions.get("drop_allow", []))),
            "market": {k: market(new)[k] for k in fields}}


def merged_settings(data, change):
    """settings: новые разрешения и плагины в конец, убранное по «да» — вон, поля каталога — в его запись,
    чужое — как было."""
    if change["drop_allow"]:
        data["permissions"]["allow"] = [a for a in data["permissions"]["allow"] if a not in change["drop_allow"]]
    if change["add_allow"]:
        data.setdefault("permissions", {}).setdefault("allow", []).extend(change["add_allow"])
    for plugin in change["add_plugins"]:
        data.setdefault("enabledPlugins", {})[plugin] = True
    if change["market"]:
        data["extraKnownMarketplaces"][catalog_name()].update(change["market"])
    return dump_json(data).encode("utf-8")


def write_all(base, targets):
    """Запись одним заходом: [(путь от `base`, байты | None — удалить)]. Цель с теми же байтами (и удаление
    того, чего нет) пропускается — повторный sync без изменений ничего не пишет и коммита не просит (ревью
    2026-09-30, находка 3). Сначала все цели проверяются на запись — нельзя хоть одну, стоп до первой записи;
    упало посреди — записанное откатывается (прежние байты назад, новые файлы и папки — вон). Возвращает
    записанное: [путь от `base`]."""
    def same(rel, data):
        path = base / rel
        if data is None:
            return not path.exists()
        return path.is_file() and not path.is_symlink() and path.read_bytes() == data

    targets = [(rel, data) for rel, data in targets if not same(rel, data)]
    for rel, data in targets:
        path = base / rel
        parent = next(p for p in path.parents if p.exists())
        if path.is_dir() or not parent.is_dir():
            raise Stop(f"{rel}: на месте файла или его папки — другое; sync ничего не записал")
        if (path.exists() and not os.access(path, os.W_OK)) or not os.access(parent, os.W_OK | os.X_OK):
            raise Stop(f"{rel}: нет прав на запись — sync ничего не записал; поправьте права, потом sync")
    saved = [(base / rel, (base / rel).read_bytes() if (base / rel).exists() else None) for rel, _ in targets]
    made = []
    try:
        for rel, data in targets:
            path = base / rel
            if data is None:
                path.unlink()
                continue
            missing = [p for p in reversed(path.parents) if not p.exists()]
            for folder in missing:
                folder.mkdir()
                made.append(folder)
            path.write_bytes(data)
    except Exception as e:
        for path, old in reversed(saved):
            try:
                if old is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_bytes(old)
            except OSError:
                pass
        for folder in reversed(made):
            try:
                folder.rmdir()
            except OSError:
                pass
        raise Stop(f"запись прервалась ({e}); записанное откатил — проект как был до sync") from e
    return [rel for rel, _ in targets]


DECISIONS = {
    "merge": "правлено и вами, и шаблоном: {файл: merge | template}",
    "own_changed": "своё, шаблон поменял: {файл: merge | template}",
    "add": "новое в шаблоне: [файл] (на месте своего файла — берём его своим, не перезаписываем)",
    "delete": "убрано из шаблона, нетронуто: [файл]",
    "keep": "оставить как есть — это ответ, больше не спрошу: [файл] (правлено и вами, и шаблоном; своё, шаблон "
            "поменял; убрано из шаблона). Файла нет ни в одном решении — ответа нет, sync спросит снова",
    "text": "файл, собранный с человеком (основа — `draft`): {файл: путь к собранному} — у правленого и вами, и "
            "шаблоном и у своего, что шаблон поменял",
    "restore": "удалено вами — вернуть: [файл]",
    "decline": "удалено вами — не возвращать: [файл]",
    "drop_allow": "шаблон убрал разрешение — убрать из settings: [разрешение]",
    "offer_allow": "старой версии шаблона нет, разрешение шаблона — добавить в settings: [разрешение]",
    "offer_plugins": "старой версии шаблона нет, плагин шаблона — включить в settings: [плагин]",
    "offer_market": "старой версии шаблона нет, поле каталога шаблона — добавить в settings: [поле]",
    "keep_allow": "шаблон убрал разрешение — оставить (ответ, больше не спрошу): [разрешение]",
    "no_offer": "старой версии шаблона нет — не добавлять (ответ, больше не спрошу): [разрешение, плагин, поле]",
    "root": "settings.json корня: {offer_plugins: [плагин], offer_market: [поле], no_offer: [...]} — как у репо",
}


def check_decisions(d, s):
    """Каждое решение — про файл своей группы; склейка — только без конфликтов. Иначе Stop, ничего не пишем."""
    unknown = sorted(set(d) - set(DECISIONS))
    if unknown:
        raise Stop(f"нет таких решений: {', '.join(unknown)}; есть: " +
                   "; ".join(f"{k} — {v}" for k, v in DECISIONS.items()))
    groups = s["groups"]

    def need(key, rels, *names):
        allowed = {rel for name in names for rel in groups.get(name, [])}
        wrong = sorted(set(rels) - allowed)
        if wrong:
            raise Stop(f"{key}: не из группы {'/'.join(names)}: {', '.join(wrong)} — решение по свежей описи (plan)")

    for key, group in (("merge", "merge"), ("own_changed", "own_changed")):
        chosen = d.get(key, {})
        need(key, chosen, group)
        bad = sorted(rel for rel, v in chosen.items() if v not in ("merge", "template"))
        if bad:
            raise Stop(f"{key}: решение — merge или template: {', '.join(bad)}")
        counts = carry_counts(s)
        for rel, v in chosen.items():
            if v == "merge" and s["merges"][rel] and counts[rel]["left"]:
                raise Stop(f"{key}: {rel} склеивается с конфликтом, и правка шаблона не встаёт само (кусков: "
                           f"{counts[rel]['left']}) — только template или оставить своё (keep)")
    need("add", d.get("add", []), "new", "new_occupied")
    need("delete", d.get("delete", []), "removed")
    need("keep", d.get("keep", []), "merge", "own_changed", "removed")
    both = sorted(set(d.get("keep", [])) & (set(d.get("merge", {})) | set(d.get("own_changed", {})) |
                                            set(d.get("delete", []))))
    if both:
        raise Stop(f"keep: и оставить, и взять шаблон или удалить: {', '.join(both)}")
    texts = d.get("text", {})
    need("text", texts, "merge", "own_changed")
    both = sorted(set(texts) & (set(d.get("keep", [])) | set(d.get("merge", {})) | set(d.get("own_changed", {}))))
    if both:
        raise Stop(f"text: по файлу два решения — собранный текст и ещё одно: {', '.join(both)}")
    for rel, path in texts.items():
        if not Path(path).is_file():
            raise Stop(f"text: {rel} — нет файла {path}")
        if CONFLICT_MARK.search(Path(path).read_text(encoding="utf-8", errors="replace")):
            raise Stop(f"text: {rel} — в собранном остались маркеры конфликта (<<<<<<< / >>>>>>>) — каждый кусок "
                       "решите с человеком, потом apply")
    need("restore", d.get("restore", []), "deleted")
    need("decline", d.get("decline", []), "deleted")
    both = sorted(set(d.get("restore", [])) & set(d.get("decline", [])))
    if both:
        raise Stop(f"и вернуть, и не возвращать: {', '.join(both)}")
    for key in ("drop_allow", "keep_allow"):
        wrong = sorted(set(d.get(key, [])) - set(s["settings"]["drop_allow"]))
        if wrong:
            raise Stop(f"{key}: шаблон это не убирал (план: settings.drop_allow): {', '.join(wrong)}")
    both = sorted(set(d.get("drop_allow", [])) & set(d.get("keep_allow", [])))
    if both:
        raise Stop(f"и убрать, и оставить: {', '.join(both)}")
    offered = {x for key in ("offer_allow", "offer_plugins", "offer_market") for x in s["settings"][key]}
    wrong = sorted(set(d.get("no_offer", [])) - offered)
    if wrong:
        raise Stop(f"no_offer: этого не предлагали (план: settings.offer_*): {', '.join(wrong)}")
    both = sorted(set(d.get("no_offer", [])) & {x for k in ("offer_allow", "offer_plugins", "offer_market")
                                                for x in d.get(k, [])})
    if both:
        raise Stop(f"и добавить, и не добавлять: {', '.join(both)}")
    for key in ("offer_allow", "offer_plugins", "offer_market"):
        wrong = sorted(set(d.get(key, [])) - set(s["settings"][key]))
        if wrong:
            raise Stop(f"{key}: этого не предлагали (план: settings.{key}): {', '.join(wrong)}")
    if "root" in d:
        root = s["root"]
        if not root or root.get("skipped"):
            raise Stop("root: settings.json корня sync не трогает (план: root) — решения по нему не нужны")
        extra = sorted(set(d["root"]) - {"offer_plugins", "offer_market", "no_offer"})
        if extra:
            raise Stop(f"root: у корня только offer_plugins, offer_market и no_offer, не {', '.join(extra)}")
        data = load_json(Path(root["path"]))
        have = {"offer_plugins": set(data.get("enabledPlugins", {})), "offer_market": set(market(data)),
                "no_offer": set()}
        offers = {**root["settings"], "no_offer": root["settings"]["offer_plugins"] + root["settings"]["offer_market"]}
        for key, chosen in d["root"].items():  # уже есть — ответ пришёл с другим репо, не ошибка
            wrong = sorted(set(chosen) - set(offers[key]) - have[key])
            if wrong:
                raise Stop(f"root.{key}: этого не предлагали (план: root.settings.{key}): {', '.join(wrong)}")


def apply(repo, decisions):
    """Молчаливая часть и решения человека (`DECISIONS`) по свежей описи; сначала проверка, потом запись."""
    s = survey(repo)
    check_decisions(decisions, s)
    repo, files, new, base = s["repo"], dict(s["manifest"]["files"]), s["new"], s["base"]
    writes, updated, deletes = {}, [], []
    answered = {*decisions.get("merge", {}), *decisions.get("own_changed", {}), *decisions.get("delete", []),
                *decisions.get("keep", []), *decisions.get("text", {})}
    # Нет ответа — не отказ (решение человека 2026-09-28): файл как был, в манифесте — `base`, версия шаблона,
    # с которой его спросили; следующий sync сравнит с ней и спросит снова. Отказ — только явный `keep`.
    waiting = sorted(rel for g in ("merge", "own_changed", "removed") for rel in s["groups"].get(g, [])
                     if rel not in answered)
    for group, rels in s["groups"].items():
        for rel in rels:
            if group == "update":
                writes[rel] = new[rel]
                updated.append(rel)
                files[rel] = {**files[rel], "sha256": qa_template.sha256(new[rel])}
            elif group == "same":
                files[rel] = {**files[rel], "sha256": qa_template.sha256(new[rel])}
            elif group == "removed_edited" or (group == "removed" and rel in answered):
                del files[rel]
    skip = {SETTINGS, *s["groups"].get("unsafe", [])}
    for rel in [rel for rel in files if rel not in skip and not (repo / rel).exists() and rel not in new]:
        del files[rel]  # нет ни в проекте, ни в шаблоне
    for key in ("merge", "own_changed"):
        for rel, choice in decisions.get(key, {}).items():
            if choice == "merge" and s["merges"][rel]:  # конфликт склейки — перенос правки шаблона в файл человека
                writes[rel] = s["carried"][rel]["data"]
            elif choice == "merge":
                writes[rel] = merge_file(base.get(rel, b""), (repo / rel).read_bytes(), new[rel])[1]
            else:
                writes[rel] = new[rel]
            if choice == "template" or key == "own_changed":  # склеенное своё — своё; склеенное правленое — правлено
                files[rel] = {**files[rel], "sha256": qa_template.sha256(writes[rel])}
    for rel, path in decisions.get("text", {}).items():  # собрано с человеком: своё — своим, правленое — правленым
        writes[rel] = Path(path).read_bytes()
        if rel in s["groups"].get("own_changed", []):
            files[rel] = {**files[rel], "sha256": qa_template.sha256(writes[rel])}
    occupied = set(s["groups"].get("new_occupied", []))
    for rel in decisions.get("add", []):
        if rel in occupied:
            files[rel] = {"sha256": qa_template.sha256((repo / rel).read_bytes()), "state": "own"}
        else:
            writes[rel] = new[rel]
            files[rel] = {"sha256": qa_template.sha256(new[rel]), "state": "issued"}
    deletes += decisions.get("delete", [])
    for rel in decisions.get("restore", []):
        writes[rel] = new[rel]
        files[rel] = {**files[rel], "sha256": qa_template.sha256(new[rel])}
    for rel in decisions.get("decline", []):
        files[rel] = {**files[rel], "state": "declined"}
    unsafe_rels = set(s["groups"].get("unsafe", []))
    for rel, entry in files.items():
        if rel in waiting:
            files[rel] = {**entry, "base": entry.get("base") or s["from"]}
        elif "base" in entry and rel not in unsafe_rels:  # ответ получен или спрашивать больше не о чем
            files[rel] = {k: v for k, v in entry.items() if k != "base"}
    change = settings_change(s["settings"], decisions, load_json(TEMPLATES / s["marker"]["role"] / SETTINGS))
    if SETTINGS in files and (repo / SETTINGS).is_file():
        data = (repo / SETTINGS).read_bytes()
        if any(change.values()):  # без дельты не переписываем: чужое форматирование (plugin install) — как было
            data = writes[SETTINGS] = merged_settings(json.loads(data), change)
        files[SETTINGS] = {**files[SETTINGS], "sha256": qa_template.sha256(data)}
    root_out, root_write = None, []
    if s["root"] and not s["root"].get("skipped"):
        path = Path(s["root"]["path"])
        role_new = role_part(load_json(TEMPLATES / s["marker"]["role"] / SETTINGS))
        root_change = settings_change(s["root"]["settings"], decisions.get("root", {}), role_new)
        if any(root_change.values()):  # без дельты не переписываем
            root_write = [(str(path), merged_settings(json.loads(path.read_text(encoding="utf-8")), root_change))]
        root_out = {"path": str(path), "add_plugins": root_change["add_plugins"], "market": sorted(root_change["market"])}
    manifest = {**s["manifest"], "plugin_version": s["to"], "files": dict(sorted(files.items()))}
    pending = {"settings": next_pending(s["settings"], decisions)}
    if s["root"] and not s["root"].get("skipped"):
        pending["root"] = next_pending(s["root"]["settings"], decisions.get("root", {}))
    pending = {k: v for k, v in pending.items() if v}
    manifest.pop("pending", None)
    if pending:
        manifest["pending"] = pending
    marker = (repo / MARKER).read_text(encoding="utf-8")
    marker = re.sub(r"^plugin_version: .*$", f"plugin_version: {s['to']}", marker, count=1, flags=re.M)
    done = write_all(repo, [*writes.items(), *((rel, None) for rel in deletes),
                            (MANIFEST.as_posix(), dump_json(manifest).encode("utf-8")),
                            (MARKER.as_posix(), marker.encode("utf-8")), *root_write])
    from qa_codex import maybe_configure
    codex_written = maybe_configure(repo)
    return {"repo": str(repo), "from": s["from"], "to": s["to"], "updated": sorted(updated),
            "written": sorted(set(writes) - set(updated) - {SETTINGS}), "deleted": sorted(deletes),
            "declined": sorted(decisions.get("decline", [])), "kept": sorted(decisions.get("keep", [])),
            "waiting": waiting, "root": root_out,
            "git_add": git_add(repo, s["one_git"], [t for t in root_write if t[0] in done]) if done or codex_written else None,
            "settings": {"add_allow": change["add_allow"], "add_plugins": change["add_plugins"],
                         "drop_allow": change["drop_allow"], "market": sorted(change["market"])}}


def git_add(repo, one_git, root_write):
    """Команда `git add` коммита sync из папки репо. Один git в корне — settings.json корня в том же репо:
    что sync в нём поменял, едет тем же коммитом (путь — от папки репо, как вся команда)."""
    return GIT_ADD + [os.path.relpath(path, repo) for path, _ in root_write] if one_git else GIT_ADD


# --- корень проекта (решение человека 2026-09-30) -------------------------------------------

ROOT_RECORD = Path(".qa") / "root.json"  # учёт корня: версия шаблона и отпечаток шаблонной карты (пишет qa-init.py)
ROOT_MAP = "CLAUDE.md"
ROOT_PATHS = (ROOT_MAP, ".gitignore", SETTINGS, ROOT_RECORD.as_posix())  # что sync в корне читает и пишет
SOURCE_NAMES = {"current": "шаблоны этого плагина", "cache": "кэш плагина", "clone": "история каталога",
                "none": "не найдена"}


def root_repos(root):
    """Папки проекта с маркером — записями для отрисовки корня, как `marker_repo` у `qa-init.py`; название —
    из маркера первой папки."""
    repos, title = [], None
    for path in sorted(p for p in root.iterdir() if p.is_dir() and (p / MARKER).is_file()):
        marker = qa_template.read_marker(path / MARKER)
        if marker.get("schema") != str(SCHEMA):
            raise Stop(f"{path.name}: схема данных {marker.get('schema')}, плагин ждёт {SCHEMA} — сначала /qa:migrate")
        if title is None:
            title = marker.get("title", root.name)
        repo = {"role": marker.get("role"), "dir": path.name}
        if repo["role"] == "autotests":
            repo["layers"] = [x for x in marker.get("layers") or [] if x in qa_template.LAYERS]
            if marker.get("frontend_lib"):
                repo["frontend_lib"] = marker["frontend_lib"]
        if marker["paths"]:
            repo["paths"] = marker["paths"]
        repos.append(repo)
    return repos, title


def root_checks(root):
    """Корень в своём git — True: файлы корня, которые sync пишет, чисты, индекс пуст (иначе `git commit` унёс
    бы чужое). Корень не git (два git, проекты до 2026-09-29) — False: пишем только молчаливое и принятое,
    откат — руками. Корень внутри чужого git — стоп."""
    for rel in ROOT_PATHS:
        if unsafe(root, rel):
            raise Stop(f"корень: {rel} — симлинк или путь за пределы корня; sync сквозь него не пишет — положите "
                       "настоящий файл, потом sync")
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=root, capture_output=True, text=True)
    if top.returncode != 0:
        return False
    if Path(top.stdout.strip()).resolve() != root:  # ревью 2026-09-30, находка 9: писали бы в чужой репо
        raise Stop(f"корень лежит внутри чужого git ({top.stdout.strip()}) — sync туда не пишет: сделайте корень "
                   "своим git (`git init` в нём) или вынесите проект из чужого репо, потом sync")

    def git(*args):
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True).stdout

    dirty = git("status", "--porcelain", "--untracked-files=all", "--", *ROOT_PATHS).strip()
    if dirty:
        raise Stop(f"корень: в git незакоммиченные правки файлов корня ({', '.join(ROOT_PATHS)}) — закоммить или "
                   "отложи их: sync кладёт всё одним коммитом")
    staged = [rel for rel in git("diff", "--cached", "--name-only", "-z").split("\0") if rel]
    if staged:
        raise Stop(f"корень: в индексе git чужие правки — {', '.join(staged)}: коммит sync унёс бы их; "
                   "закоммить или убери из индекса (`git restore --staged`), потом sync")
    return True


def survey_root(root):
    """Опись корня: папки, учёт, база, разрешения шаблона. Без учёта (корень собран до шаблона, как у FPS и
    Shooting) — «шаблон корню раньше ничего не давал» (решение человека 2026-09-30): недостающее — молча."""
    root = Path(root).resolve()
    repos, title = root_repos(root) if root.is_dir() else ([], None)
    if not repos:
        raise Stop(f"{root}: нет ни одной папки с {MARKER.as_posix()} — это не корень QA-проекта (нужен /qa:init)")
    in_git = root_checks(root)
    path = root / ROOT_RECORD
    try:  # ревью, находка 7: битый файл — стоп с причиной, не трейсбек
        record = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
        project = load_json(root / SETTINGS)
    except ValueError as e:
        raise Stop(f"корень: битый JSON ({e}) в {ROOT_RECORD.as_posix()} или {SETTINGS} — поправьте файл, потом sync")
    if record is not None and not (isinstance(record, dict) and isinstance(record.get("plugin_version"), str)):
        raise Stop(f"корень: в {ROOT_RECORD.as_posix()} нет версии — учёт битый; поправьте или удалите его (sync "
                   "заведёт заново, как у корня без учёта), потом sync")
    if not isinstance(project, dict):
        raise Stop(f"корень: {SETTINGS} — не объект JSON; поправьте, потом sync")
    frm, to = (record or {}).get("plugin_version"), plugin_version()
    if frm and qa_template.version_key(frm) > qa_template.version_key(to):
        raise Stop(f"корень: уже на шаблоне {frm}, а плагин старее — {to}. Сначала обновите плагин "
                   f"(claude plugin update qa@{catalog_name()}), потом sync")
    git_root = (root / ".git").exists()  # как у qa-init.py: карта говорит «один git в корне»
    inputs = qa_template.root_inputs(title, repos, git_root)
    # база рисуется с теми папками, что были при учёте (ревью 2026-09-30, находка 4); карта, ждущая ответа, —
    # со своими версией и папками
    rec_inputs = (record or {}).get("inputs") or inputs

    def draw(templates, inp):
        return {k: v.encode("utf-8") for k, v in
                qa_template.render_root(templates, inp["title"], inp["repos"], inp["git_root"]).items()}

    files = dict((record or {}).get("files", {}))
    entry = files.get(ROOT_MAP)
    map_version = (entry or {}).get("base") or frm  # карта без ответа — со своей версией, как файлы папок
    map_inputs = (entry or {}).get("inputs") or rec_inputs
    base_tpl, source, commit, base_map, has_base = None, "none", None, None, False
    with tempfile.TemporaryDirectory() as tmp:
        if record:
            issued = {rel: e["sha256"] for rel, e in files.items() if e.get("state", "issued") == "issued"
                      and not e.get("base")}
            base_tpl, source, commit = find_base(frm, issued, lambda t: draw(t, rec_inputs), tmp)
        base_allow = qa_template.root_template_allow(base_tpl, rec_inputs["repos"]) if base_tpl else []
        if entry and entry.get("base"):  # ждёт ответа — своя база, сверенная с отпечатком (находка 8)
            map_tpl = find_base(map_version, {ROOT_MAP: entry["sha256"]}, lambda t: draw(t, map_inputs), tmp)[0]
        else:
            map_tpl = base_tpl
        if map_tpl:
            base_map, has_base = draw(map_tpl, map_inputs).get(ROOT_MAP), True
    new_allow = qa_template.root_template_allow(TEMPLATES, repos)
    settings = settings_delta(project, {"permissions": {"allow": new_allow}}, {"permissions": {"allow": base_allow}},
                              record is None or base_tpl is not None)
    with_pending(settings, (record or {}).get("pending", {}), project, {"permissions": {"allow": new_allow}})
    new = draw(TEMPLATES, inputs)
    path = root / ROOT_MAP
    have = path.read_bytes() if path.is_file() else None
    if entry is None:  # учёта карты нет — корень собран до шаблона: своя она или шаблонная, не узнать
        group = "new" if have is None else "same" if have == new[ROOT_MAP] else "unknown"
    else:
        group = classify(ROOT_MAP, {**entry, "state": entry.get("state", "issued")}, have, new[ROOT_MAP],
                         base_map, has_base)
    conflicts = merge_file(base_map or b"", have, new[ROOT_MAP])[0] if group == "merge" else None
    moved = carry(base_map or b"", have, new[ROOT_MAP]) if conflicts else None  # как у файлов репо
    return {"root": root, "repos": repos, "title": title, "record": record, "files": files, "from": frm, "to": to,
            "map_carried": moved, "map_loss": loss(have, new[ROOT_MAP]) if group in ("merge", "unknown") else None,
            "source": source, "commit": commit, "in_git": in_git, "project": project,
            "settings": {k: settings[k] for k in ("add_allow", "drop_allow", "offer_allow")},
            "new": new, "have": have, "base_map": base_map, "map_version": map_version,
            "inputs": inputs, "map_inputs": map_inputs,
            "map": {"group": group, "conflicts": conflicts}, "gitignore": gitignore_missing(root, new)}


def gitignore_missing(root, new):
    """Строки `.gitignore` шаблона корня, которых в корне нет, — как у `qa-init.py`: пустые и комментарии не в
    счёт; файла нет — весь шаблон."""
    text = new.get(".gitignore", b"").decode("utf-8")
    path = root / ".gitignore"
    have = set(path.read_text(encoding="utf-8").splitlines()) if path.is_file() else set()
    return [line for line in text.splitlines() if line and not line.startswith("#") and line not in have]


MAP_LINES = {
    "update": "карта корня CLAUDE.md нетронута, шаблон поменял — обновлю молча",
    "new": "карты корня CLAUDE.md нет — положу из шаблона",
    "edited": "карта корня CLAUDE.md — с вашими правками, шаблон её не менял: не трогаю",
    "unknown": "карта корня CLAUDE.md отличается от шаблона, учёта нет — чьи это правки, не узнать: покажу "
               "разницу и спрошу (оставить своё / собрать вместе / заменить шаблоном)",
    "deleted": "карта корня CLAUDE.md удалена вами — вернуть?",
}


def root_report_lines(s):
    if s["from"]:
        lines = [f"корень: шаблон {s['from']} → {s['to']}; старая версия шаблона: {SOURCE_NAMES[s['source']]}"]
    else:
        lines = [f"корень: учёта нет (корень собран до шаблона) — заведу .qa/root.json; шаблон → {s['to']}"]
    st = s["settings"]
    if st["add_allow"]:
        lines.append(f"разрешения корня молча: +{len(st['add_allow'])}: {', '.join(st['add_allow'])}")
    if st["drop_allow"]:
        lines.append(f"разрешения корня — шаблон убрал, убрать?: {', '.join(st['drop_allow'])}")
    if st["offer_allow"]:
        lines.append("разрешения корня — в шаблоне есть, у вас нет; убирали ли вы сами, не узнать — старой версии "
                     f"шаблона нет; добавить?: {', '.join(st['offer_allow'])}")
    m = s["map"]
    if m["group"] == "merge":
        left = map_carry(s)["left"] if m["conflicts"] else 0
        note = ("без конфликта" if not m["conflicts"] else "добавка шаблона встаёт в вашу карту сама" if not left
                else f"не встаёт само: кусков {left} — покажу и спрошу")
        lines.append(f"карта корня CLAUDE.md — правили и вы, и шаблон: добавить правку шаблона в вашу карту? ({note})")
    elif m["group"] == "unknown" and s["record"]:  # ревью, находка 6: учёт есть — нет старой версии шаблона
        lines.append("карта корня CLAUDE.md правлена, а старой версии шаблона нет — поменял ли её шаблон, не узнать: "
                     "покажу разницу и спрошу (оставить своё / собрать вместе / заменить шаблоном)")
    elif m["group"] in MAP_LINES:
        lines.append(MAP_LINES[m["group"]])
    if not s["in_git"]:  # решение человека по ревью: сказать до «да»
        lines.append("корень не в git — sync запишет в него, коммита не будет: откатить можно только руками")
    if s["gitignore"]:
        lines.append(f".gitignore корня молча: +{len(s['gitignore'])}: {', '.join(s['gitignore'])}")
    return lines


def map_carry(s):
    """Перенос правки шаблона в карту человека при конфликте склейки: {moved, same, left} — или None."""
    if not s["map"]["conflicts"]:
        return None
    c = s["map_carried"]
    if c is None:  # не текст для переноса
        return {"moved": 0, "same": 0, "left": s["map"]["conflicts"]}
    return {"moved": c["moved"], "same": c["same"], "left": len(c["left"])}


def plan_root(root):
    s = survey_root(root)
    return {"root": str(s["root"]), "from": s["from"], "to": s["to"],
            "base": {"source": s["source"], "commit": s["commit"]}, "git": s["in_git"], "settings": s["settings"],
            "map": s["map"], "map_carry": map_carry(s), "map_loss": s["map_loss"],
            "gitignore": s["gitignore"], "report_lines": root_report_lines(s)}


ROOT_DECISIONS = {
    "drop_allow": "шаблон убрал разрешение корня — убрать: [разрешение]",
    "offer_allow": "старой версии шаблона нет, разрешение шаблона — добавить в корень: [разрешение]",
    "keep_allow": "шаблон убрал разрешение корня — оставить (ответ, больше не спрошу): [разрешение]",
    "no_offer": "старой версии шаблона нет — не добавлять в корень (ответ, больше не спрошу): [разрешение]",
    "map": "карта корня: merge (склейка без конфликта) | template (взять шаблон) | keep (оставить своё) — у "
           "merge и unknown; restore | decline — у deleted",
    "map_text": "карта корня, собранная с человеком, — путь к файлу (у merge и unknown)",
}
MAP_CHOICES = {"merge": {"merge", "template", "keep"}, "unknown": {"template", "keep"},
               "deleted": {"restore", "decline"}}


def check_root_decisions(d, s):
    unknown = sorted(set(d) - set(ROOT_DECISIONS))
    if unknown:
        raise Stop(f"корень: нет таких решений: {', '.join(unknown)}; есть: " +
                   "; ".join(f"{k} — {v}" for k, v in ROOT_DECISIONS.items()))
    for key, group in (("drop_allow", "drop_allow"), ("keep_allow", "drop_allow"), ("offer_allow", "offer_allow"),
                       ("no_offer", "offer_allow")):
        wrong = sorted(set(d.get(key, [])) - set(s["settings"][group]))
        if wrong:
            raise Stop(f"корень, {key}: этого не предлагали (план: settings.{group}): {', '.join(wrong)}")
    for a, b in (("drop_allow", "keep_allow"), ("offer_allow", "no_offer")):
        both = sorted(set(d.get(a, [])) & set(d.get(b, [])))
        if both:
            raise Stop(f"корень: и {a}, и {b}: {', '.join(both)}")
    group = s["map"]["group"]
    if "map" in d and "map_text" in d:
        raise Stop("корень: map и map_text вместе — одно решение по карте")
    if "map" in d and d["map"] not in MAP_CHOICES.get(group, set()):
        raise Stop(f"корень, map: {d['map']} не подходит карте в группе {group} (план: map); можно: "
                   f"{', '.join(sorted(MAP_CHOICES.get(group, []))) or 'ничего — решения не нужно'}")
    if d.get("map") == "merge" and s["map"]["conflicts"] and map_carry(s)["left"]:
        raise Stop("корень, map: карта склеивается с конфликтом, и правка шаблона не встаёт само (кусков: "
                   f"{map_carry(s)['left']}) — только template, keep или map_text")
    if "map_text" in d:
        if group not in ("merge", "unknown"):
            raise Stop(f"корень, map_text: у карты в группе {group} решения не нужно (план: map)")
        if not Path(d["map_text"]).is_file():
            raise Stop(f"корень, map_text: нет файла {d['map_text']}")
        text = Path(d["map_text"]).read_text(encoding="utf-8", errors="replace")
        if CONFLICT_MARK.search(text):
            raise Stop("корень, map_text: в карте остались маркеры конфликта (<<<<<<< / >>>>>>>) — каждый кусок "
                       "решите с человеком, потом apply-root")


def apply_root(root, decisions):
    """Молчаливое и решения человека по свежей описи корня; учёт — на версию плагина. Сначала проверка."""
    s = survey_root(root)
    check_root_decisions(decisions, s)
    root, files = s["root"], s["files"]
    delta = {**s["settings"], "add_plugins": [], "offer_plugins": [], "add_market": [], "offer_market": []}
    change = settings_change(delta, decisions, {})
    targets = []
    if change["add_allow"] or change["drop_allow"]:  # без дельты не переписываем
        targets.append((SETTINGS, merged_settings(s["project"], change)))
    waiting = []
    group, choice, new_map = s["map"]["group"], decisions.get("map"), s["new"][ROOT_MAP]
    text = Path(decisions["map_text"]).read_bytes() if "map_text" in decisions else None
    data = {"update": new_map, "new": new_map}.get(group)
    if text is not None:
        data = text
    elif choice == "merge" and s["map"]["conflicts"]:  # перенос правки шаблона в карту человека
        data = s["map_carried"]["data"]
    elif choice == "merge":
        data = merge_file(s["base_map"] or b"", s["have"], new_map)[1]
    elif choice in ("template", "restore"):
        data = new_map
    if data is not None:
        targets.append((ROOT_MAP, data))
    # В учёте — шаблонная карта этой версии: файл от неё отличается — правка человека, её склеиваем поверх
    if choice == "decline":
        files[ROOT_MAP] = {"sha256": qa_template.sha256(new_map), "state": "declined"}
    elif group in ("merge", "unknown", "deleted") and choice is None and text is None:
        waiting.append(ROOT_MAP)  # нет ответа — не отказ: как была, спросим снова
        if ROOT_MAP in files:
            files[ROOT_MAP] = {**files[ROOT_MAP], "base": s["map_version"], "inputs": s["map_inputs"]}
    elif group != "declined":
        files[ROOT_MAP] = {"sha256": qa_template.sha256(new_map)}
    if s["gitignore"]:
        path = root / ".gitignore"
        have = path.read_text(encoding="utf-8") if path.is_file() else ""
        if have:
            add = ("" if have.endswith("\n") else "\n") + "# qa-toolkit\n" + "".join(f"{l}\n" for l in s["gitignore"])
        else:
            add = s["new"][".gitignore"].decode("utf-8")
        targets.append((".gitignore", (have + add).encode("utf-8")))
    record = {"plugin_version": s["to"], "inputs": s["inputs"], "files": dict(sorted(files.items()))}
    pending = next_pending(s["settings"], decisions)
    if pending:
        record["pending"] = pending
    targets.append((ROOT_RECORD.as_posix(), dump_json(record).encode("utf-8")))
    written = write_all(root, targets)
    from qa_codex import maybe_configure
    codex_written = maybe_configure(root)
    written += [os.path.relpath(p, root) for p in codex_written]
    return {"root": str(root), "from": s["from"], "to": s["to"], "written": written, "waiting": waiting,
            "git": s["in_git"],
            "map": {"group": group, "choice": "map_text" if text is not None else choice},
            "gitignore": s["gitignore"], "settings": {"add_allow": change["add_allow"], "drop_allow": change["drop_allow"]},
            "git_add": ["git", "add", "--", *written] if s["in_git"] and written else None}


def unified(a, b, left, right):
    if a is None and b is None:
        return ""
    if binary(a) or binary(b):
        return "двоичный файл — построчно не показать\n"
    try:
        la = (a or b"").decode("utf-8").splitlines(keepends=True)
        lb = (b or b"").decode("utf-8").splitlines(keepends=True)
    except UnicodeDecodeError:
        return "двоичный файл — построчно не показать\n"
    # строка без перевода в конце файла — как у git diff, иначе она склеится со следующей строкой diff
    return "".join(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n"
                   for line in difflib.unified_diff(la, lb, left, right))


def carried_text(project, moved, frm, to):
    """Что показать, когда склейка с конфликтом: файл человека с перенесённой правкой шаблона (без маркеров —
    чужого текста в его файле не показываем) и куски, которые не встали."""
    out = ""
    if moved["moved"]:
        out += (f"== ваш файл после: добавлено строк: {moved['added']}, убрано: {moved['removed']}; ваших строк не "
                f"тронуто: {moved['total'] - moved['removed']} из {moved['total']}\n"
                + unified(project, moved["data"], "сейчас", "после"))
    if moved["same"]:
        out += f"== уже есть у вас — кусков: {moved['same']}\n"
    if moved["left"]:
        out += (f"== не встаёт само — кусков: {len(moved['left'])}: у вас это место своё; шаблон поменял его так "
                "(ваш файл здесь не меняется)\n")
        for piece in moved["left"]:
            out += unified("".join(line + "\n" for line in piece["old"]).encode("utf-8"),
                           "".join(line + "\n" for line in piece["new"]).encode("utf-8"),
                           f"шаблон {frm}", f"шаблон {to}")
    return out


def outside(dest, project):
    """Путь основы «собрать вместе» — вне проекта: до «да» sync в проект не пишет."""
    dest = Path(dest).resolve()
    if dest == project or project in dest.parents:
        raise Stop(f"{dest}: основа склейки — во временный файл, не в проект (до «да» sync в проект не пишет)")
    return dest


def draft(repo, rel, dest):
    """Основа «собрать вместе» для файла репо (решение человека 2026-10-02) — в файл вне проекта: файл человека,
    в который уже перенесено всё, что встало само; `left` — куски правки шаблона, которые не встали: их агент
    ставит на место с человеком и отдаёт собранное решением `text`."""
    s = survey(repo)
    if rel not in s["groups"].get("merge", []) + s["groups"].get("own_changed", []):
        raise Stop(f"{rel}: нечего собирать — файл не из тех, что правили и вы, и шаблон (план: merge, own_changed)")
    dest = outside(dest, s["repo"])
    project = (s["repo"] / rel).read_bytes()
    if not s["merges"][rel]:
        data, moved, left = merge_file(s["base"].get(rel, b""), project, s["new"][rel])[1], None, []
    elif s["carried"][rel]["left"] is None:
        raise Stop(f"{rel}: не текст для переноса (концы строк CRLF) — только заменить шаблоном или оставить своё")
    else:
        c = s["carried"][rel]
        data, moved, left = c["data"], c["moved"], c["left"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return {"file": str(dest), "basis": "own", "moved": moved, "left": left}


def diff(repo, rel, text=None):
    """Что показать человеку по файлу перед вопросом — по его группе в свежей описи; `text` — файл, собранный
    с человеком: сейчас → он."""
    if text is not None:
        path = Path(repo).resolve() / rel
        return f"== {rel}: так станет (собрано с вами)\n" + unified(
            path.read_bytes() if path.is_file() else None, Path(text).read_bytes(), "сейчас", "после")
    s = survey(repo)
    group = next((g for g, rels in s["groups"].items() if rel in rels), None)
    if group == "unsafe":
        raise Stop(f"{rel}: путь за пределы репо или через симлинк — не трогаю и не показываю")
    repo, new, base, frm, to = s["repo"], s["new"].get(rel), s["base"].get(rel), s["from"], s["to"]
    path = repo / rel
    project = path.read_bytes() if path.is_file() else None
    frm = s["base_version"].get(rel, frm)  # ждёт ответа — со своей версии
    change = f"== правка шаблона {frm} → {to}: {rel}\n"
    if group in ("skill_text", "own_changed", "merge"):
        out = change + unified(base, new, f"шаблон {frm}", f"шаблон {to}")
        if group != "skill_text":
            conflicts, merged = merge_file(base or b"", project, new)
            moved = carry(base or b"", project, new) if conflicts else None
            if not conflicts:
                out += "== ваш файл после: правка шаблона встаёт без конфликта\n" + unified(project, merged, "сейчас",
                                                                                            "после")
            elif moved is None:  # не текст для переноса (концы строк CRLF) — как раньше, с маркерами
                out += (f"== склейка: ваш файл станет таким (конфликтов: {conflicts} — не встаёт само, только "
                        "заменить шаблоном или оставить своё)\n" + unified(project, merged, "сейчас", "после склейки"))
            else:
                out += carried_text(project, moved, frm, to)
            lost = loss(project, new)
            if lost:
                out += f"== заменить шаблоном: пропадёт ваших строк: {lost['own']} из {lost['total']}\n"
        return out
    if group in ("update", "new", "new_occupied", "deleted", "unknown", "binary"):
        heads = {"update": "обновится молча", "new": "новый файл шаблона", "new_occupied": "ваш файл и файл шаблона",
                 "deleted": "вернётся из шаблона", "unknown": "ваш файл и новый шаблон (старой версии шаблона нет)",
                 "binary": "ваш файл и новый шаблон (склеить нельзя, правьте сами)"}
        return f"== {heads[group]}: {rel}\n" + unified(project, new, "сейчас", f"шаблон {to}")
    if group == "removed":
        return (f"== убрано из шаблона {to}, в проекте нетронуто — удалится: {rel}\n"
                + unified(project, None, "сейчас", "после удаления"))
    if group == "removed_edited":
        return (f"== убрано из шаблона {to}, у вас правлено или заполнено — остаётся вашим, sync его не удалит "
                f"(из манифеста уходит): {rel}\n" + unified(None, project, f"шаблон {to}: нет", "сейчас"))
    raise Stop(f"{rel}: нечего показать — группа {group or 'нет в описи'}")


def draft_root(root, dest):
    """Основа для «склеить вместе» (ревью 2026-09-30, находка 2) — в файл вне проекта: без учёта (`unknown`) —
    карта шаблона целиком, склейка (`merge`) — результат `git merge-file`, с конфликтом — с маркерами. Плюс
    строки человека, которых в шаблоне нет, — их агент переносит в основу."""
    s = survey_root(root)
    group, have, new = s["map"]["group"], s["have"], s["new"][ROOT_MAP]
    if group not in ("unknown", "merge"):
        raise Stop(f"карта корня: «склеить вместе» — только у unknown и merge, а она в группе {group}")
    dest = outside(dest, s["root"])
    known = set(new.decode("utf-8").splitlines())
    own = [line for line in have.decode("utf-8").splitlines() if line.strip() and line not in known]
    dest.parent.mkdir(parents=True, exist_ok=True)
    if group == "merge" and s["map_carried"] is not None:  # решение 2026-10-02: основа — карта человека
        moved = s["map_carried"]
        dest.write_bytes(moved["data"])
        return {"file": str(dest), "basis": "own", "conflicts": s["map"]["conflicts"], "moved": moved["moved"],
                "left": moved["left"], "own_lines": own}
    conflicts, data = (None, new) if group == "unknown" else merge_file(s["base_map"] or b"", have, new)
    dest.write_bytes(data)
    return {"file": str(dest), "basis": "template" if group == "unknown" else "merge", "conflicts": conflicts,
            "own_lines": own}


def diff_root(root, text=None):
    """Что показать по карте корня перед вопросом; `text` — карта, собранная с человеком: сейчас → она."""
    s = survey_root(root)
    group, have, new = s["map"]["group"], s["have"], s["new"][ROOT_MAP]
    if text is not None:
        return "== карта корня CLAUDE.md: так станет (собрана с вами)\n" + unified(
            have, Path(text).read_bytes(), "сейчас", "после")
    lost = s["map_loss"]
    tail = f"== заменить шаблоном: пропадёт ваших строк: {lost['own']} из {lost['total']}\n" if lost else ""
    if group == "merge":
        conflicts, merged = merge_file(s["base_map"] or b"", have, new)
        out = (f"== правка шаблона {s['map_version']} → {s['to']}: карта корня CLAUDE.md\n"
               + unified(s["base_map"], new, f"шаблон {s['map_version']}", f"шаблон {s['to']}"))
        if conflicts and s["map_carried"] is not None:
            return out + carried_text(have, s["map_carried"], s["map_version"], s["to"]) + tail
        note = "без конфликта" if not conflicts else (f"конфликтов: {conflicts} — не встаёт само: заменить "
                                                      "шаблоном, оставить своё или собрать вместе")
        head = "ваша карта после: правка шаблона встаёт без конфликта" if not conflicts else f"склейка ({note})"
        return out + f"== {head}\n" + unified(have, merged, "сейчас", "после") + tail
    heads = {"update": "обновится молча", "new": "новая из шаблона", "deleted": "вернётся из шаблона",
             "edited": "ваши правки (шаблон её не менял)",
             "unknown": "ваша карта и шаблон (учёта нет — чьи правки, не узнать)"}
    if group not in heads:
        raise Stop(f"карта корня: нечего показать — группа {group}")
    return (f"== карта корня CLAUDE.md — {heads[group]}\n" + unified(have, new, "сейчас", f"шаблон {s['to']}")
            + (tail if group == "unknown" else ""))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_plan = sub.add_parser("plan", help="опись: что sync сделает с файлами репо")
    p_plan.add_argument("repo")
    p_apply = sub.add_parser("apply", help="записать: молчаливую часть и решения человека; коммит — у скилла")
    p_apply.add_argument("repo")
    p_apply.add_argument("decisions", nargs="?", help="JSON с решениями человека")
    p_diff = sub.add_parser("diff", help="что показать человеку по файлу перед вопросом")
    p_diff.add_argument("repo")
    p_diff.add_argument("file")
    p_diff.add_argument("--text", help="файл, собранный с человеком: показать, каким станет")
    p_dr = sub.add_parser("draft", help="основа для «собрать вместе» по файлу репо — в файл вне проекта")
    p_dr.add_argument("repo")
    p_dr.add_argument("file")
    p_dr.add_argument("dest")
    for cmd, text in (("plan-root", "опись корня: разрешения, карта, .gitignore, учёт; ничего не пишет"),
                      ("apply-root", "записать в корень молчаливое и решения человека; коммит — у скилла")):
        p_root = sub.add_parser(cmd, help=text)
        p_root.add_argument("root")
        if cmd == "apply-root":
            p_root.add_argument("decisions", nargs="?", help="JSON с решениями человека по корню")
    p_draft = sub.add_parser("draft-root", help="основа для «склеить вместе» — в файл вне проекта")
    p_draft.add_argument("root")
    p_draft.add_argument("file")
    p_droot = sub.add_parser("diff-root", help="что показать по карте корня перед вопросом")
    p_droot.add_argument("root")
    p_droot.add_argument("--text", help="карта, собранная с человеком: показать, какой станет")
    args = parser.parse_args(argv)
    try:
        if args.cmd == "draft-root":
            print(json.dumps(draft_root(args.root, args.file), ensure_ascii=False, indent=2))
        if args.cmd == "diff-root":
            sys.stdout.write(diff_root(args.root, args.text))
        if args.cmd == "plan-root":
            print(json.dumps(plan_root(args.root), ensure_ascii=False, indent=2))
        if args.cmd == "apply-root":
            decisions = json.loads(Path(args.decisions).read_text(encoding="utf-8")) if args.decisions else {}
            print(json.dumps(apply_root(args.root, decisions), ensure_ascii=False, indent=2))
        if args.cmd == "plan":
            print(json.dumps(plan(args.repo), ensure_ascii=False, indent=2))
        if args.cmd == "diff":
            sys.stdout.write(diff(args.repo, args.file, args.text))
        if args.cmd == "draft":
            print(json.dumps(draft(args.repo, args.file, args.dest), ensure_ascii=False, indent=2))
        if args.cmd == "apply":
            decisions = json.loads(Path(args.decisions).read_text(encoding="utf-8")) if args.decisions else {}
            print(json.dumps(apply(args.repo, decisions), ensure_ascii=False, indent=2))
    except (Stop, qa_template.TemplateError) as e:
        print(e, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
