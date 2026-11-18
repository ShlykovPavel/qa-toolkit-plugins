#!/usr/bin/env python3
"""qa-init.py — механика `/qa:init`: опись папки, раскладка шаблонов, проверка результата.

Решения и сценарии — `docs/plugin/qa-init-draft.md` репо мастерской `qa-toolkit`. Здесь только то, что
проверяется тестом (`qa-toolkit/tests/test_qa_init.py`); интервью, паспорта, вопросы человеку и
коммиты — у скилла. Сейчас покрыт сценарий 1: пустая папка → два новых репо; из сценария 6 (уже
QA-проект) — опись: сводка репо по маркерам и места «— решим позже»; `apply` досоздаёт второй репо;
из сценария 3 (готовый ручник) — опись: настоящие папки вики и коллекции, старая обвязка с двойниками
в плагине, данные скиллов, своё, состояние git, другой агент, готовые пары переносов; из сценария 2 (готовые автотесты) — опись: паспорт и
строки «Охват тестирования», старая обвязка с двойниками (скиллы, агенты, хук, скрипты), данные скиллов
готовыми парами «откуда → куда», своё, записи settings, которые смотрят в обвязку.

    qa-init.py scan                 # опись текущей папки (корня) → JSON; git: root | repos | conflict
                                    #   (+ git_problem) — где будет git проекта; state: empty | occupied |
                                    #   project (в подпапках маркеры) | inside-repo (запуск из репо);
                                    #   adopt (в подпапке наш старый ручник или форк автотестов
                                    #   без маркера, found; missing_roles) |
                                    #   unmarked-repo (запуск из такого репо);
                                    #   у project — report_lines: строки про /qa:sync и отложенное
    qa-init.py apply <план.json>    # создать репо по подтверждённому плану; git — в выводе: root (один
                                    #   git в корне) | repos (свой git в каждой папке, как было)
    qa-init.py filled <репо> <файл>…  # скилл заполнил файлы шаблона → новый отпечаток, state filled
    qa-init.py refs <репо>          # принятый репо: строки своих .md и данных, уехавших в .qa/, со ссылками
                                    #   на перенесённое и чем заменить; журнал, страницы вики, отчёты и пробы
                                    #   лабораторий, `AGENTS.md` и `GEMINI.md` (инструкции другого
                                    #   агента) и обвязка, оставленная ему при «скрыть», — только счёт; report_lines — сводка по заменам,
                                    #   detail_lines — все строки
    qa-init.py refs <репо> --keep [<оставлено>…]
                                    # после ответа человека и правок: что он оставил — строки сводки
                                    #   целиком (group) или `файл:строка` — записать в манифест (refs_kept),
                                    #   verify их больше не считает; живая, которую не назвали, — отказ
                                    #   со списком для человека
    qa-init.py refs <репо> --apply <строка сводки | файл:строка>…
                                    # после «да» человека: в названном ровно `ref` → `replace` (где замена
                                    #   механическая: данные, относительный путь, скрипт → команда);
                                    #   applied — что поправил, manual — что осталось руками;
                                    #   без перечня — отказ: перечень даёт только ответ человека
    qa-init.py verify               # проверить маркеры, манифесты, settings в корне и репо, живые
                                    #   ссылки на перенесённое у принятых репо (кроме refs_kept);
                                    #   печатает версии плагинов каталога по папкам и числа по ссылкам
                                    #   принятых репо (было при приёме — refs_found от apply)
    qa-init.py root                 # готовый проект без карты корня: положить недостающие файлы шаблона
                                    #   корня по маркерам папок; готовые не трогает
    qa-init.py strip <папка>        # снять разметку слоёв, оставив все слои (песочница эвалов)

План (`apply`), JSON:
    {"product": "polygon",                     # короткое имя: a-z, 0-9, дефис
     "title": "Polygon",
     "catalog": {"source": "github", "repo": "<владелец>/<репо>", "ref": "<ветка>"}
             | {"source": "git", "url": "<адрес git>", "ref": "<ветка>"},
     "repos": [{"role": "kb", "dir": "polygon-kb"},
               {"role": "autotests", "dir": "polygon-autotests",
                "layers": ["frontend", "mobile"],        # API — ядро, есть всегда; список может быть пуст
                "frontend_lib": "selenium"}]}           # или playwright; только при frontend

Приём готового ручника (сценарий 3) — в `repos` вместо нового kb; переносы — пары описи как есть:
`archive_moves` при «В архив», `archive_own_skills` при «Свои скиллы — в архив», данные — `data_moves`
(человеку — строками `plan_lines` описи, как есть):
    {"role": "kb", "dir": "manual-shooting", "adopt": true,
     "paths": {"wiki": "shooting_wiki", "collection": "shooting_api_collection"},  # из описи, found
     "moves": [[".claude/skills/task-recheck", ".qa/archive/<дата>/.claude/skills/task-recheck"],
               [".claude/skills/task-recheck/project/card.md", ".qa/labs/task-recheck/card.md"]]}
Приём готовых автотестов (сценарий 2) — так же, со слоями вместо путей:
    {"role": "autotests", "dir": "fps", "adopt": true, "layers": ["mobile"],
     "moves": [[".claude/agents/test-writer.md", ".qa/archive/<дата>/.claude/agents/test-writer.md"],
               [".claude/skills/keys-mobile/project/card.md", ".qa/keys-mobile/docs/card.md"]]}
Репо должен быть узнан описью в той же роли, без маркера и с чистым git. Шаблон не копируется, своё не
трогается.
Переносы — только в `.qa/archive/`, `.qa/labs/` и `.qa/<скилл>/docs/`, `git mv`, остаются в
индексе; маркер, манифест и settings — вне индекса: скилл коммитит переносы отдельно от записи.
Settings сливаются: каталог, плагины, разрешения шаблона; разрешения и хуки, которые смотрят в
перенесённое, убираются — `apply` печатает их в `settings_dropped`. Данные, чей старый скилл остался на
месте, оставляют на старом пути ссылку на новый файл. `"hide_old": true` — «оставить и скрыть от
Claude» для другого агента: обвязку не переносят, старые скиллы с двойниками выключает `skillOverrides`
в `.claude/settings.local.json`, хук Claude уступает хуку плагина (что именно — `hide_old` описи);
`AGENTS.md`/`GEMINI.md`, что ссылками ведут на `CLAUDE.md`, отделяются: первая — копия его текста, другая —
ссылка на неё (`claude_md_links` описи). `AGENTS.md` и `GEMINI.md` не переносятся ни у какой роли.

Git (решение человека 2026-09-29): у нового проекта один git — в корне, своих `.git` у папок нет;
корень, уже ставший git (склонирован пустой репо — README, лицензия, свой `.gitignore` не мешают),
берётся как есть. Рядом с принятым репо со своей историей или в проект из двух git — `git init` в новой
папке, как было: историю склеивают руками. Корень — git, а в нём папка со своим `.git` — отказ (`conflict`).
Свой `.gitignore` корня не перезаписывается: недостающие строки шаблона дописываются в конец.

Корень (решение человека 2026-09-29: агент работает только из корня) — шаблон `templates/root/`: карта
`CLAUDE.md` (что где лежит, куда за чем, кого звать) и `.gitignore`. Куски ролей и слоёв, которых нет, режет та же
разметка «слой: <тег>» (теги — `kb`, `autotests`, `both` при обеих и слои автотестов), `{{…}}` — имена папок.
Готовый файл корня `apply` не перезаписывает (кроме карты прошлого `apply`, которую никто не правил: второй репо
дописывается в неё) и называет его в `root_kept`. В settings корня — ещё разрешения из settings папки
автотестов, пути правил — от корня, и правила корня из `templates/root/allow.json`. Учёт корня для `/qa:sync`
— `.qa/root.json`: версия плагина и отпечаток карты, отрисованной из шаблона (и когда в корне осталась своя).

Слои шаблона автотестов (решение человека 2026-09-25): карта файлов — `templates/autotests-layers.json`,
куски общих файлов размечены строками «слой: <тег>» … «/слой» в комментарии (`<!-- -->` или `#`).
Невыбранные файлы и куски в проект не попадают, разметка выбранных снимается.

Факты, на которых стоит механика (спайк 2026-09-25, `docs/plugin/spike-results.md`):
- `claude plugin install` не пишет источник каталога в settings проекта и переписывает файл
  целиком — поэтому источник и включение плагинов пишет этот скрипт, установку скилл зовёт после;
- репо внутри корня плагины корня не наследует — у корня и у каждого репо свои settings;
- включения в settings мало: установку `verify` сверяет по `claude plugin list --json` (полигон
  init-1, 2026-09-25: скилл пропустил установку в корне, а проверка settings этого не видела).

Коды возврата: 0 — готово; 1 — `verify` нашёл проблемы; 2 — план или `filled` не приняты, ничего не записано.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qa_template  # noqa: E402

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = PLUGIN_ROOT / "templates"
SCHEMA = 1
ROLES = {"kb": "qa-manual", "autotests": "qa-auto"}  # роль репо → плагин, который она включает
LAYERS = {"frontend", "mobile"}  # API — ядро шаблона, слоем не считается
FRONTEND_LIBS = {"selenium", "playwright"}
LAYER_MAP = TEMPLATES / "autotests-layers.json"
BLOCK = re.compile(r"^\s*(?:<!--|#)\s*(/?)слой:?\s*(\w*)\s*(?:-->)?\s*$")
JUNK = {"__pycache__", ".DS_Store", ".pytest_cache"}
ROOT_FILES = qa_template.ROOT_FILES  # шаблон корня: карта проекта и .gitignore
ROOT_RECORD = Path(".qa") / "root.json"  # учёт корня для /qa:sync: версия и отпечаток шаблонной карты
IGNORED_IN_ROOT = {".claude", ".git", ".qa", ".DS_Store", "plan.json", *ROOT_FILES}  # то, что не делает корень занятым
SLUG = re.compile(r"[a-z0-9][a-z0-9-]*")
# Склонированный с GitHub пустой репо: README, лицензия, .gitattributes — не занятость, если корень уже git
# (решение человека 2026-09-30: `/qa:init` берёт его git и ставит проект в него).
CLONE_FILES = re.compile(r"(readme|license|licence|copying)(\.\w+)?|\.gitattributes", re.I)
MARKER = Path(".qa") / "project.yaml"
LATER = "решим позже"  # так скилл пишет неизвестное в интервью — это и доспрашивается в сценарии 6
MANIFEST = Path(".qa") / "manifest.json"
SETTINGS = Path(".claude") / "settings.json"
FILLED = {SETTINGS.as_posix()}  # файлы шаблона, в которые apply делает подстановки (плюс размеченные)


class PlanError(Exception):
    pass


def plugin_version():
    return json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]


def catalog_name():
    """Имя каталога берётся из settings шаблона — оно одно на все проекты (спайк, находка 11)."""
    data = json.loads((TEMPLATES / "kb" / SETTINGS).read_text(encoding="utf-8"))
    (name,) = data["extraKnownMarketplaces"]
    return name


def has_placeholder(value):
    return "<" in json.dumps(value, ensure_ascii=False)


def version_key(version):
    return tuple(int(x) if x.isdigit() else 0 for x in version.split("."))


def dump_json(data):
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


# --- опись ---------------------------------------------------------------------------------

def git_mode(root, ready):
    """Где git проекта: `root` — один в корне, `repos` — свой у каждой папки (рядом готовые папки со своим
    .git, корень не git). Корень — git, а у готовой папки свой .git — PlanError: склейка истории — руками."""
    nested = [p.name for p in ready if (p / ".git").exists()]
    if not (root / ".git").exists():
        return "repos" if nested else "root"
    if nested:
        raise PlanError(f"корень — git-репо, а у {', '.join(nested)} свой .git: в один git проекта без склейки "
                        f"истории не лечь, склейку делают руками — перенеси историю в git корня или начни в "
                        f"новой папке-корне без .git")
    return "root"


def git_field(root, ready):
    try:
        return {"git": git_mode(root, ready)}
    except PlanError as e:
        return {"git": "conflict", "git_problem": str(e)}


def scan(root):
    """Опись: пустая, занятая, уже QA-проект (в подпапках маркеры), готовое к приёму (в подпапках наш
    старый репо без маркера) или запуск изнутри репо — с маркером или без."""
    if (root / MARKER).is_file():
        return {"root": str(root), "state": "inside-repo", "root_hint": str(root.parent),
                "repo": repo_summary(root)}
    own_repo = recognize(root)
    if own_repo:
        return {"root": str(root), "state": "unmarked-repo", "root_hint": str(root.parent), "repo": own_repo}
    entries, repos = [], []
    clone = (root / ".git").exists()
    for p in sorted(root.iterdir()):
        if p.name in IGNORED_IN_ROOT or (clone and p.is_file() and CLONE_FILES.fullmatch(p.name)):
            continue
        if p.is_dir() and (p / MARKER).is_file():
            repos.append(repo_summary(p))
            continue
        entries.append({"path": p.name, "kind": "dir" if p.is_dir() else "file"})
    if repos:
        roles = {r["role"] for r in repos}
        return {"root": str(root), "state": "project", "plugin_version": plugin_version(), "repos": repos,
                "missing_roles": [r for r in ROLES if r not in roles], "entries": entries,
                "report_lines": report_lines(repos),
                **git_field(root, [root / r["dir"] for r in repos])}
    found = [f for f in (recognize(root / e["path"]) for e in entries if e["kind"] == "dir") if f]
    if found:
        roles = {f["role"] for f in found}
        return {"root": str(root), "state": "adopt", "plugin_version": plugin_version(), "found": found,
                "missing_roles": [r for r in ROLES if r not in roles], "entries": entries,
                **git_field(root, [root / f["dir"] for f in found])}
    return {"root": str(root), "state": "occupied" if entries else "empty", "entries": entries,
            **git_field(root, [])}


# Скиллы и агенты каталога — двойники старой обвязки. Зашиты сюда: из кэша установки соседние плагины
# не видны (у каждого своя папка версии). Сторож — `test_plugin_twins_match_toolkit`.
PLUGIN_TWINS = {
    "skills": {name: f"{plugin}:{name}" for plugin, names in {
        "qa": ["hello", "init", "kb-ingest", "kb-lint", "kb-query", "next", "progress", "rules", "setup-machine",
               "skill-lab", "sync", "task"],
        "qa-manual": ["task-recheck", "tracker-filing", "ui-bug-sweep"],
        "qa-auto": ["api-clients", "api-suite", "api-tests", "bug-report", "frontend-tests", "keys-admin",
                    "keys-mobile", "mobile-tests", "review-tests", "setup-fork", "test-flow"],
    }.items() for name in names},
    "agents": {name: f"{plugin}:{name}" for plugin, names in {
        "qa-manual": ["skeptic-evidence"],
        "qa-auto": ["app-keys-editor", "test-fixer", "test-reviewer", "test-spec-writer", "test-writer"],
    }.items() for name in names},
}
OLD_ALIASES = [".preflight-ok"]  # следы старой обвязки в корне репо
# Правила `rules/` старого ручника разъехались справочниками по скиллам плагина (журнал 2026-09-22);
# `toolchain.md` устарел и в плагин не ехал. Файл не отсюда — своё правило проекта.
RULE_TWINS = {
    "assistants.md": "qa:rules", "search-and-api.md": "qa:rules", "wiki-and-collection.md": "qa:rules",
    "task-verification.md": "qa-manual:task-recheck", "frontend.md": "qa-manual:ui-bug-sweep",
    "tracker.md": "qa-manual:tracker-filing", "lab-journal.md": "qa:skill-lab", "toolchain.md": None,
}
LAB_TITLE = re.compile(r"^#\s*Лаборатория скилла `([\w-]+)`")


def recognize(repo):
    """Наш старый репо без маркера: ручник (сценарий 3) или автотесты (сценарий 2). Не узнан — None."""
    return recognize_kb(repo) or recognize_autotests(repo)


def recognize_kb(repo):
    """Наш старый ручник без маркера (сценарий 3): где вики и коллекция, что из старой обвязки спорит с
    плагином, где данные скиллов, что своё. Не узнан — None."""
    signs = [s for s in ("project-passport.md", "site-notes.md", ".claude/skills/task-recheck")
             if (repo / s).exists()]
    if "project-passport.md" not in signs and ".claude/skills/task-recheck" not in signs:
        return None
    children = sorted(p for p in repo.iterdir() if p.name not in JUNK and p.name != ".git")
    wiki = [p.name for p in children if p.is_dir() and (p / "index.md").is_file() and (p / "raw").is_dir()]
    collection = []
    for p in children:
        if p.is_dir() and (p / "bruno.json").is_file():
            collection.append({"dir": p.name, "format": "bruno"})
        elif p.is_dir() and any(p.glob("*.postman_collection.json")):
            collection.append({"dir": p.name, "format": "postman"})
    binding, data = [], []
    for kind in ("skills", "agents"):
        folder = repo / ".claude" / kind
        for p in sorted(folder.iterdir()) if folder.is_dir() else []:
            if p.name in JUNK:
                continue
            name = p.name if kind == "skills" else p.stem
            binding.append({"path": p.relative_to(repo).as_posix(), "twin": PLUGIN_TWINS[kind].get(name)})
            if kind == "skills":
                data += [f.relative_to(repo).as_posix() for f in sorted((p / "project").rglob("*"))
                         if f.is_file() and f.name != "TEMPLATE.md" and f.name not in JUNK]
    for extra in (".claude/hooks", ".claude/commands", ".agents", *OLD_ALIASES):
        if (repo / extra).exists() or (repo / extra).is_symlink():
            binding.append({"path": extra, "twin": None})
    other_agent = [t for t in (".agents", *OTHER_AGENT_DOCS) if (repo / t).exists() or (repo / t).is_symlink()]
    own = []
    for p in sorted((repo / "rules").glob("*.md")):
        if p.name in RULE_TWINS:
            binding.append({"path": f"rules/{p.name}", "twin": RULE_TWINS[p.name]})
        else:
            own.append(f"rules/{p.name}")
    labs = []
    for p in children:
        readme = p / "README.md"
        title = LAB_TITLE.match(readme.read_text(encoding="utf-8")) if p.is_dir() and readme.is_file() else None
        if title:
            labs.append({"path": p.name, "skill": title.group(1)})
    known = (template_names("kb") | set(wiki) | {c["dir"] for c in collection} | {"rules", *OLD_ALIASES, *other_agent}
             | {lab["path"] for lab in labs})
    own = sorted(own + [p.name for p in children if p.name not in known])
    # Пары и строки плана — готовыми, как у автотестов (находки (а4), (г2)): карточки скиллов и лаборатория
    # целиком — туда, где их ищет плагин. Хука, которому уступать, у старого ручника нет.
    day = f"{ARCHIVE}{datetime.date.today().isoformat()}"
    mine = [b["path"] for b in binding if not b["twin"] and b["path"].startswith(".claude/skills/")]
    archive = sorted([b["path"], f"{day}/{b['path']}"] for b in binding if b["path"] not in mine)
    moves = [[f, f".qa/labs/{f.split('/')[2]}/{f.split('/', 4)[4]}"] for f in data]
    moves += [[lab["path"], f".qa/labs/{lab['skill']}/{lab['path']}"] for lab in labs]
    hide_old = {"skills": [b["path"].rsplit("/", 1)[1] for b in binding
                           if b["twin"] and b["path"].startswith(".claude/skills/")], "settings_drop": [],
                "claude_md_links": claude_md_links(repo)}
    return {"dir": repo.name, "role": "kb", "signs": signs, "wiki": wiki, "collection": collection,
            "old_binding": binding, "other_agent": other_agent, "skill_data": data, "labs": labs,
            "hide_old": hide_old, "archive_moves": archive, "archive_own_skills": [[p, f"{day}/{p}"] for p in mine],
            "data_moves": sorted(moves), "own": own, "git": git_state(repo),
            "plan_lines": plan_lines(repo, day, [a for a, _ in archive], mine, moves)}


# Скрипты и хук старого форка автотестов, переехавшие в `bin/` и `hooks/` плагинов; их тесты
# (`scripts/test_<имя>`) уехали в мастерскую вместе с ними. Сторож — `test_script_and_hook_twins_exist_in_toolkit`.
SCRIPT_TWINS = {name: plugin for plugin, names in {
    "qa": ["preflight.py"],
    "qa-auto": ["api_client_check.py", "coverage_check.py", "dump_dom.py", "dump_ui_tree.py",
                "mobile_keys_audit.py", "openapi_slice.py", "spec_loader.py"],
}.items() for name in names}
HOOK_TWINS = {"check_no_hardcode.py": "qa-auto"}
# Инструкции других агентов остаются при любом выборе: их читают многие харнессы, Claude они не мешают;
# `.agents` — их обвязка, архив старых скиллов её ломает (решения человека 2026-09-27).
OTHER_AGENT_DOCS = ("AGENTS.md", "GEMINI.md")


def claude_md_links(repo):
    """Инструкции другого агента, которые ссылками ведут на `CLAUDE.md` (Shooting): правка `CLAUDE.md` под
    плагин меняла бы и их — при «оставить и скрыть» `apply` их отделяет (решение человека 2026-09-29)."""
    claude = repo / "CLAUDE.md"
    return [d for d in OTHER_AGENT_DOCS if claude.is_file() and (repo / d).is_symlink()
            and (repo / d).resolve() == claude.resolve()]


def split_claude_md_links(repo):
    """Вариант (б): первая инструкция — копия нынешнего `CLAUDE.md` байт в байт, остальные — ссылки на неё
    (как в FPS: `GEMINI.md` → `AGENTS.md`). Другой агент читает тот же текст; в индексе — с переносами."""
    links = claude_md_links(repo)
    if not links:
        return {}
    first, text = links[0], (repo / "CLAUDE.md").read_bytes()
    (repo / first).unlink()
    (repo / first).write_bytes(text)
    for doc in links[1:]:
        (repo / doc).unlink()
        (repo / doc).symlink_to(first)
    subprocess.run(["git", "add", *links], cwd=repo, check=True, capture_output=True)
    return {first: "копия CLAUDE.md", **{doc: f"→ {first}" for doc in links[1:]}}
ALIAS_SCRIPTS = ("antigravity_",)  # скрипты под Antigravity: их зовёт `.agents/hooks.json` (решение человека 2026-09-27)
AUTOTESTS_CORE = ("src/http_methods.py", "Tests/conftest.py")
PASSPORT = "docs/project-profile.md"
# Куда плагин кладёт данные скилла (журнал 2026-09-21, 2026-09-22): рабочие документы — `.qa/<скилл>/docs/`
# (только у скиллов из WORKING_DOCS), остальное из `project/` и лаборатория — `.qa/labs/<скилл>/`. Бланки
# лаборатории есть в плагине — это не данные. Сторож — `test_lab_blanks_match_toolkit`.
WORKING_DOCS = ("keys-mobile",)
LAB_BLANKS = ("README.md", "runs/TEMPLATE.md")
OWN_BY_FILE = ("docs", "scripts")  # папки шаблона, где своё лежит вперемешку с файлами шаблона


def recognize_autotests(repo):
    """Наш старый форк автотестов без маркера (сценарий 2): ядро шаблона плюс паспорт или старая обвязка.
    Что спорит с плагином, куда уезжают данные скиллов, что своё, какие записи settings смотрят в
    обвязку. Не узнан — None."""
    if not all((repo / s).is_file() for s in AUTOTESTS_CORE):
        return None
    binding, moves = [], []
    for kind in ("skills", "agents"):
        folder = repo / ".claude" / kind
        for p in sorted(folder.iterdir()) if folder.is_dir() else []:
            if p.name in JUNK:
                continue
            binding.append({"path": p.relative_to(repo).as_posix(),
                            "twin": PLUGIN_TWINS[kind].get(p.name if kind == "skills" else p.stem)})
            if kind == "skills":
                moves += skill_data_moves(repo, p)
    hooks = repo / ".claude" / "hooks"
    for p in sorted(hooks.iterdir()) if hooks.is_dir() else []:
        if p.name not in JUNK:
            twin = HOOK_TWINS.get(p.name)
            binding.append({"path": p.relative_to(repo).as_posix(), "twin": twin and f"{twin}:{p.name}"})
    for extra in (".claude/commands", ".claude/evals", ".agents", ".preflight-ok"):
        if (repo / extra).exists() or (repo / extra).is_symlink():
            binding.append({"path": extra, "twin": None})
    other_agent = [t for t in (".agents", *OTHER_AGENT_DOCS) if (repo / t).exists() or (repo / t).is_symlink()]
    for p in sorted((repo / "scripts").glob("*.py")):
        name = p.name.removeprefix("test_")
        plugin = SCRIPT_TWINS.get(name) or HOOK_TWINS.get(name)
        if plugin:
            binding.append({"path": f"scripts/{p.name}", "twin": f"{plugin}:{name}"})
        elif name.startswith(ALIAS_SCRIPTS):  # копия хука под другой харнесс — уезжает вместе с `.agents`
            binding.append({"path": f"scripts/{p.name}", "twin": None})
    if not (repo / PASSPORT).is_file() and not binding:
        return None  # голая копия шаблона — не наш настроенный форк
    taken = {b["path"] for b in binding} | {PASSPORT, *other_agent}
    template = template_names("autotests")
    own = [p.name for p in sorted(repo.iterdir())
           if p.name not in template | taken | JUNK | {".git"}]
    for folder in OWN_BY_FILE:
        ours = {p.name for p in (TEMPLATES / "autotests" / folder).iterdir()}
        own += [f"{folder}/{p.name}" for p in sorted((repo / folder).iterdir()) if (repo / folder).is_dir()
                and p.name not in ours | JUNK and f"{folder}/{p.name}" not in taken]
    refs = settings_refs(repo, binding)
    hooks = {b["path"] for b in binding if b["twin"] and b["path"].startswith(".claude/hooks/")}
    hide_old = {"skills": [b["path"].rsplit("/", 1)[1] for b in binding
                           if b["twin"] and b["path"].startswith(".claude/skills/")],
                "settings_drop": [r["entry"] for r in refs if r["path"] in hooks],
                "claude_md_links": claude_md_links(repo)}
    # «В архив» формы 9 — готовыми парами: собирая их сам, агент на полигонах init-12 и init-13 то уносил
    # `.agents` и `scripts/antigravity_*`, то оставлял (находка (а4)). Свой скилл без двойника — своими
    # парами: его судьбу решает вопрос «Свои скиллы». `AGENTS.md` и `GEMINI.md` в обвязку не входят.
    day = f"{ARCHIVE}{datetime.date.today().isoformat()}"
    mine = [b["path"] for b in binding if not b["twin"] and b["path"].startswith(".claude/skills/")]
    archive = sorted([b["path"], f"{day}/{b['path']}"] for b in binding if b["path"] not in mine)
    return {"dir": repo.name, "role": "autotests", "passport": PASSPORT if (repo / PASSPORT).is_file() else None,
            "coverage": passport_coverage(repo / PASSPORT), "old_binding": binding, "other_agent": other_agent,
            "hide_old": hide_old, "archive_moves": archive, "archive_own_skills": [[p, f"{day}/{p}"] for p in mine],
            "data_moves": sorted(moves), "own": sorted(own), "settings_refs": refs, "git": git_state(repo),
            "plan_lines": plan_lines(repo, day, [a for a, _ in archive], mine, moves)}


BINDING_KINDS = (  # виды обвязки для строки плана: первое совпадение по началу пути
    ("скиллы", (".claude/skills/",)), ("агенты", (".claude/agents/",)), ("правила", ("rules/",)),
    ("хук", (".claude/hooks/",)),
    ("обвязка другого агента", (".agents", *(f"scripts/{p}" for a in ALIAS_SCRIPTS for p in (a, f"test_{a}")))),
    ("скрипты и их тесты", ("scripts/",)), ("харнесс эвалов", (".claude/evals",)), ("прочее", ("",)))
KINDS_SHOWN = ("скиллы", "агенты", "правила", "хук", "скрипты и их тесты", "обвязка другого агента", "харнесс эвалов", "прочее")


def plan_lines(repo, day, archive, mine, data):
    """Строки «Переношу» плана — готовыми. Находка (г2) `init-16`: агент считал сам — «31 файл + 30 файлов»
    при парах 32 + 32, в отчёте «32 файла» при 257 файлах в коммите. Файлы данных — только в данных: в архив
    со скиллом они не едут. Данные бывают папкой (лаборатория ручника) — считаются её файлы."""
    leaving = {src for src, _ in data}

    def files(path):
        p = repo / path
        if p.is_symlink() or p.is_file():
            return int(path not in leaving)
        return sum(1 for f in p.rglob("*") if (f.is_symlink() or f.is_file()) and not JUNK.intersection(f.parts)
                   and f.relative_to(repo).as_posix() not in leaving)

    kinds = {}
    for path in archive:
        kind = next(k for k, starts in BINDING_KINDS if path.startswith(starts))
        kinds[kind] = kinds.get(kind, 0) + 1
    by_kind = ", ".join(f"{k} — {kinds[k]}" for k in KINDS_SHOWN if k in kinds)
    per_skill = {}
    for src, dst in data:  # `.qa/labs/<скилл>/…` или `.qa/<скилл>/docs/…`
        skill = re.match(r"\.qa/(?:labs/)?([^/]+)/", dst).group(1)
        per_skill[skill] = per_skill.get(skill, 0) + (files(src) if (repo / src).is_dir() else 1)
    lines = {"archive": f"в архив `{day}/`: мест — {len(archive)}, файлов в них — {sum(map(files, archive))} ({by_kind})"}
    if mine:
        names = ", ".join(f"`{p.rsplit('/', 1)[1]}`" for p in mine)
        lines["archive_own_skills"] = (f"свои скиллы в архив `{day}/`: {names}, файлов в них — "
                                       f"{sum(map(files, mine))}")
    if data:
        lines["data"] = f"данные скиллов в `.qa/`: файлов — {sum(per_skill.values())} (" + ", ".join(
            f"{s} — {n}" for s, n in sorted(per_skill.items())) + ")"
    return lines


def skill_data_moves(repo, skill):
    """Пары «откуда → куда» для данных скилла из его папки: карточки и уроки из `project/`, лаборатория."""
    name, moves = skill.name, []
    for kind in ("project", "lab"):
        for f in sorted((skill / kind).rglob("*")):
            rel = f.relative_to(skill / kind).as_posix()
            if not f.is_file() or JUNK.intersection(f.parts) or f.name == "TEMPLATE.md" and kind == "project":
                continue
            if kind == "lab" and rel in LAB_BLANKS:
                continue
            if kind == "project" and rel != "lessons.md" and name in WORKING_DOCS:
                dst = f".qa/{name}/docs/{rel}"
            else:
                dst = f".qa/labs/{name}/{rel}"
            moves.append([f.relative_to(repo).as_posix(), dst])
    return moves


def passport_coverage(path):
    """Первая фраза каждой строки «Охват тестирования» паспорта — подсказка к вопросу о слоях."""
    if not path.is_file():
        return []
    section = re.search(r"^## Охват тестирования\n(.*?)(?=^#|\Z)", path.read_text(encoding="utf-8"), re.M | re.S)
    items = []
    for line in section.group(1).splitlines() if section else []:
        if line.startswith("- "):
            items.append(line[2:].strip())
        elif line.startswith(" ") and line.strip() and items:
            items[-1] += " " + line.strip()
    return [(re.match(r".+?\.(?=\s|$)", item) or re.match(r".{1,160}", item)).group(0) for item in items]


def settings_refs(repo, binding):
    """Разрешения и команды хуков settings репо, которые смотрят в старую обвязку."""
    try:
        data = json.loads((repo / SETTINGS).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    entries = list(data.get("permissions", {}).get("allow", []))
    entries += [h.get("command", "") for groups in data.get("hooks", {}).values()
                for group in groups for h in group.get("hooks", [])]
    refs = []
    for entry in entries:
        for b in binding:
            if mentions(entry, b["path"]):
                refs.append({"entry": entry, "path": b["path"]})
                break
    return refs


def template_names(role):
    return {p.name for p in (TEMPLATES / role).iterdir() if p.name not in JUNK}


def git_state(repo):
    if not (repo / ".git").exists():
        return None
    def git(*args):
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True).stdout.strip()
    return {"branch": git("rev-parse", "--abbrev-ref", "HEAD"), "dirty": bool(git("status", "--porcelain")),
            "origin": bool(git("remote", "get-url", "origin"))}


def repo_summary(repo):
    """Маркер репо плюс места «— решим позже» в файлах шаблона — что можно доспросить (сценарий 6)."""
    marker = read_marker(repo / MARKER)
    summary = {"dir": repo.name, **{k: marker[k] for k in
               ("role", "product", "title", "plugin_version", "sibling") if k in marker}}
    if "layers" in marker:
        summary["layers"] = [x.strip() for x in marker["layers"].strip("[]").split(",") if x.strip()]
    if "frontend_lib" in marker:
        summary["frontend_lib"] = marker["frontend_lib"]
    summary["template_behind"] = version_key(marker.get("plugin_version", "0")) < version_key(plugin_version())
    try:
        files = json.loads((repo / MANIFEST).read_text(encoding="utf-8"))["files"]
    except (OSError, ValueError, KeyError):
        files = {}
    later = []
    for rel in sorted(files):
        if not rel.endswith(".md") or not (repo / rel).is_file():
            continue
        for n, line in enumerate((repo / rel).read_text(encoding="utf-8").splitlines(), 1):
            if LATER in line:
                later.append({"file": rel, "line": n, "text": line.strip()})
    summary["later"] = later
    return summary


def report_lines(repos):
    """Готовые строки для сводки и отчёта — скилл переписывает их как есть.

    Собирая их сам, агент путал версии шаблона и плагина (полигон init-8) и расходился в счёте
    отложенного со списком (init-6, init-8): число из описи, места — по памяти."""
    lines = [f"{r['dir']}: шаблон {r.get('plugin_version', '?')}, плагин {plugin_version()} — файлы "
             "проекта обновит `/qa:sync`, её пока нет; сейчас не трогаю"
             for r in repos if r["template_behind"]]
    later = [f"- {r['dir']}/{place['file']}:{place['line']} — {place['text']}"
             for r in repos for place in r["later"]]
    return lines + [f"Отложено («— {LATER}») — мест: {len(later)}"] + later


# --- план ----------------------------------------------------------------------------------

def check_plan(plan, root):
    product = plan.get("product", "")
    if not SLUG.fullmatch(product):
        raise PlanError(f"product {product!r}: нужно короткое имя из a-z, 0-9 и дефиса")
    if not plan.get("title"):
        raise PlanError("title пуст")
    catalog = plan.get("catalog") or {}
    need = {"github": ("repo", "ref"), "git": ("url", "ref")}.get(catalog.get("source"))
    if need is None:
        raise PlanError(f"catalog.source {catalog.get('source')!r}: бывает github или git")
    missing = [k for k in need if not catalog.get(k)]
    if missing:
        raise PlanError(f"catalog: нет {', '.join(missing)}")
    if has_placeholder(catalog):
        raise PlanError("catalog: в источнике осталась заглушка <…>")
    repos = plan.get("repos") or []
    if not repos:
        raise PlanError("repos пуст")
    roles = [r.get("role") for r in repos]
    for r in repos:
        if r.get("role") not in ROLES:
            raise PlanError(f"role {r.get('role')!r}: бывает kb или autotests")
        if not r.get("dir") or "/" in r["dir"] or r["dir"].startswith("."):
            raise PlanError(f"dir {r.get('dir')!r}: имя папки внутри корня")
        if r["role"] == "autotests":
            layers = r.get("layers")
            if not isinstance(layers, list) or not set(layers) <= LAYERS:
                raise PlanError(f"layers {layers!r}: список из {sorted(LAYERS)} (API есть всегда)")
            lib = r.get("frontend_lib")
            if "frontend" in layers and lib not in FRONTEND_LIBS:
                raise PlanError(f"frontend_lib {lib!r}: при фронте нужна одна из {sorted(FRONTEND_LIBS)}")
            if "frontend" not in layers and lib is not None:
                raise PlanError("frontend_lib без слоя frontend")
        if r.get("adopt"):
            check_adopt(r, root)
    if len(set(roles)) != len(roles):
        raise PlanError("два репо с одной ролью")
    busy = [r["dir"] for r in repos if not r.get("adopt")
            and (root / r["dir"]).exists() and any((root / r["dir"]).iterdir())]
    if busy:
        raise PlanError(f"папка уже занята: {', '.join(busy)} — чужое не перезаписываем")
    check_existing(plan, root, roles)


PATH_KEYS = {"wiki": "wiki", "collection": "api_collection", "collection_format": "bruno"}  # как в qa-paths
ARCHIVE = ".qa/archive/"
MOVE_TARGETS = re.compile(r"\.qa/(archive|labs|[\w-]+/docs)/")  # рабочие документы скилла — .qa/<скилл>/docs/


def check_adopt(repo, root):
    """Готовый репо принимается как есть (сценарии 3 и 2): узнан описью в той же роли, без маркера, git
    чистый — переносы и запись скилл коммитит отдельно, чужие незакоммиченные правки к ним не примешать."""
    dest, name = root / repo["dir"], repo["dir"]
    if (dest / MARKER).exists():
        raise PlanError(f"{name}: уже есть маркер {MARKER.as_posix()} — это готовый проект, не приём")
    known = recognize(dest) if dest.is_dir() else None
    if known is None:
        raise PlanError(f"{name}: не узнан как наш ручник или форк автотестов — принимать нечего")
    if known["role"] != repo["role"]:
        raise PlanError(f"{name}: узнан как {known['role']}, а в плане {repo['role']}")
    if not isinstance(repo.get("hide_old", False), bool):
        raise PlanError(f"{name}: hide_old — true или false")
    git = git_state(dest)
    if git is None:
        raise PlanError(f"{name}: не git-репо")
    if git["dirty"]:
        raise PlanError(f"{name}: есть незакоммиченное — пусть человек сначала закоммитит своё")
    for key, value in (repo.get("paths") or {}).items():
        if key not in PATH_KEYS:
            raise PlanError(f"paths: неизвестный ключ {key!r}, бывают {', '.join(PATH_KEYS)}")
        if key == "collection_format":
            if value not in ("bruno", "postman"):
                raise PlanError(f"paths.collection_format {value!r}: bruno или postman")
        elif "/" in value or not (dest / value).is_dir():
            raise PlanError(f"paths.{key} {value!r}: нет такой папки в {name}")
    targets = set()
    for src, dst in repo.get("moves") or []:
        s, d = Path(src), Path(dst)
        if s.is_absolute() or ".." in s.parts or s.parts[0] in (".git", ".qa"):
            raise PlanError(f"перенос {src}: .git, .qa и пути наружу не переносим")
        if src in OTHER_AGENT_DOCS:
            raise PlanError(f"перенос {src}: инструкции других агентов остаются при любом выборе")
        if not (dest / s).exists() and not (dest / s).is_symlink():
            raise PlanError(f"перенос {src}: в {name} такого нет")
        if d.is_absolute() or ".." in d.parts:
            raise PlanError(f"перенос в {dst}: путь без .. и не абсолютный")
        if not MOVE_TARGETS.match(dst):
            raise PlanError(f"перенос в {dst}: только в .qa/archive/, .qa/labs/ или .qa/<скилл>/docs/")
        if (dest / d).exists() or dst in targets:
            raise PlanError(f"перенос в {dst}: туда уже переносится или лежит другое — дважды не кладём")
        targets.add(dst)


def existing_repos(root):
    """Репо готового проекта в корне: папка → маркер."""
    return {p: read_marker(p / MARKER) for p in sorted(root.iterdir())
            if p.is_dir() and (p / MARKER).is_file()}


def check_existing(plan, root, roles):
    """Второй репо в готовый проект (сценарий 6): тот же продукт, название и каталог, роль свободна."""
    for repo, marker in existing_repos(root).items():
        for key in ("product", "title"):
            if marker.get(key) != plan[key]:
                raise PlanError(f"{repo.name}: {key} {marker.get(key)!r}, а в плане {plan[key]!r} — "
                                f"второй репо досоздаётся для того же продукта")
        if marker.get("role") in roles:
            raise PlanError(f"роль {marker['role']} уже есть — {repo.name}")
        try:
            source = json.loads((repo / SETTINGS).read_text(encoding="utf-8"))[
                "extraKnownMarketplaces"][catalog_name()]["source"]
        except (OSError, ValueError, KeyError):
            source = None
        if source != plan["catalog"]:
            raise PlanError(f"{repo.name}: catalog {source!r}, а в плане {plan['catalog']!r}")


# --- apply ---------------------------------------------------------------------------------

def active_tags(repo):
    """Теги слоёв, которые остаются в проекте; None — роль без слоёв (kb)."""
    if repo["role"] != "autotests":
        return None
    layers = set(repo["layers"])
    tags = set(layers)
    if "frontend" in layers:
        tags.add(repo["frontend_lib"])
    if layers:
        tags.add("ui")
    return tags


def load_layer_map():
    data = json.loads(LAYER_MAP.read_text(encoding="utf-8"))
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
                raise PlanError(f"шаблон {where}:{n}: /слой без открытия")
            open_tag, keep = None, True
        else:
            if open_tag is not None:
                raise PlanError(f"шаблон {where}:{n}: блок внутри блока «{open_tag}»")
            open_tag, keep = m.group(2), m.group(2) in tags
    if open_tag is not None:
        raise PlanError(f"шаблон {where}: блок «{open_tag}» не закрыт")
    return "".join(out) if marked else None


def copy_template(repo, dest):
    """Копирует шаблон роли; возвращает пути файлов, в которых вырезаны куски слоёв."""
    src = TEMPLATES / repo["role"]
    tags = active_tags(repo)
    layer_map = load_layer_map() if tags is not None else {}
    filled = set()
    for p in sorted(src.rglob("*")):
        rel = p.relative_to(src)
        if JUNK.intersection(rel.parts) or not p.is_file():
            continue
        key = rel.as_posix()
        if tags is not None and not file_tags(key, layer_map) <= tags:
            continue
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest / rel)
        if tags is None:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        cut = cut_blocks(text, tags, key)
        if cut is not None:
            (dest / rel).write_text(cut, encoding="utf-8")
            filled.add(key)
    return filled


def fill_settings(path, catalog, tags):
    data = json.loads(path.read_text(encoding="utf-8"))
    data["extraKnownMarketplaces"][catalog_name()]["source"] = catalog
    allow = data.get("permissions", {}).get("allow")
    if allow is not None and tags is not None and "frontend" not in tags:
        # JSON без комментариев — разметку слоя сюда не поставить, режем по имени
        data["permissions"]["allow"] = [a for a in allow if a != "mcp__playwright"]
    path.write_text(dump_json(data), encoding="utf-8")


def write_marker(dest, plan, repo, sibling, created):
    paths = {k: v for k, v in (repo.get("paths") or {}).items() if v != PATH_KEYS[k]}  # только отличия
    lines = [
        f"schema: {SCHEMA}",
        f"role: {repo['role']}",
        f"product: {plan['product']}",
        f"title: {plan['title']}",
        f"origin: {'adopted' if repo.get('adopt') else 'new'}",
        f"template: {repo['role']}",
        f"plugin_version: {plugin_version()}",
        f"created: {created}",
        f"sibling: {sibling or 'none'}",
    ]
    if repo["role"] == "autotests":
        layers = ["api"] + [layer for layer in ("frontend", "mobile") if layer in repo["layers"]]
        lines.append(f"layers: [{', '.join(layers)}]")
        if repo.get("frontend_lib"):
            lines.append(f"frontend_lib: {repo['frontend_lib']}")
        lines.append("framework: own")
    if paths:
        lines += ["paths:"] + [f"  {k}: {v}" for k, v in paths.items()]
    (dest / MARKER).parent.mkdir(parents=True, exist_ok=True)
    (dest / MARKER).write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_manifest(dest, role, created, filled):
    files = {}
    for p in sorted(dest.rglob("*")):
        rel = p.relative_to(dest)
        if not p.is_file() or rel.parts[0] in (".git", ".qa"):
            continue
        key = rel.as_posix()
        files[key] = {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                      "state": "filled" if key in FILLED | filled else "issued"}
    manifest = {"plugin_version": plugin_version(), "template": role, "created": created, "files": files}
    (dest / MANIFEST).write_text(dump_json(manifest), encoding="utf-8")


def root_rule(rule, folder):
    return qa_template.root_rule(rule, folder)


def merge_root_settings(root, catalog, repos):
    """Дописывает в settings корня источник каталога, плагины и разрешения автотестов с путями от корня: агент
    работает из корня, а settings папки оттуда не действуют (спайк `mono-1`). Разрешения берутся из settings
    папки, как их записал `apply`: у нового репо — шаблона под слои, у принятого — после слияния, без
    убранного. Чужие ключи и их порядок — как были."""
    path = root / SETTINGS
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    name = catalog_name()
    markets = data.setdefault("extraKnownMarketplaces", {})
    markets[name] = {"source": catalog, "autoUpdate": True}
    plugins = data.setdefault("enabledPlugins", {})
    for plugin in ["qa"] + [ROLES[r["role"]] for r in repos]:
        plugins.setdefault(f"{plugin}@{name}", True)
    merge_root_permissions(data, root, repos)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_json(data), encoding="utf-8")


def root_permissions(root, repos):
    """Разрешения корня: автотестов — из settings их папки с путями от корня; сверх них — из шаблона корня
    (`root/allow.json`): при базе знаний `qa-paths` (карта корня зовёт `qa-paths wiki`), при обеих ролях
    `qa-kb-slice` (скиллы автотестов берут срез вики для тест-спеки)."""
    rules = []
    for repo in repos:
        if repo["role"] == "autotests":
            try:
                allow = json.loads((root / repo["dir"] / SETTINGS).read_text(encoding="utf-8"))["permissions"]["allow"]
            except (OSError, ValueError, KeyError, TypeError):
                continue
            rules += [root_rule(rule, repo["dir"]) for rule in allow]
    return rules + qa_template.root_extra_allow(TEMPLATES, repos)


def merge_root_permissions(data, root, repos):
    rules = root_permissions(root, repos)
    if not rules:
        return
    have = data.setdefault("permissions", {}).setdefault("allow", [])
    for rule in rules:
        if rule not in have:
            have.append(rule)


def marker_repo(path, marker):
    """Репо готового проекта записью плана — для карты и settings корня."""
    repo = {"role": marker.get("role"), "dir": path.name}
    if repo["role"] == "autotests":
        repo["layers"] = [x.strip() for x in marker.get("layers", "").strip("[]").split(",") if x.strip() in LAYERS]
        if marker.get("frontend_lib"):
            repo["frontend_lib"] = marker["frontend_lib"]
    paths = dict(re.findall(r"^\s+(wiki|collection): (.+)$", (path / MARKER).read_text(encoding="utf-8"), re.M))
    if paths:
        repo["paths"] = paths
    return repo


def render_root(title, repos, git_root):
    """Файлы шаблона корня под эти репо: {имя: текст} — `qa_template.render_root` текущих шаблонов."""
    try:
        return qa_template.render_root(TEMPLATES, title, repos, git_root)
    except qa_template.TemplateError as e:
        raise PlanError(str(e)) from e


def write_root(root, title, repos, git_root, before=None):
    """Кладёт в корень файлы шаблона корня. Готовый файл не перезаписывает — кроме нетронутой карты: её положил
    прошлый `apply` (`before` — отрисовка под прежний набор репо) или она совпадает с отпечатком учёта
    `.qa/root.json` (прошлая версия плагина, ревью 2026-09-30): второй репо дописывается в карту. Карта, от
    которой человек отказался в sync (`declined` в учёте), не кладётся. Учёт переписывается, кроме случая, когда
    карта осталась своей при учёте: его версия и папки — база для склейки у sync.
    Возвращает (записано, строки «не трогал» — для отчёта)."""
    written, kept = [], []
    rendered = render_root(title, repos, git_root)
    record = read_root_record(root)
    entry = (record or {}).get("files", {}).get("CLAUDE.md") or {}
    own_map = False
    for name, text in rendered.items():
        path = root / name
        if path.exists() and name == ".gitignore":  # свой .gitignore — дописать недостающее, своё не трогать
            have = path.read_text(encoding="utf-8")
            lines = set(have.splitlines())
            missing = [l for l in text.splitlines() if l and not l.startswith("#") and l not in lines]
            if missing:
                path.write_text(have + ("" if have.endswith("\n") or not have else "\n")
                                + "# qa-toolkit\n" + "".join(f"{l}\n" for l in missing), encoding="utf-8")
                kept.append(f"`.gitignore` в корне уже был свой — дописал строки плагина: "
                            + ", ".join(f"`{l}`" for l in missing))
            continue
        if name == "CLAUDE.md" and entry.get("state") == "declined" and not path.exists():
            own_map = True  # отказ человека в sync — не возвращаем, учёт как был
            continue
        if path.exists():
            have = path.read_text(encoding="utf-8")
            if have == text:
                continue
            untouched = (before and have == before.get(name)) or (
                name == "CLAUDE.md" and entry.get("state", "issued") == "issued" and not entry.get("base")
                and hashlib.sha256(have.encode("utf-8")).hexdigest() == entry.get("sha256"))
            if not untouched:
                own_map = own_map or name == "CLAUDE.md"
                kept.append(f"`{name}` в корне уже был свой — не трогал" + (
                    ": карта проекта из шаблона плагина в корень не легла" if name == "CLAUDE.md" else ""))
                continue
        path.write_text(text, encoding="utf-8")
        written.append(name)
    if not (own_map and record):
        write_root_record(root, rendered, qa_template.root_inputs(title, repos, git_root))
    return written, kept


def read_root_record(root):
    try:
        return json.loads((root / ROOT_RECORD).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def write_root_record(root, rendered, inputs):
    """Учёт корня для `/qa:sync` (решение человека 2026-09-30): версия и отпечаток карты — отрисовки шаблона,
    даже если в корне осталась своя: отличие файла от неё sync считает правкой человека и склеивает поверх.
    `inputs` — из чего карта нарисована (sync рисует базу с ними). `.gitignore` не учитывается — sync, как
    init, только дописывает в него недостающие строки."""
    record = {"plugin_version": plugin_version(), "inputs": inputs,
              "files": {"CLAUDE.md": {"sha256": hashlib.sha256(rendered["CLAUDE.md"].encode("utf-8")).hexdigest()}}}
    path = root / ROOT_RECORD
    path.parent.mkdir(exist_ok=True)
    path.write_text(dump_json(record), encoding="utf-8")


def put_root(root):
    """`qa-init.py root`: недостающие файлы корня у готового проекта — по маркерам папок."""
    existing = existing_repos(root)
    if not existing:
        raise PlanError(f"{root}: нет ни одного репо с маркером {MARKER.as_posix()} — корню нечего описывать")
    title = next(iter(existing.values())).get("title", root.name)
    repos = [marker_repo(p, m) for p, m in existing.items()]
    path = root / SETTINGS
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    before = json.dumps(data)
    merge_root_permissions(data, root, repos)
    if json.dumps(data) != before:  # без дельты не переписываем: чужое форматирование — как было
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dump_json(data), encoding="utf-8")
    return write_root(root, title, repos, (root / ".git").exists())


def adopt_repo(dest, plan, repo, sibling, created):
    """Приём готового репо: переносы `git mv` (в индексе), settings слиянием, маркер, манифест.
    Шаблон не копируется, своё не трогается; маркер, манифест и settings — вне индекса. Возвращает записи
    settings, убранные вместе с перенесённым.

    `hide_old` — «оставить и скрыть от Claude» (решение человека 2026-09-27): старые скиллы с двойниками
    остаются для другого агента, Claude их не видит (`skillOverrides` в `settings.local.json` — проверено
    спайком 2026-09-25), хук Claude уступает хуку плагина."""
    moves = repo.get("moves") or []
    binding = [b["path"] for b in recognize(dest)["old_binding"]] if repo.get("hide_old") else []
    for src, dst in sorted(moves, key=lambda m: -len(Path(m[0]).parts)):  # вложенное — раньше
        (dest / dst).parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "mv", src, dst], cwd=dest, check=True, capture_output=True)
        parent = (dest / src).parent
        while parent != dest and not any(parent.iterdir()):  # опустевшие папки (`.claude/agents`) не оставляем
            parent.rmdir()
            parent = parent.parent
    for src, dst in moves:  # старый скилл остался — читает данные по старому пути: там ссылка, файл один
        parts = Path(src).parts
        reader = parts[2] if parts[:2] == (".claude", "skills") else (  # лаборатория ручника — `lab/` в корне
            re.match(r"\.qa/labs/([^/]+)/", dst).group(1) if len(parts) == 1 and dst.startswith(".qa/labs/") else None)
        if dst.startswith(ARCHIVE) or not reader or not (dest / ".claude" / "skills" / reader).is_dir():
            continue
        (dest / src).parent.mkdir(parents=True, exist_ok=True)
        (dest / src).symlink_to(os.path.relpath(dest / dst, (dest / src).parent))
        subprocess.run(["git", "add", src], cwd=dest, check=True, capture_output=True)
    hidden, hook_paths, split = [], [], {}
    if repo.get("hide_old"):
        split = split_claude_md_links(dest)
        skills = dest / ".claude" / "skills"
        hidden = sorted(p.name for p in skills.iterdir() if PLUGIN_TWINS["skills"].get(p.name)) if skills.is_dir() else []
        hook_paths = [f".claude/hooks/{name}" for name in HOOK_TWINS if (dest / ".claude" / "hooks" / name).exists()]
        local = dest / ".claude" / "settings.local.json"
        own = json.loads(local.read_text(encoding="utf-8")) if local.exists() else {}
        own.setdefault("skillOverrides", {}).update({name: "off" for name in hidden})
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text(dump_json(own), encoding="utf-8")
    template = json.loads((TEMPLATES / repo["role"] / SETTINGS).read_text(encoding="utf-8"))
    path = dest / SETTINGS
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    name = catalog_name()
    data.setdefault("extraKnownMarketplaces", {})[name] = {
        **template["extraKnownMarketplaces"][name], "source": plan["catalog"]}
    for plugin, on in template["enabledPlugins"].items():
        data.setdefault("enabledPlugins", {}).setdefault(plugin, on)
    dropped = drop_moved_refs(data, [src for src, _ in moves] + hook_paths)
    tags = active_tags(repo)
    for allow in template.get("permissions", {}).get("allow", []):
        have = data.setdefault("permissions", {}).setdefault("allow", [])
        if allow not in have and not (allow == "mcp__playwright" and tags is not None and "frontend" not in tags):
            have.append(allow)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_json(data), encoding="utf-8")
    write_marker(dest, plan, repo, sibling, created)
    # Файлы, у которых в шаблоне есть двойник, — свои: /qa:sync их не перезаписывает. Остальное в
    # манифест не попадает — это не файлы шаблона.
    paths = {**PATH_KEYS, **(repo.get("paths") or {})}
    rename = {"wiki": paths["wiki"], "api_collection": paths["collection"]}
    files = {}
    src = TEMPLATES / repo["role"]
    for p in sorted(src.rglob("*")):
        rel = p.relative_to(src)
        if not p.is_file() or JUNK.intersection(rel.parts):
            continue
        mine = Path(rename.get(rel.parts[0], rel.parts[0]), *rel.parts[1:])
        if (dest / mine).is_file():
            files[mine.as_posix()] = {"sha256": hashlib.sha256((dest / mine).read_bytes()).hexdigest(),
                                      "state": "filled" if rel == SETTINGS else "own"}
    manifest = {"plugin_version": plugin_version(), "template": repo["role"], "created": created,
                "origin": "adopted", "moves": moves, "files": files}
    if hidden:
        manifest["hidden_skills"] = hidden
    if split:
        manifest["other_agent_docs"] = split
    kept = sorted(b for b in binding if (dest / b).exists() or (dest / b).is_symlink())
    if kept:  # её читает другой агент — `refs` только считает (решение человека 2026-09-29)
        manifest["other_agent_binding"] = kept
    (dest / MANIFEST).write_text(dump_json(manifest), encoding="utf-8")
    try:  # «было» для отчёта — сразу после переносов, до правок (находка (а3) `init-12`)
        manifest["refs_found"] = len(stale_refs(dest)["live"])
    except PlanError:
        return dropped  # переносов нет — ссылок искать не на что
    (dest / MANIFEST).write_text(dump_json(manifest), encoding="utf-8")
    return dropped


def mentions(entry, path):
    return re.search(r"(?<![\w.-])" + re.escape(path) + r"(?![\w.-])", entry) is not None


def drop_moved_refs(data, moved):
    """Убирает из settings разрешения и команды хуков, которые смотрят в перенесённое: хук на уехавший
    файл падал бы на каждой правке (материал сценария 2 — `check_no_hardcode.py`). Возвращает убранное."""
    hit = lambda entry: any(mentions(entry, m) for m in moved)
    dropped = []
    allow = data.get("permissions", {}).get("allow")
    if allow is not None:
        dropped += [a for a in allow if hit(a)]
        data["permissions"]["allow"] = [a for a in allow if not hit(a)]
    hooks = data.get("hooks") or {}
    for event in list(hooks):
        groups = []
        for group in hooks[event]:
            kept = [h for h in group.get("hooks", []) if not hit(h.get("command", ""))]
            dropped += [h["command"] for h in group.get("hooks", []) if hit(h.get("command", ""))]
            if kept:
                groups.append({**group, "hooks": kept})
        if groups:
            hooks[event] = groups
        else:
            del hooks[event]
    if "hooks" in data and not hooks:
        del data["hooks"]
    return dropped


# --- ссылки на перенесённое ------------------------------------------------------------------

REF_TAIL = re.compile(r"[^\s`)\]'\"<>|]*")
MD_LINK = re.compile(r"\]\(([^)\s]+)\)")


def relink(repo, target, old, new, moved):
    """Относительная ссылка из перенесённого файла: куда она вела со старого места и как дойти туда с
    нового. Цель уехала в архив — двойник в плагине, как у прочих ссылок. Ссылка, что уже ведёт к файлу
    от нового места, исправлена — её не трогаем (находка (а1) `init-12`)."""
    if re.match(r"[a-z]+:|[#/]", target):
        return None
    path = target.partition("#")[0]
    here = os.path.normpath(os.path.join(os.path.dirname(new), path))
    if not here.startswith("..") and (repo / here).exists():
        return None
    was = os.path.normpath(os.path.join(os.path.dirname(old), path))
    if was.startswith(".."):
        return None
    now = was
    for src, dst in moved:
        if was == src or was.startswith(src + "/"):
            if dst.startswith(ARCHIVE):
                fix = suggest(src, dst, was[len(src):])
                return fix, summary_group(src, dst, fix), None
            now = dst + was[len(src):]
            break
    fixed = os.path.relpath(now, os.path.dirname(new))
    anchor = target[len(path):]
    return None if fixed == path else (f"`{fixed}` — путь от этого файла", RELATIVE_GROUP, fixed + anchor)


RELATIVE_GROUP = "относительные ссылки перенесённых файлов — путь от нового места"


def summary_group(src, dst, fix):
    """Строка сводки, в которую попадает замена: по виду, а не по адресу (на форке FPS адресов — десятки)."""
    if not dst.startswith(ARCHIVE):
        return "данные — тот же файл на новом месте в `.qa/`"
    if fix.startswith("в архиве"):
        return f"в архиве, двойника в плагине нет: `{src}`"
    return fix


def stale_refs(repo):
    """Строки своих .md, которые ссылаются на перенесённое при приёме, и чем их заменить (вариант (б),
    решение человека 2026-09-26). Журнал и страницы вики — история: только счёт."""
    try:
        manifest = json.loads((repo / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        manifest = {}
    moves = manifest.get("moves") or []
    left = [Path(b) for b in manifest.get("other_agent_binding", [])]
    if not moves:
        raise PlanError(f"{repo.name}: в манифесте нет переносов — это не принятый репо, ссылок искать не на что")
    wiki = re.search(r"^  wiki: (.+)$", (repo / MARKER).read_text(encoding="utf-8"), re.M)
    wiki = Path(wiki.group(1) if wiki else PATH_KEYS["wiki"])
    history = [wiki / "log.md", wiki / "wiki", wiki / "raw"]
    moved = sorted(moves, key=lambda m: -len(m[0]))  # вложенный перенос (карточка из папки скилла) — раньше
    pattern = re.compile(r"(?<![\w./-])((?:\.\./)*)(" + "|".join(re.escape(s) for s, _ in moved)
                         + r")(?![\w-]|\.\w)")
    # Файлы данных, уехавшие из папок скиллов в `.qa/`, читает скилл: карточка, уроки, список холодного
    # старта (`.qa/labs/<скилл>/<файл>`), рабочие документы (`.qa/<скилл>/docs/`) — их пути живые. Отчёты
    # и пробы лаборатории глубже (`runs/`, `probes/`) — история, только счёт. Перенесённая целиком папка
    # лаборатории — журнал, её не смотрим.
    data = {dst: src for src, dst in moves if not dst.startswith(ARCHIVE) and (repo / dst).is_file()}
    lab_files = {dst: src for dst, src in data.items()
                 if re.fullmatch(r"\.qa/labs/[^/]+/[^/]+|\.qa/[^/]+/docs/.+", dst)}
    paths = [p for p in repo.rglob("*.md") if p.relative_to(repo).parts[0] not in (".git", ".qa")]
    live, past = [], 0
    # Инструкции другого агента при приёме не трогаем вовсе (находка (а5) `init-13`): замены там — под Claude,
    # а читает их другой агент. Только счёт, отдельно от живых и от истории. Вложенные — тоже его: их читают
    # по папкам.
    # Обвязка, оставленная другому агенту при «скрыть от Claude», — тоже его (решение человека 2026-09-29):
    # только счёт; по старым путям данных там ссылки на новые места.
    others, kept = {}, {}
    for p in sorted(paths + [repo / dst for dst in data]):
        rel = p.relative_to(repo)
        if p.is_symlink():
            continue
        if rel.name in OTHER_AGENT_DOCS or any(rel == b or b in rel.parents for b in left):
            try:
                n = sum(1 for _ in pattern.finditer(p.read_text(encoding="utf-8")))
            except UnicodeDecodeError:
                continue
            if n:
                (others if rel.name in OTHER_AGENT_DOCS else kept)[rel.as_posix()] = n
            continue
        is_past = any(rel == h or h in rel.parents for h in history) or (
            rel.as_posix() in data and rel.as_posix() not in lab_files)
        old = lab_files.get(rel.as_posix())
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            targets = list(MD_LINK.finditer(line))
            links = targets if old else []
            for m in pattern.finditer(line):
                if any(link.start(1) <= m.start() < link.end(1) for link in links):
                    continue  # ссылка перенесённого файла считается от его старого места — ниже
                if is_past:
                    past += 1
                    continue
                src = m.group(2)
                dst = dict(moves)[src]
                tail = REF_TAIL.match(line, m.end()).group(0).rstrip(".,;:") if (repo / dst).is_dir() else ""
                ref = m.group(1) + src + tail
                if any((r["file"], r["line"], r["ref"]) == (rel.as_posix(), n, ref) for r in live[-3:]):
                    continue  # `[путь](путь)` — одна ссылка, а не две
                fix = suggest(src, dst, tail)
                entry = {"file": rel.as_posix(), "line": n, "text": line.strip(),
                         "ref": ref, "suggest": fix, "group": summary_group(src, dst, fix)}
                in_link = any(link.start(1) <= m.start() < link.end(1) for link in targets)
                exact = replacement(src, dst, tail, m.group(1), line[:m.start()], in_link)
                if exact:
                    entry["replace"] = exact[0]
                    if exact[1]:
                        entry["cut"] = exact[1]
                live.append(entry)
            for link in links:
                found_fix = relink(repo, link.group(1), old, rel.as_posix(), moved)
                if found_fix:
                    entry = {"file": rel.as_posix(), "line": n, "text": line.strip(),
                             "ref": link.group(1), "suggest": found_fix[0], "group": found_fix[1]}
                    live.append({**entry, "replace": found_fix[2]} if found_fix[2] else entry)
    files = len({r["file"] for r in live})
    lines = [f"Ссылок на перенесённое — {len(live)} в {files} файлах; в истории (журналы, страницы вики, отчёты "
             f"лабораторий) — {past}, их не правлю"]
    if others:
        lines.append(f"{', '.join(f'`{f}`' for f in others)} — инструкции другого агента, ссылок на перенесённое "
                     f"в них — {sum(others.values())}: их не правлю")
    if kept:
        lines.append(f"обвязка другого агента, оставленная при «скрыть от Claude»: ссылок на перенесённое — "
                     f"{sum(kept.values())} в {len(kept)} файлах (старые пути данных работают — там ссылки на "
                     f"новые места): не правлю")
    groups = {}
    for r in live:
        groups.setdefault(r["group"], []).append(r)
    # Человеку — сводка по видам замен, полный список — по просьбе (решение человека 2026-09-27: на форке
    # FPS ссылок под двести, простыню не читают).
    for group, rs in sorted(groups.items(), key=lambda g: -len(g[1])):
        first = rs[0]
        example = f"`{first['ref']}`" + ("" if first["suggest"] == group else f" → {first['suggest']}")
        lines.append(f"- {group}: {len(rs)} (например, {example}, {first['file']}:{first['line']})")
    detail = [f"- {r['file']}:{r['line']} — `{r['ref']}` → {r['suggest']}" for r in live]
    return {"live": live, "history": past, "other_agent": {**others, **kept}, "other_binding": kept,
            "report_lines": lines, "detail_lines": detail}


INTERPRETER = re.compile(r"(?:^|\s)\S*(?:python[\d.]*|bash|sh|zsh|run)\s+$")
# Интерпретатор, который уходит вместе с путём: команду плагина зовут по имени (находка (в2) `init-15`).
LEAD = re.compile(r"(?<![\w./-])(?:(?:uv|poetry|pipenv)\s+run\s+(?:[\w./-]*python[\d.]*\s+)?"
                  r"|[\w./-]*(?:python[\d.]*|bash|sh|zsh)\s+)$")


def replacement(src, dst, tail, prefix, before, in_link):
    """Чем ровно заменить в строке, когда замена механическая: данные — новый путь, скрипт с двойником
    в плагине — имя команды. Возвращает (замена, что заменить, если больше `ref`) или None. Находка (б4)
    `init-14`: по тексту `suggest` агент заменял сам и задвоил обратные кавычки. Находка (в2) `init-15`:
    интерпретатор перед скриптом (`python3 scripts/x.py`) уходит вместе с путём — иначе агент убирал его своей
    заменой и не весь. Нет замены — правка вручную: скилл, агент, хук, архив без двойника; скрипт в ссылке
    markdown (имя команды — не путь) или после прочего текста команды (`cat scripts/x.py`)."""
    if not dst.startswith(ARCHIVE):
        return prefix + dst + tail, None
    fix = suggest(src, dst, tail)
    if not fix.endswith("— команда плагина по имени") or in_link:
        return None
    name = Path(src + tail).name
    lead = LEAD.search(before)
    if lead:
        return name, lead.group(0) + prefix + src + tail
    if before.count("`") % 2:
        if before[before.rfind("`") + 1:].strip():
            return None
    elif INTERPRETER.search(before):
        return None
    return name, None


def suggest(src, dst, tail):
    """Чем заменить ссылку: данные — новым путём, старая обвязка — двойником в плагине."""
    full = Path(src + tail)
    if not dst.startswith(ARCHIVE):
        return f"`{dst}{tail}`"
    parts = full.parts
    if parts[0] == "scripts" and len(parts) == 2 and SCRIPT_TWINS.get(full.name):
        return f"`{full.name}` — команда плагина по имени"
    tested = full.name.removeprefix("test_")
    if parts[0] == "scripts" and len(parts) == 2 and tested != full.name and (tested in SCRIPT_TWINS or tested in HOOK_TWINS):
        return f"тест `{tested}` — уехал вместе с ним"
    if parts[:2] == (".claude", "hooks") and HOOK_TWINS.get(full.name):
        return f"хук плагина `{HOOK_TWINS[full.name]}` — работает сам"
    if parts[:2] == (".claude", "skills") and len(parts) > 2 and PLUGIN_TWINS["skills"].get(parts[2]):
        twin, inner = PLUGIN_TWINS["skills"][parts[2]], parts[3:]
        if len(inner) > 1 and inner[0] == "scripts":
            return f"`{full.name}` — команда плагина по имени"
        if len(inner) > 1 and inner[0] == "references":
            return f"`references/{'/'.join(inner[1:])}` скилла `{twin}`"
        return f"скилл `{twin}`"
    if parts[:2] == (".claude", "agents") and len(parts) > 2 and PLUGIN_TWINS["agents"].get(full.stem):
        return f"агент `{PLUGIN_TWINS['agents'][full.stem]}`"
    if parts[0] == "rules" and RULE_TWINS.get(full.name):
        return f"`references/{full.name}` скилла `{RULE_TWINS[full.name]}`"
    return f"в архиве: `{dst}{tail}` — двойника в плагине нет"


def apply(root, plan):
    check_plan(plan, root)
    created = datetime.date.today().isoformat()
    repos = plan["repos"]
    existing = existing_repos(root)
    in_root = git_mode(root, [root / r["dir"] for r in repos if r.get("adopt")] + list(existing)) == "root"
    old = [marker_repo(p, m) for p, m in existing.items()]
    before = render_root(plan["title"], old, in_root) if old else None  # карта корня, которую положил прошлый apply
    dropped = {}
    for repo in repos:
        dest = root / repo["dir"]
        others = [r["dir"] for r in repos if r is not repo] + [p.name for p in existing]
        sibling = f"../{others[0]}" if others else None
        if repo.get("adopt"):
            gone = adopt_repo(dest, plan, repo, sibling, created)
            if gone:
                dropped[repo["dir"]] = gone
            continue
        dest.mkdir(exist_ok=True)
        filled = copy_template(repo, dest)
        fill_settings(dest / SETTINGS, plan["catalog"], active_tags(repo))
        write_marker(dest, plan, repo, sibling, created)
        write_manifest(dest, repo["role"], created, filled)
        if not in_root:
            subprocess.run(["git", "init", "-q"], cwd=dest, check=True)
    if in_root and not (root / ".git").exists():
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    for path, marker in existing.items():  # у одиночного репо соседа не было — теперь есть
        if marker.get("sibling") == "none":
            text = (path / MARKER).read_text(encoding="utf-8")
            (path / MARKER).write_text(text.replace("sibling: none", f"sibling: ../{repos[0]['dir']}", 1),
                                       encoding="utf-8")
    merge_root_settings(root, plan["catalog"], repos + old)
    _, kept = write_root(root, plan["title"], repos + old, in_root, before)
    from qa_codex import maybe_configure
    maybe_configure(root)
    return [str(root / r["dir"]) for r in repos], dropped, kept, "root" if in_root else "repos"


def mark_filled(repo, rels):
    """Скилл вписал ответы в файлы шаблона: новый отпечаток и пометка filled. Чужие файлы — отказ."""
    path = repo / MANIFEST
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise PlanError(f"{repo.name}: нет или битый {MANIFEST.as_posix()}")
    unknown = [rel for rel in rels if rel not in manifest["files"] or not (repo / rel).is_file()]
    if unknown:
        raise PlanError(f"{repo.name}: не из шаблона или нет на месте: {', '.join(unknown)}")
    for rel in rels:
        manifest["files"][rel] = {"sha256": hashlib.sha256((repo / rel).read_bytes()).hexdigest(),
                                  "state": "filled"}
    path.write_text(dump_json(manifest), encoding="utf-8")


def strip(folder):
    """Снимает строки разметки слоёв во всех текстовых файлах папки, содержимое слоёв оставляет."""
    every = set(load_layer_map())
    for p in sorted(folder.rglob("*")):
        if not p.is_file() or ".git" in p.relative_to(folder).parts:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        cut = cut_blocks(text, every, p.relative_to(folder).as_posix())
        if cut is not None:
            p.write_text(cut, encoding="utf-8")


# --- verify --------------------------------------------------------------------------------

def read_marker(path):
    return dict(re.findall(r"^(\w+): (.*)$", path.read_text(encoding="utf-8"), re.M))


def verify(root):
    """Проблемы и версии установленных плагинов каталога по папкам (корень, потом репо)."""
    problems = []
    repos = [p for p in sorted(root.iterdir()) if p.is_dir() and (p / ".qa").is_dir()]
    if not repos:
        problems.append(f"{root}: нет ни одного репо с папкой .qa/")
    elif not (root / "CLAUDE.md").is_file() and ((read_root_record(root) or {}).get("files", {}).get(
            "CLAUDE.md") or {}).get("state") != "declined":  # отказ человека в sync — не зовём вернуть
        problems.append("корень: нет карты проекта `CLAUDE.md` — из корня агент не знает, что где лежит и кого "
                        "звать; выполни в корне как есть: qa-init.py root (кладёт карту из шаблона плагина по "
                        "маркерам папок, готовые файлы не трогает)")
    name = catalog_name()
    refs_lines = []
    # Один git в корне (решение 2026-09-29): агент работает только из корня — плагины и settings проверяем
    # у корня; настройки папок ролей из корня не действуют (спайк `mono-1`), свой `.git` в папке — ошибка.
    one_git = (root / ".git").exists()
    for repo in repos:
        tag = repo.name
        role = read_marker(repo / MARKER).get("role") if (repo / MARKER).is_file() else None
        if not (repo / MARKER).is_file():
            problems.append(f"{tag}: нет маркера {MARKER.as_posix()}")
        elif role not in ROLES:
            problems.append(f"{tag}: в {MARKER.as_posix()} нет роли kb или autotests")
        problems += check_rules_call(repo, tag, role)
        try:
            json.loads((repo / MANIFEST).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            problems.append(f"{tag}: нет или битый {MANIFEST.as_posix()}")
        if not one_git:
            problems += check_settings(repo, tag, name)
        status = refs_status(repo)
        problems += check_refs(status, tag)
        if status:
            refs_lines.append(refs_report_line(status, tag))
        if one_git and (repo / ".git").exists():
            problems.append(f"{tag}: свой .git внутри git корня — вложенный репо, git корня его файлы не видит; "
                            "проект — один git в корне")
        elif not one_git and not (repo / ".git").exists():
            problems.append(f"{tag}: не git-репо")
    problems += check_settings(root, "корень", name)
    if one_git:  # папки ролей не проверяются — корень должен включать плагин каждой роли (ревью 0.2.20, В5)
        problems += check_root_role_plugins(root, repos, name)
    from qa_codex import codex_runtime, verify_project
    if codex_runtime():
        return problems + verify_project(root), ["Codex plugins checked; Claude settings prepared, Claude installation is separate."], refs_lines
    try:
        installed = project_installs()
    except (OSError, ValueError, subprocess.CalledProcessError) as e:
        return problems + [f"не проверить установку плагинов: `claude plugin list --json` — {e}"], [], refs_lines
    folders = [(root, "корень")] + ([] if one_git else [(r, r.name) for r in repos])
    for folder, tag in folders:
        problems += check_installed(folder, tag, name, installed)
    return problems, [f"{tag}: {installed_here(folder, name, installed)}" for folder, tag in folders], refs_lines


RULES_VERB = re.compile(r"вызов|вызыв|в начале сессии", re.I)


def rules_calls(text):
    """Абзацы, которые зовут скилл `qa:rules`: в абзаце есть и скилл, и вызов. Комментарии не в счёт, как
    и упоминание `qa:rules` без вызова — такое оставляет замена ссылки из `refs`."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return [p for p in re.split(r"\n\s*\n", text) if "qa:rules" in p and RULES_VERB.search(p)]


