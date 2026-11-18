#!/usr/bin/env python3
"""check_no_sleep.py — гейт make verify: слепые паузы в тестовом слое.

Зачем. Запрет `time.sleep` записан в трёх местах (`.claude/rules/tests.md`,
`docs/tests.md`, чеклист экрана `/mobile-tests`), но держится на дисциплине:
агент переносит паузы из отладочных скриптов в модуль, живой прогон зелёный,
и ничто механическое нарушение не ловит. Правило, которое держится на
дисциплине, лечится проверкой, а не ещё одним напоминанием.

Что ищет (по AST, упоминания в докстрингах и комментариях не считаются):
  * `time.sleep(...)` / `asyncio.sleep(...)`, включая `import time as t`;
  * `sleep(...)`, импортированный `from time|asyncio import sleep [as x]`;
  * `<что угодно>.wait_for_timeout(...)` — слепая пауза Playwright.

Где: `Tests/`, `src/` и код слоёв UI (список — SCOPE ниже).
Исключения — инфраструктура, где пауза и есть реализация ожидания:
`src/wait_utils.py` (сам поллинг).
# слой: mobile
`Appium/Simulator/` и `Appium/Appium_launcher/` (опрос загрузки эмулятора)
в скоуп не входят.
# /слой
Замена паузе — `wait_until()` из `src/wait_utils.py`.

    python3 scripts/check_no_sleep.py            # exit 0 — чисто, 1 — найдено
    python3 scripts/check_no_sleep.py --root DIR # для тестов

Тесты: `.venv/bin/python -m pytest scripts/test_check_no_sleep.py -q`
(правишь скрипт — сначала тест).
"""
import argparse
import ast
import sys
from pathlib import Path

SCOPE = (
    "Tests",
    "src",
    # слой: frontend
    "frontend",
    # /слой
    # слой: mobile
    "Appium/app_keys",
    "Appium/Modules",
    # /слой
)
EXCLUDED = {"src/wait_utils.py"}
SLEEP_MODULES = {"time", "asyncio"}
SKIP_DIRS = {"__pycache__", ".venv", "node_modules"}


def find_blind_waits(source: str) -> list[tuple[int, str]]:
    """Вернуть [(строка, что найдено)] для слепых пауз в исходнике."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []  # синтаксис ловит compileall в той же цели verify

    module_aliases: dict[str, str] = {}  # локальное имя -> time/asyncio
    sleep_aliases: dict[str, str] = {}   # локальное имя -> time.sleep
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in SLEEP_MODULES:
                    module_aliases[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module in SLEEP_MODULES:
            for alias in node.names:
                if alias.name == "sleep":
                    sleep_aliases[alias.asname or "sleep"] = f"{node.module}.sleep"

    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            if func.attr == "wait_for_timeout":
                found.append((node.lineno, "wait_for_timeout"))
            elif (func.attr == "sleep" and isinstance(func.value, ast.Name)
                  and func.value.id in module_aliases):
                found.append((node.lineno, f"{module_aliases[func.value.id]}.sleep"))
        elif isinstance(func, ast.Name) and func.id in sleep_aliases:
            found.append((node.lineno, sleep_aliases[func.id]))
    return sorted(found)


def iter_files(root: Path):
    for part in SCOPE:
        base = root / part
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            if SKIP_DIRS.intersection(path.parts):
                continue
            rel = path.relative_to(root).as_posix()
            if rel not in EXCLUDED:
                yield rel, path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    root = Path(parser.parse_args().root)

    hits = []
    for rel, path in iter_files(root):
        for line, what in find_blind_waits(path.read_text(encoding="utf-8")):
            hits.append(f"{rel}:{line}: {what}")

    if hits:
        print("Слепые паузы в тестовом слое — замени на wait_until() из src/wait_utils.py:")
        print("\n".join(f"  {h}" for h in hits))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
