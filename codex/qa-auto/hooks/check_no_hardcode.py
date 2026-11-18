#!/usr/bin/env python3
"""PreToolUse-хук: блокирует хардкод URL/паролей/токенов в коде тестов.

Контракт Claude Code hooks (сверен с официальной документацией 2026-07):
на stdin приходит JSON события Write/Edit; exit 2 + причина в stderr —
заблокировать вызов, exit 0 — пропустить. Подключение — hooks/hooks.json
плагина qa-auto, matcher "Write|Edit".

Хук молчит вне QA-проектов: корень проекта — ближайшая к файлу папка с
маркером .qa/project.yaml. Пути считаются от неё, а не от папки сессии —
сессия может стоять в папке над двумя репо.

Что блокируется (только в Tests/, src/, frontend/, Appium/):
- http(s)://-URL с хостом вне плейсхолдеров (localhost, 127.0.0.1,
  example.com/org); схемы file:// и data: легальны;
- литеральные секреты: password="...", api_key="...", Bearer <литерал>;
- запись файла .env (в любом месте QA-проекта; .env.example разрешён).

Что пропускается: строки с os.getenv/config., комментарии, файлы
с example_ в имени (эталоны упоминают паттерны в докстрингах),
значения из переменных (password=creds.pwd, f"Bearer {token}").

Границы механики: хук ловит редактирование агентом, а НЕ git commit.
Ошибки парсинга события — fail-open (exit 0): хук страхует, не ломает.
"""
import json
import os
import re
import sys

CODE_ROOTS = ("Tests", "src", "frontend", "Appium")
ALLOWED_HOSTS = {"localhost", "127.0.0.1"}
ALLOWED_HOST_SUFFIXES = ("example.com", "example.org")

URL_RE = re.compile(r"\bhttps?://([A-Za-z0-9.-]+)")
# password="..." / api_key: '...' — литеральное непустое значение в кавычках;
# {' внутри значения = f-string-интерполяция, это переменная, не литерал
SECRET_RE = re.compile(
    r"""(?i)\b(password|api[_-]?key)\b["']?\s*[=:]\s*["'][^"'{]+["']"""
)
# Bearer + голый литерал токена; f"Bearer {token}" не матчится ({ вне класса)
BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9._+/=-]{8,}")


MARKER = os.path.join(".qa", "project.yaml")


def _project_root(file_path: str, cwd: str) -> str:
    """Ближайшая к файлу папка с маркером QA-проекта; '' если маркера нет."""
    path = os.path.join(cwd or os.getcwd(), file_path)  # абсолютный file_path не меняется
    folder = os.path.dirname(os.path.abspath(path))
    while True:
        if os.path.isfile(os.path.join(folder, MARKER)):
            return folder
        parent = os.path.dirname(folder)
        if parent == folder:
            return ""
        folder = parent


def _host_allowed(host: str) -> bool:
    host = host.lower().rstrip(".")
    if host in ALLOWED_HOSTS:
        return True
    return any(
        host == suf or host.endswith("." + suf) for suf in ALLOWED_HOST_SUFFIXES
    )


def find_violations(rel_path: str, content: str) -> list:
    if "example_" in os.path.basename(rel_path):
        return []
    violations = []
    for lineno, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if "os.getenv" in line or "config." in line:
            continue
        for match in URL_RE.finditer(line):
            if not _host_allowed(match.group(1)):
                violations.append(
                    f"строка {lineno}: хардкод URL {match.group(0)} — "
                    f"вынеси в .env и читай через config.py (os.getenv)"
                )
        if SECRET_RE.search(line):
            violations.append(
                f"строка {lineno}: литеральный секрет ({stripped[:60]}…) — "
                f"пароли/ключи только из .env через config.py"
            )
        elif BEARER_RE.search(line):
            violations.append(
                f"строка {lineno}: литеральный Bearer-токен — токены выдаёт "
                f"auth-фикстура в HttpClient.access_folder, не хардкод"
            )
    return violations


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # fail-open: битое событие не должно ломать работу

    tool_input = event.get("tool_input") or {}
    file_path = tool_input.get("file_path") or ""
    if not file_path:
        return 0

    root = _project_root(file_path, event.get("cwd", ""))
    if not root:
        return 0  # не QA-проект — хук плагина молчит

    basename = os.path.basename(file_path)
    if basename == ".env":
        print(
            "Запись .env заблокирована: .env не редактируется агентом "
            "(секреты стенда). Новые переменные — в .env.example.",
            file=sys.stderr,
        )
        return 2

    rel_path = os.path.relpath(os.path.join(event.get("cwd", ""), file_path), root)
    if rel_path.split(os.sep, 1)[0] not in CODE_ROOTS:
        return 0

    # Write несёт content, Edit — new_string; проверяем только добавляемое
    content = tool_input.get("content") or tool_input.get("new_string") or ""
    if not content:
        return 0

    violations = find_violations(rel_path, content)
    if violations:
        print(
            f"Хардкод в {rel_path} (CLAUDE.md: «Never hardcode URLs, "
            f"passwords, API keys»):\n" + "\n".join(violations),
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
