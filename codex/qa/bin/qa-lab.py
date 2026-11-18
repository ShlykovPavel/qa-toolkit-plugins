#!/usr/bin/env python3
"""qa-lab — выжимка сессии Claude Code для лаборатории плагина (docs/plugin/lab-draft.md мастерской).

    qa-lab.py digest <транскрипт.jsonl>                  # выжимка одной сессии — одна строка JSON в stdout
    qa-lab.py record <транскрипт.jsonl> [--cwd <папка>]  # выжимку — в файл репо проекта
    qa-lab.py catch-up <папка транскриптов> --cwd <папка> [--skip <session_id>]  # записать пропущенные
    qa-lab.py hook-end | hook-start                      # хуки плагина: вход — JSON хука в stdin

Куда пишется: `.qa/labs/sessions/<машина>.jsonl` репо, где шла сессия (от папки сессии вверх до маркера
`.qa/project.yaml`); сессия корня над репо — в репо базы знаний (`role: kb` среди подпапок). Файл свой у каждой
машины — ветки с двух машин сливаются без конфликтов; строка на сессию, повторная запись (сессию продолжили)
заменяет строку. Не QA-проект или `lab: off` в маркере — ничего не пишется. Машина — имя хоста или
`QA_LAB_MACHINE`.

Хуки (`hooks/hooks.json`): `SessionEnd` — `record` этой сессии, `SessionStart` — `catch-up` сессий этой папки,
которых нет в файле (упала, `kill -9`, история до плагина), кроме идущей. Хуку `SessionEnd` дают 1,5 с (спайк
2026-09-28), поэтому оба только запускают работу отцепленным процессом и выходят; ничего не печатают (вывод
`SessionStart` попал бы в контекст агента), код всегда 0. Ошибки фоновой работы — в `$TMPDIR/qa-lab.log`.

Сбор — механикой, суждение — моделью: скрипт считает и вырезает куски вокруг сигналов, что они значат —
решает аналитик на разборе. Сырой транскрипт в git не идёт (тяжёлый, с данными продукта) — только выжимка,
секреты в ней скрыты.

Выжимка: сессия (`session`, `cwd`, `branch`, `cc` — версия Claude Code, `start`, `end`), `prompts` — реплик
человека, `plugins` — версии плагинов по вызванным скиллам (`dev` — не из кэша, `--plugin-dir`), `skills` —
вызовы (`slash` — командой человека, `tool` — агент сам), `commands` — встроенные слэш-команды (`/model`,
`/compact`: после них нет строки «Base directory for this skill»), `agents`, `bash` — первые слова команд, `reads` —
чтения файлов скиллов (путь от `skills/`), `lang` — доля кириллицы в речи агента, `tokens` — главный разговор
и субагенты, `broken` — битых строк (файл дописывался при чтении), `signals` — кандидаты для аналитика:

    tool_error            ошибка инструмента; «Exit code 1» без слов-ошибок в выводе (grep ничего не нашёл,
                          цепочка echo/grep) — не ошибка; строка zsh `(eval):N: ==== not found` (разделитель
                          `echo ====`) в счёт слов не идёт
    denied                отказ в разрешении (`denial` — вид: правило, классификатор, человек)
    pushback              реплика человека с «нет», «не так», «стоп», «я же», «не не», «давай на русском», оценкой
                          («плохо», «излишне», «раньше … делал»)… в первых 300 знаках — смысл решает аналитик
    own_answer            на форму с вариантами человек ответил своим текстом — варианты не подошли; `what` —
                          вопрос и ответ
    interrupt             человек прервал агента
    write_before_answer   первая запись (Write/Edit, git commit/push) после вызова скилла, когда человек ещё
                          ни разу не ответил — ни формой, ни текстом

У сигнала `line` — номер строки транскрипта (с 1) и `context` — соседние реплики и вызовы, обрезанные.
Строки субагентов (`isSidechain`, старые версии) идут только в счёт токенов.

Продолженная сессия (`--resume`, ветка в приложении) — новый файл, который начинается с копии старой истории: те же
`uuid` и время, `sessionId` бывает и старый. Поэтому id сессии — имя файла, а строка, чей `uuid` уже есть в более
раннем файле той же папки (по времени создания файла), — копия: в счёт не идёт. `copied` — сколько таких строк,
`resumed_from` — чья история скопирована.
Тест — `qa-toolkit/tests/test_qa_lab.py`.

Коды возврата: 0 — готово; 2 — файла нет или он не читается, причина в stderr.
"""
import argparse
import fcntl
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