def check_rules_call(repo, tag, role):
    """Находка (б2) `init-13`, `init-14`: при приёме агент не добавил в `CLAUDE.md` вызов `qa:rules` —
    правила плагина в проекте не грузятся, а verify был зелёным. Новый репо из шаблона вызов уже несёт.
    Находка (г1) `init-16`: «добавь» до шага «Ссылки» агент выполнил сразу, мимо гейта «Правлю?» — пока
    шаг не пройден (`--keep` не записал `refs_kept`), строка отсылает к «Правлю?»."""
    try:
        if rules_calls((repo / "CLAUDE.md").read_text(encoding="utf-8")):
            return []
    except (OSError, UnicodeDecodeError):
        pass
    template = TEMPLATES / (role if role in ROLES else "kb") / "CLAUDE.md"
    (para, *_) = rules_calls(template.read_text(encoding="utf-8"))
    try:
        manifest = json.loads((repo / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        manifest = {}
    if manifest.get("origin") == "adopted" and "refs_kept" not in manifest:
        what = (f"шаг «Ссылки» не пройден: в «Правлю?» скажи «добавлю» и вставь после «да», до ответа "
                f"`CLAUDE.md` не трогай; абзац из шаблона `{template}` как есть")
    else:
        what = f"добавь абзац из шаблона `{template}` как есть"
    return [f"{tag}: в CLAUDE.md нет вызова скилла `qa:rules` — правила плагина в проекте не загрузятся; "
            f"{what}: {' '.join(para.split())}"]


def refs_status(repo):
    """Ссылки принятого репо сейчас: живые (строками-вхождениями, как в `refs`), не оставленные человеком,
    пары `refs_kept`, счёт при приёме (`refs_found` от `apply`) и в истории; не принятый репо — None."""
    try:
        found = stale_refs(repo)
        manifest = json.loads((repo / MANIFEST).read_text(encoding="utf-8"))
    except (PlanError, OSError, ValueError):
        return None
    kept = {tuple(k) for k in manifest.get("refs_kept", [])}
    return {"found": manifest.get("refs_found"), "live": len(found["live"]), "history": found["history"],
            "other_agent": sum(found["other_agent"].values()) - sum(found["other_binding"].values()),
            "other_binding": sum(found["other_binding"].values()), "pairs": len(kept), "unkept": [r for r in found["live"] if (r["file"], r["ref"]) not in kept]}


def refs_report_line(status, tag):
    """Строка отчёта про ссылки — готовая: на полигоне init-12 агент посчитал сам и выдумал числа."""
    left, unkept = status["live"], len(status["unkept"])
    kept = f"оставлено по решению человека — {left - unkept}" + (
        f" (пар «файл → ссылка» в манифесте — {status['pairs']})" if status["pairs"] else "")
    was = (f"при приёме найдено — {status['found']}; поправлено — {max(status['found'] - left, 0)}"
           if status["found"] is not None else f"при приёме — не записано; живых сейчас — {left}")
    line = f"{tag}: {was}; {kept}; в истории — {status['history']}, не правились"
    if status["other_agent"]:  # не в «найдено»: `refs_found` от `apply` их тоже не считает
        line += f"; в инструкциях другого агента — {status['other_agent']}, не правились"
    if status["other_binding"]:
        line += f"; в обвязке, оставленной другому агенту, — {status['other_binding']}, не правились"
    return line + (f"; не решено — {unkept}: шаг «Ссылки» не пройден" if unkept else "")


def keep_refs(repo, named=()):
    """Шаг «Ссылки» пройден: живые после правок — только те, что человек оставил, и они названы: строка
    сводки целиком (`group`) или ссылка `файл:строка`. Находка (а6) `init-13`: голый `--keep` записывал всё
    живое, и агент оставил 4 ссылки сам, а verify подписал их «по решению человека». Живая без имени или имя
    без живой — отказ, манифест не тронут."""
    found = stale_refs(repo)
    named = set(named)
    hit = lambda r: r["group"] in named or f"{r['file']}:{r['line']}" in named
    unnamed = [r for r in found["live"] if not hit(r)]
    unknown = sorted(n for n in named if not any(n in (r["group"], f"{r['file']}:{r['line']}") for r in found["live"]))
    if unnamed or unknown:
        why = []
        if unnamed:
            why.append("живые ссылки, которых человек не оставлял — покажи их ему формой «оставить / поправить», "
                       "до ответа --keep не зови:\n" + "\n".join(
                           f"- {r['file']}:{r['line']} — `{r['ref']}` → {r['suggest']}" for r in unnamed))
        if unknown:
            why.append("среди живых нет: " + "; ".join(unknown)
                       + " (оставить можно строку сводки целиком или `файл:строка` из свежего `refs`)")
        raise PlanError("манифест не тронут: " + "\n".join(why))
    path = repo / MANIFEST
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["refs_kept"] = sorted({(r["file"], r["ref"]) for r in found["live"]})
    path.write_text(dump_json(manifest), encoding="utf-8")
    return found


def apply_refs(repo, named):
    """После «да» человека: в строках названных групп сводки (или `файл:строка`) ровно `ref` → `replace`,
    кавычки и соседний текст не трогает. Что без `replace` или не вышло однозначно — в ручные.
    Неизвестное имя — отказ, файлы не тронуты. Пустой перечень — тоже: находка (б1) `init-14`, агент правил
    до ответа человека; что править, называет только ответ на сводку."""
    if not named:
        raise PlanError("ничего не правил: --apply без перечня. Спроси человека «Правлю?» с числами из `report_lines`; "
                        "после «да» — все строки сводки (поле `group`)")
    found = stale_refs(repo)
    named = set(named)
    hit = lambda r: r["group"] in named or f"{r['file']}:{r['line']}" in named
    unknown = sorted(n for n in named if not any(n in (r["group"], f"{r['file']}:{r['line']}") for r in found["live"]))
    if unknown:
        raise PlanError("ничего не правил: среди живых нет: " + "; ".join(unknown)
                        + " (назови строку сводки целиком — поле `group` из `refs` — или `файл:строка`)")
    chosen = [r for r in found["live"] if hit(r)]
    by_file = {}
    for r in chosen:
        by_file.setdefault(r["file"], {}).setdefault(r["line"], []).append(r)
    applied, manual = [], []
    for rel, lines in by_file.items():
        path = repo / rel
        raw = path.read_bytes().decode("utf-8")  # не read_text: переводы строк файла — как были
        text = raw.splitlines(keepends=True)
        for n, rs in lines.items():
            line, spans = text[n - 1], []
            for r in rs:
                if r.get("replace"):
                    at = re.compile(r"(?<![\w./-])" + re.escape(r.get("cut", r["ref"])) + r"(?![\w/-]|\.\w)")
                    spans += [(m.start(), m.end(), r) for m in at.finditer(line)]
            spans.sort(key=lambda s: s[0])
            clash = {id(a[2]) for a, b in zip(spans, spans[1:]) if b[0] < a[1]}
            clash |= {id(b[2]) for a, b in zip(spans, spans[1:]) if b[0] < a[1]}
            done = set()
            for start, end, r in reversed(spans):
                if id(r) not in clash:
                    line = line[:start] + r["replace"] + line[end:]
                    done.add(id(r))
            text[n - 1] = line
            for r in rs:
                (applied if id(r) in done else manual).append(r)
        if "".join(text) != raw:
            path.write_bytes("".join(text).encode("utf-8"))
    files = len({r["file"] for r in applied})
    return {"applied": [f"- {r['file']}:{r['line']} — `{r.get('cut', r['ref'])}` → `{r['replace']}`"
                        for r in applied],
            "manual": [f"- {r['file']}:{r['line']} — `{r['ref']}` → {r['suggest']}" for r in manual],
            "report_lines": [f"Поправил сам ссылок — {len(applied)} в {files} файлах; вручную — {len(manual)}"]}


def check_refs(status, tag):
    """Полигон init-11: после нового kb агент ушёл по нумерации основного пути и шаг «Ссылки» пропустил,
    verify был зелёным при 190 живых ссылках."""
    left = status and status["unkept"]
    if not left:
        return []
    return [f"{tag}: ссылок на перенесённое — {len(left)}, шаг «Ссылки» не пройден: `qa-init.py refs {tag}` "
            f"→ «Правлю?» человеку; что он оставил — `qa-init.py refs {tag} --keep <строка сводки | файл:строка>…`"]


def project_installs():
    """Установки плагинов в проекты: (id плагина, реальный путь папки) → версия.

    Путь есть только в `--json`: обычный `claude plugin list` печатает установки всех проектов
    машины подряд, без папки, — версию своей по нему не понять (полигоны init-2, init-7)."""
    out = subprocess.run(["claude", "plugin", "list", "--json"], capture_output=True, text=True,
                         check=True).stdout
    return {(row["id"], os.path.realpath(row["projectPath"])): row.get("version", "?")
            for row in json.loads(out) if row.get("scope") == "project" and row.get("projectPath")}


def installed_here(folder, name, installed):
    where = os.path.realpath(folder)
    found = sorted((pid.removesuffix(f"@{name}"), version) for (pid, path), version in installed.items()
                   if path == where and pid.endswith(f"@{name}"))
    return ", ".join(f"{plugin} {version}" for plugin, version in found) or "плагины каталога не установлены"


def check_installed(folder, tag, name, installed):
    try:
        enabled = json.loads((folder / SETTINGS).read_text(encoding="utf-8")).get("enabledPlugins", {})
    except (OSError, ValueError):
        return []  # о битых settings уже сказал check_settings
    where = os.path.realpath(folder)
    missing = [pid for pid, on in enabled.items()
               if on and pid.endswith(f"@{name}") and (pid, where) not in installed]
    # Команда готовая, с папкой: полигон init-14 (находка (б3)) — список «что куда» агент собрал сам и в репо
    # поставил только qa-auto/qa-manual, без ядра qa.
    return [f"{tag}: включён, но не установлен {pid} — выполни как есть: "
            f"cd {shlex.quote(where)} && claude plugin install {pid} --scope project" for pid in missing]


def check_root_role_plugins(root, repos, name):
    try:
        enabled = json.loads((root / SETTINGS).read_text(encoding="utf-8")).get("enabledPlugins", {})
    except (OSError, ValueError, AttributeError):
        return []  # о битых settings уже сказал check_settings
    roles = {read_marker(r / MARKER).get("role") for r in repos if (r / MARKER).is_file()}
    return [f"корень: не включён плагин {ROLES[role]}@{name} — из корня скиллов роли {role} нет; добавь его в "
            f"enabledPlugins {SETTINGS.as_posix()} корня" for role in sorted(roles & set(ROLES))
            if not enabled.get(f"{ROLES[role]}@{name}")]


def check_settings(folder, tag, name):
    try:
        data = json.loads((folder / SETTINGS).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [f"{tag}: нет или битый {SETTINGS.as_posix()}"]
    source = data.get("extraKnownMarketplaces", {}).get(name, {}).get("source")
    if not source or has_placeholder(source):
        return [f"{tag}: не заполнен источник каталога {name} в {SETTINGS.as_posix()}"]
    if not data.get("enabledPlugins", {}).get(f"qa@{name}"):
        return [f"{tag}: не включён плагин qa@{name}"]
    return []


# --- CLI -----------------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scan", help="опись текущей папки")
    p_apply = sub.add_parser("apply", help="создать репо по плану")
    p_apply.add_argument("plan", type=Path)
    p_filled = sub.add_parser("filled", help="отметить файлы шаблона, заполненные скиллом")
    p_filled.add_argument("repo", type=Path)
    p_filled.add_argument("files", nargs="+")
    p_refs = sub.add_parser("refs", help="ссылки своих файлов на перенесённое при приёме")
    p_refs.add_argument("repo", type=Path)
    refs_mode = p_refs.add_mutually_exclusive_group()
    refs_mode.add_argument("--keep", nargs="*", metavar="ОСТАВЛЕНО",
                           help="что оставил человек — строки сводки целиком или `файл:строка`; записать в манифест")
    refs_mode.add_argument("--apply", nargs="*", metavar="ПРАВЛЮ",
                           help="после «да» человека: строки сводки (или `файл:строка`) — "
                                "механические замены сделать, ручные напечатать")
    sub.add_parser("verify", help="проверить результат")
    sub.add_parser("root", help="положить в корень готового проекта недостающие файлы шаблона корня")
    p_strip = sub.add_parser("strip", help="снять разметку слоёв, оставив все слои")
    p_strip.add_argument("folder", type=Path)
    for cp in (p_apply,):
        cp.add_argument("--with-codex", action="store_true", help="also create Codex companions without changing Claude settings")
    args = ap.parse_args(argv)
    if getattr(args, "with_codex", False):
        os.environ["QA_WITH_CODEX"] = "1"
    root = Path.cwd()

    if args.cmd == "scan":
        print(json.dumps(scan(root), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "apply":
        try:
            plan = json.loads(args.plan.read_text(encoding="utf-8"))
            made, dropped, kept, git = apply(root, plan)
        except (PlanError, ValueError, OSError) as e:
            print(f"qa-init: план не принят, ничего не записано: {e}", file=sys.stderr)
            return 2
        print(json.dumps({"created": made, "settings_dropped": dropped, "root_kept": kept, "git": git},
                         ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "root":
        try:
            written, kept = put_root(root)
            from qa_codex import maybe_configure
            maybe_configure(root)
        except PlanError as e:
            print(f"qa-init: {e}", file=sys.stderr)
            return 2
        print(json.dumps({"written": written, "root_kept": kept}, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "filled":
        try:
            mark_filled(root / args.repo, args.files)
        except PlanError as e:
            print(f"qa-init: манифест не тронут: {e}", file=sys.stderr)
            return 2
        return 0
    if args.cmd == "refs":
        try:
            repo = root / args.repo
            if args.apply is not None:
                found = apply_refs(repo, args.apply)
            else:
                found = stale_refs(repo) if args.keep is None else keep_refs(repo, args.keep)
            print(json.dumps(found, ensure_ascii=False, indent=2))
        except PlanError as e:
            print(f"qa-init: {e}", file=sys.stderr)
            return 2
        return 0
    if args.cmd == "strip":
        try:
            strip(args.folder)
        except PlanError as e:
            print(f"qa-init: {e}", file=sys.stderr)
            return 2
        return 0
    problems, versions, refs_lines = verify(root)
    for line in problems:
        print(f"- {line}")
    if not problems:
        print("verify: всё на месте")
    if versions:
        print("установлено (версии по папкам — их и пиши в отчёт):")
        for line in versions:
            print(f"- {line}")
    if refs_lines:
        print("ссылки на перенесённое (числа — их и пиши в отчёт, сам не считай):")
        for line in refs_lines:
            print(f"- {line}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