from qa_template import read_marker

VERSION = 1
MARKER = Path(".qa") / "project.yaml"
SESSIONS = Path(".qa") / "labs" / "sessions"
LOG = Path(tempfile.gettempdir()) / "qa-lab.log"
CONTEXT_BEFORE, CONTEXT_AFTER, TEXT_MAX = 3, 2, 300
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
GIT_WRITE = re.compile(r"\bgit\s+(?:-\S+\s+(?:\S+\s+)?)*(?:commit|push)\b")
PUSHBACK = re.compile(r"(?:^|[.!?]\s*)нет\b|\bне так\b|\bне то\b|\bстоп\b|\bя же\b|\bзачем\b|\bне надо\b|\bверни\b"
                      r"|\bоткати\b|\bоткатывай|\bнеправильн|\bне\s+не\b"
                      r"|\bплохо\b|\bизлиш|\bраньше\b[^.!?\n]{0,60}\b(?:делал|работал|умел)"
                      r"|(?:^|[.!?]\s*)(?:давай\s+|говори\s+|пиши\s+)?(?:на русском|по-русски)\b"
                      r"|(?:^|[.!?]\s*)no\b|\bstop\b|\bwrong\b|\bdon'?t\b",
                      re.I)
PUSHBACK_HEAD = 300  # несогласие — в начале реплики; дальше — вставленная задача, там «зачем» и «не так» не про агента
ERROR_WORDS = re.compile(r"traceback|error|fatal|no such file|not found|denied|failed|exception|cannot|can't"
                         r"|permission|not permitted|blocked|ошибк", re.I)
ZSH_EQUALS = re.compile(r"^\(eval\):\d+: =+ not found$", re.M)  # zsh раскрывает `=слово` в путь команды
INTERRUPT = "[Request interrupted by user"
SKILL_BASE = re.compile(r"^Base directory for this skill: (\S+)")
CACHED = re.compile(r"/plugins/cache/[^/]+/([^/]+)/([^/]+)/skills/")
COMMAND = re.compile(r"<command-name>/([^<\s]+)</command-name>")
SECRETS = [
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]{8,}"), r"\1***"),
    (re.compile(r"(?i)((?:token|password|passwd|secret|api[_-]?key|authorization)[\"']?\s*[:=]\s*[\"']?)"
                r"[^\s\"'&,;]{4,}"), r"\1***"),
    (re.compile(r"\b(?:ghp|gho|ghs|github_pat|glpat|sk|xox[bp])[-_][A-Za-z0-9_-]{10,}"), "***"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"), "***"),
    (re.compile(r"\bperm[:-][A-Za-z0-9.=_-]{10,}"), "***"),
]


def mask(text):
    for pattern, repl in SECRETS:
        text = pattern.sub(repl, text)
    return text


def clip(text):
    text = mask(" ".join(str(text).split()))
    return text if len(text) <= TEXT_MAX else text[:TEXT_MAX - 1] + "…"


def read_lines(path):
    lines, broken = [], 0
    with open(path, encoding="utf-8", errors="replace") as f:
        for n, raw in enumerate(f, 1):
            try:
                lines.append((n, json.loads(raw)))
            except json.JSONDecodeError:
                broken += 1
    return lines, broken


def blocks(line):
    content = (line.get("message") or {}).get("content")
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return [b for b in content or [] if isinstance(b, dict)]


def human_text(line):
    """Текст реплики человека или None: служебное (мета, уведомления, результаты инструментов) — не реплика."""
    if line.get("type") != "user" or line.get("isMeta"):
        return None
    origin = (line.get("origin") or {}).get("kind")
    if origin not in (None, "human"):
        return None
    parts = blocks(line)
    if not parts or any(b.get("type") == "tool_result" for b in parts):
        return None
    text = "\n".join(b.get("text", "") for b in parts if b.get("type") == "text")
    if not text or text.startswith(("<task-notification>", "<local-command", "Caveat:")):
        return None
    return text


def usage_sum(lines, seen=None):
    seen = set() if seen is None else seen
    tin = tout = 0
    for _, line in lines:
        msg = line.get("message") or {}
        usage = msg.get("usage")
        key = msg.get("id") or line.get("requestId") or line.get("uuid")
        if line.get("type") != "assistant" or not usage or key in seen:
            continue
        seen.add(key)
        tin += sum(usage.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens",
                                                "cache_read_input_tokens"))
        tout += usage.get("output_tokens") or 0
    return tin, tout


SHELL_WORDS = {"do", "done", "then", "else", "elif", "fi", "time", "!", "{", "}", "esac", "while", "until", "if"}
HEREDOC = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?")
HEAD = re.compile(r"^[\w.][\w.+-]*$")


def bash_heads(command):
    """Первые слова команд; тела heredoc и слова shell (`for … do … done`) — не команды."""
    heads, end = [], None
    for text in command.splitlines():
        if end is not None:
            end = None if text.strip() == end else end
            continue
        heredoc = HEREDOC.search(text)
        end = heredoc.group(1) if heredoc else None
        for part in re.split(r"&&|\|\||[;|()]", text):
            words = part.split()
            while words and (words[0] in SHELL_WORDS or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0])):
                words = words[1:]  # if cmd, do cmd, FOO=1 cmd
            if not words or words[0] in ("for", "case", "select"):
                continue
            head = Path(words[0]).name
            if HEAD.match(head):
                heads.append(head)
    return heads


def tool_summary(block):
    inp = block.get("input") or {}
    name = block.get("name", "?")
    detail = (inp.get("command") or inp.get("file_path") or inp.get("skill") or inp.get("subagent_type")
              or inp.get("pattern") or "")
    if name == "AskUserQuestion":
        detail = " | ".join(q.get("question", "") for q in inp.get("questions", []))
    return f"{name}: {detail}"


def answer_marks(use, text):
    """Только найденные ответы; подтверждение отправки формы не является ответом."""
    questions = [q for q in (use.get("input") or {}).get("questions") or [] if isinstance(q, dict)]
    marks = [(text.find(f'"{q.get("question")}"="'), q) for q in questions]
    return sorted(((at, q) for at, q in marks if at >= 0), key=lambda mark: mark[0])


def own_answers(use, text):
    """Ответы на форму не из вариантов: [(вопрос, ответ)]. Вопрос без вариантов не судим."""
    marks = answer_marks(use, text)
    found = []
    for i, (at, q) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        raw = text[at + len(q["question"]) + 4:end]
        labels = sorted((o.get("label", "") for o in q.get("options") or [] if isinstance(o, dict)),
                        key=len, reverse=True)
        rest = raw
        while True:  # выбор — подпись варианта; при множественном — подписи через «, »
            label = next((x for x in labels if x and rest.startswith(x)), None)
            if not label:
                break
            rest = rest[len(label):]
            if not rest.startswith(", "):
                break
            rest = rest[2:]
        if labels and not rest.startswith(('"', '[No preference]"')):  # пропущенный вопрос — не свой текст
            found.append((q["question"], raw[:raw.rfind('"')] if '"' in raw else raw))
    return found


def result_text(block):
    content = block.get("content")
    if isinstance(content, list):
        content = "\n".join(c.get("text", "") for c in content if isinstance(c, dict))
    return str(content or "")


UUID = re.compile(r'"uuid":\s*"([^"]+)"')


def born(path):
    st = path.stat()
    return getattr(st, "st_birthtime", st.st_mtime), path.name


def uuid_owners(folder):
    """uuid строки → сессия (имя файла), где она появилась первой: файлы по времени создания, старший — хозяин."""
    owners = {}
    for p in sorted(Path(folder).glob("*.jsonl"), key=born):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for u in UUID.findall(text):
            owners.setdefault(u, p.stem)
    return owners


def digest(path, owners=None):
    path = Path(path)
    from qa_codex import is_rollout, digest as codex_digest
    if is_rollout(path):
        return codex_digest(path)[0]
    owners = uuid_owners(path.parent) if owners is None else owners
    lines, broken = read_lines(path)
    own, copied = [], []  # copied — чьи строки скопированы, по строке
    for n, x in lines:
        owner = owners.get(x.get("uuid"), path.stem)
        if owner == path.stem:
            own.append((n, x))
        else:
            copied.append(owner)
    lines = own
    main = [(n, x) for n, x in lines if not x.get("isSidechain")]
    side = [(n, x) for n, x in lines if x.get("isSidechain")]

    def first(key):  # служебные строки в начале (queue-operation) бывают без cwd и версии
        return next((x[key] for _, x in main if x.get(key)), None)

    stamps = [x["timestamp"] for _, x in lines if x.get("timestamp")]
    out = {"v": VERSION, "session": path.stem, "cwd": first("cwd"),
           "branch": first("gitBranch"), "cc": first("version"),
           "start": min(stamps) if stamps else None, "end": max(stamps) if stamps else None}

    events, signals = [], []  # events — для контекста: (строка, кто, текст)
    skills, plugins, agents, bash, reads, commands = [], {}, Counter(), Counter(), Counter(), Counter()
    pending = None  # слэш-команда: скилл, если следом строка «Base directory for this skill», иначе встроенная
    tools = {}  # tool_use_id -> (имя, блок)
    cyr = letters = prompts = 0
    window = None  # {"skill", "answered", "flagged"} — текущий вызванный скилл

    def start_skill(name, how, n):
        nonlocal window
        skills.append({"name": name, "how": how, "line": n})
        window = {"skill": name, "answered": False, "flagged": False}

    def flush():
        nonlocal pending
        if pending:
            commands[pending[0]] += 1
            pending = None

    for n, line in main:
        kind = line.get("type")
        if kind == "user":
            text = human_text(line)
            if text is not None:
                flush()
            if text is not None and text.startswith(INTERRUPT):
                signals.append({"kind": "interrupt", "line": n})
                events.append((n, "human", text))
                continue
            if text is not None:
                prompts += 1
                events.append((n, "human", text))
                command = COMMAND.search(text)
                if command:
                    pending = (command.group(1), n)
                    continue
                if window:
                    window["answered"] = True
                if PUSHBACK.search(text[:PUSHBACK_HEAD]):
                    signals.append({"kind": "pushback", "line": n, "what": clip(text)})
                continue
            for b in blocks(line):
                if b.get("type") == "text":
                    base = SKILL_BASE.match(b.get("text", ""))
                    if base and pending:
                        start_skill(pending[0], "slash", pending[1])
                        pending = None
                    if base:
                        cached = CACHED.search(base.group(1) + "/")
                        if cached:
                            plugins[cached.group(1)] = cached.group(2)
                        else:
                            parts = Path(base.group(1)).parts
                            if "skills" in parts:
                                owner = parts[parts.index("skills") - 1]
                                if owner != ".claude":
                                    plugins.setdefault(owner, "dev")
                if b.get("type") != "tool_result":
                    continue
                name, use = tools.get(b.get("tool_use_id"), ("?", {}))
                text = result_text(b)
                if line.get("toolDenialKind"):
                    signals.append({"kind": "denied", "line": n, "tool": name, "denial": line["toolDenialKind"],
                                    "what": clip(tool_summary(use))})
                    events.append((n, "tool", "отказ: " + text))
                elif b.get("is_error"):
                    if (name == "Bash" and text.startswith("Exit code 1")
                            and not ERROR_WORDS.search(ZSH_EQUALS.sub("", text[12:]))):
                        continue  # grep без совпадений, цепочка echo/grep, `echo ====` в zsh — поиск, не ошибка
                    signals.append({"kind": "tool_error", "line": n, "tool": name, "what": clip(text)})
                    events.append((n, "tool", "ошибка: " + text))
                elif name == "AskUserQuestion":
                    if window and answer_marks(use, text):
                        window["answered"] = True
                    own = own_answers(use, text)
                    if own:
                        signals.append({"kind": "own_answer", "line": n,
                                        "what": clip("; ".join(f"{q} → {a}" for q, a in own))})
                        events.append((n, "human", "ответ на форму: " + "; ".join(a for _, a in own)))
        elif kind == "assistant":
            flush()
            for b in blocks(line):
                if b.get("type") == "text":
                    text = b.get("text", "")
                    events.append((n, "agent", text))
                    for ch in text:
                        if ch.isalpha():
                            letters += 1
                            cyr += "а" <= ch.lower() <= "я" or ch.lower() == "ё"
                    continue
                if b.get("type") != "tool_use":
                    continue
                name, inp = b.get("name"), b.get("input") or {}
                tools[b.get("id")] = (name, b)
                events.append((n, "tool", tool_summary(b)))
                if name == "Skill" and inp.get("skill"):
                    start_skill(inp["skill"], "tool", n)
                    continue
                if name == "Agent" and inp.get("subagent_type"):
                    agents[inp["subagent_type"]] += 1
                if name == "Bash":
                    bash.update(bash_heads(inp.get("command", "")))
                if name == "Read" and "/skills/" in inp.get("file_path", ""):
                    reads[inp["file_path"].rsplit("/skills/", 1)[1]] += 1
                writes = name in WRITE_TOOLS or (name == "Bash" and GIT_WRITE.search(inp.get("command", "")))
                if writes and window and not window["answered"] and not window["flagged"]:
                    window["flagged"] = True
                    signals.append({"kind": "write_before_answer", "line": n, "skill": window["skill"],
                                    "what": clip(tool_summary(b))})

    flush()
    index = {n: i for i, (n, _, _) in reversed(list(enumerate(events)))}
    for s in signals:
        at = index.get(s["line"])
        if at is None:  # сигнал на строке результата — контекст от ближайшего события до неё
            at = max((i for i, (n, _, _) in enumerate(events) if n <= s["line"]), default=0)
        s["context"] = [{"line": n, "who": who, "text": clip(text)}
                        for n, who, text in events[max(0, at - CONTEXT_BEFORE):at + CONTEXT_AFTER + 1]]
    signals.sort(key=lambda s: s["line"])

    subdir = path.with_suffix("") / "subagents"
    subfiles = sorted(subdir.glob("*.jsonl")) if subdir.is_dir() else []
    sub_in, sub_out = usage_sum(side)
    for f in subfiles:
        s_lines, s_broken = read_lines(f)
        broken += s_broken
        a, b = usage_sum(s_lines)
        sub_in, sub_out = sub_in + a, sub_out + b
    main_in, main_out = usage_sum(main)

    out.update({"prompts": prompts, "plugins": plugins, "skills": skills, "commands": dict(commands),
                "agents": dict(agents),
                "bash": dict(bash), "reads": dict(reads),
                "lang": {"cyr": round(cyr / letters, 2) if letters else None, "chars": letters},
                "tokens": {"main": {"in": main_in, "out": main_out},
                           "sub": {"in": sub_in, "out": sub_out, "agents": len(subfiles)}},
                "broken": broken, "copied": len(copied), "resumed_from": copied[0] if copied else None,
                "signals": signals})
    return out


def machine():
    name = re.sub(r"\.local$", "", os.environ.get("QA_LAB_MACHINE") or socket.gethostname())
    return re.sub(r"[^\w.-]", "_", name) or "machine"


def lab_repo(cwd):
    """Репо, куда идёт выжимка сессии из папки `cwd`; None — не QA-проект или сбор выключен (`lab: off`)."""
    cwd = Path(cwd)
    repo = next((d for d in [cwd, *cwd.parents] if (d / MARKER).is_file()), None)
    if repo is None:
        try:
            kbs = [c for c in sorted(cwd.iterdir())
                   if c.is_dir() and (c / MARKER).is_file() and read_marker(c / MARKER).get("role") == "kb"]
        except OSError:
            return None
        repo = kbs[0] if len(kbs) == 1 else None
    if repo is None or read_marker(repo / MARKER).get("lab") == "off":
        return None
    return repo


def session_of(row):
    try:
        return json.loads(row).get("session")
    except (json.JSONDecodeError, AttributeError):
        return None


def write_rows(repo, digests):
    """Строки выжимок в файл машины: та же сессия — строка заменяется; под блокировкой — хуки двух сессий."""
    path = repo / SESSIONS / f"{machine()}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    fresh = {d["session"]: json.dumps({"v": d["v"], "machine": machine(), **d}, ensure_ascii=False)
             for d in digests}
    with open(path, "a+", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        rows = [r for r in f.read().splitlines() if r.strip() and session_of(r) not in fresh]
        f.seek(0)
        f.truncate()
        f.write("".join(r + "\n" for r in [*rows, *fresh.values()]))


def known_sessions(repo):
    path = repo / SESSIONS / f"{machine()}.jsonl"
    if not path.is_file():
        return set()
    return {session_of(r) for r in path.read_text(encoding="utf-8").splitlines()}


def record(transcript, cwd=None):
    d = digest(transcript)
    # Папка старта сессии (первый `cwd` транскрипта), а не где она кончилась: из корня агент делает
    # `cd <папка роли>` — иначе выжимка ушла бы в неё, а `catch-up` из корня записал бы сессию второй раз.
    repo = lab_repo(d["cwd"] or cwd or ".")
    if repo is not None:
        write_rows(repo, [d])


def catch_up(folder, cwd, skip=None):
    repo = lab_repo(cwd)
    if repo is None:
        return
    known = known_sessions(repo)
    missed = [p for p in sorted(Path(folder).glob("*.jsonl")) if p.stem not in known and p.stem != skip]
    if missed:
        owners = uuid_owners(folder)  # одна проходка по папке на все пропущенные
        write_rows(repo, [digest(p, owners) for p in missed])


def hook(event):
    """Хук плагина: разобрать вход, решить, QA-проект ли, и отдать работу фону. Молча и всегда код 0."""
    try:
        data = json.loads(sys.stdin.read() or "{}")
        path, cwd = data.get("transcript_path"), data.get("cwd")
        if not isinstance(path, str) or not isinstance(cwd, str) or lab_repo(cwd) is None:
            return
        if event == "end":
            args = ["record", path, "--cwd", cwd]
        else:
            args = ["catch-up", str(Path(path).parent), "--cwd", cwd, "--skip", str(data.get("session_id") or "")]
        with open(LOG, "a", encoding="utf-8") as log:
            subprocess.Popen([sys.executable, str(Path(__file__).resolve()), *args], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=log, start_new_session=True)
    except Exception as e:  # noqa: BLE001 — хук не должен ни падать, ни печатать
        try:
            with open(LOG, "a", encoding="utf-8") as log:
                log.write(f"qa-lab hook-{event}: {e!r}\n")
        except OSError:
            pass


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_digest = sub.add_parser("digest", help="выжимка одной сессии — строка JSON")
    p_digest.add_argument("transcript")
    p_record = sub.add_parser("record", help="выжимку сессии — в файл репо проекта")
    p_record.add_argument("transcript")
    p_record.add_argument("--cwd", help="папка сессии (иначе — из транскрипта)")
    p_catch = sub.add_parser("catch-up", help="записать сессии папки, которых нет в файле")
    p_catch.add_argument("folder")
    p_catch.add_argument("--cwd", required=True)
    p_catch.add_argument("--skip", help="идущая сессия — её запишет свой SessionEnd")
    sub.add_parser("hook-end", help="хук SessionEnd: record в фоне")
    sub.add_parser("hook-start", help="хук SessionStart: catch-up в фоне")
    args = parser.parse_args()
    if args.cmd in ("hook-end", "hook-start"):
        hook(args.cmd[5:])
        return 0
    try:
        if args.cmd == "digest":
            print(json.dumps(digest(args.transcript), ensure_ascii=False))
        elif args.cmd == "record":
            record(args.transcript, args.cwd)
        else:
            catch_up(args.folder, args.cwd, args.skip)
    except OSError as e:
        print(f"qa-lab: {e}", file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    sys.exit(main())
