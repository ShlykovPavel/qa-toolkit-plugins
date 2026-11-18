#!/usr/bin/env python3
"""Аудит тестовых ключей Flutter-приложения: видны ли они нативному Appium.

Отвечает на три вопроса по репозиторию мобильного приложения:
  1. Какие ключи объявлены в реестре (AppKeys), но нигде не применены —
     то есть локатора в приложении по факту нет.
  2. Как применяются применённые: ValueKey (Appium НЕ видит) или
     Semantics(identifier:) (видит).
  3. Какие ключи из документа-договорённости с тестировщиками не имеют
     соответствия в коде.

Путь к репозиторию приложения — аргументом или через env MOBILE_REPO
(см. docs/apps-repos.md). Скрипт только читает.

Использование:
    python3 ${CLAUDE_PLUGIN_ROOT}/bin/mobile_keys_audit.py --repo ~/work_repos/mobile-app
    python3 ${CLAUDE_PLUGIN_ROOT}/bin/mobile_keys_audit.py --repo <путь> --format md > out.md
"""
import argparse
import collections
import os
import pathlib
import re
import sys

DEFAULT_KEYS_FILE = "lib/src/core/resources/app_keys.dart"
DEFAULT_DOC = "key_from_autotest.md"
DEFAULT_SCAN = "lib,packages"
MIN_PREFIX = 8  # ниже этой длины префиксное совпадение недостоверно


def parse_registry(text):
    """{имя dart-константы: значение ключа} из класса-реестра AppKeys."""
    # необязательный явный тип: `static const String foo = '...'` тоже ключ
    consts = dict(
        re.findall(r"static const (?:\w+\s+)?(\w+)\s*=\s*'([^']*)'", text)
    )
    funcs = dict(
        re.findall(
            r"static String\??\s+(\w+)\([^)]*\)\s*=>\s*\n?\s*'([^']*)'", text
        )
    )
    return consts, funcs


WINDOW = 4  # строк выше места применения


def usage_form(lines, index):
    """Как ключ навешен на виджет — по окну строк выше места применения.

    Эвристика: обёртка (`Semantics(`, `key: ValueKey(`) стоит выше по дереву,
    иногда через перенос параметров и комментарии. Окно в одну строку давало
    ложные вердикты, поэтому смотрим WINDOW строк и возвращаем ещё и
    расстояние — по нему видно, насколько вердикт надёжен.
    """
    for distance in range(0, WINDOW + 1):
        line = lines[index - distance] if index - distance >= 0 else ""
        if "identifier:" in line:
            return "semantics", distance
        if "ValueKey" in line or re.search(r"\bKey\(", line):
            return "valuekey", distance
    return "unknown", -1


def scan_sources(roots, registry, keys_file):
    """Проходит все дерева исходников и считает применение ключей.

    Применение считается ТОЛЬКО по `AppKeys.<имя>`. Совпадение по строковому
    литералу отдаётся отдельным списком-подсказкой, а не засчитывается: слово
    вроде `demands` встречается и как путь роута, и как имя фичи, и выдало бы
    ложное «ключ живой».
    """
    dart = []
    for root in roots:
        if root.is_dir():
            dart += [p for p in root.rglob("*.dart") if p.is_file()]
    texts = {p: p.read_text(encoding="utf-8", errors="replace") for p in dart}
    blob = "\n".join(t for p, t in texts.items() if p != keys_file)

    used = {}
    literal_only = []
    for name, value in registry.items():
        by_name = len(re.findall(r"AppKeys\.%s\b" % re.escape(name), blob))
        # значения-генераторы содержат интерполяцию — литералом их не ищем
        by_literal = 0
        if "$" not in value:
            by_literal = len(re.findall(r"['\"]%s['\"]" % re.escape(value), blob))
        used[name] = by_name
        if not by_name and by_literal:
            literal_only.append(name)

    forms = collections.Counter()
    weak = 0
    unknown_sites = []
    for path, text in texts.items():
        if path == keys_file:
            continue
        lines = text.splitlines()
        for lineno, line in enumerate(lines):
            for match in re.finditer(r"AppKeys\.(\w+)", line):
                if match.group(1) == "_":  # приватный конструктор реестра
                    continue
                form, distance = usage_form(lines, lineno)
                forms[form] += 1
                if form != "unknown" and distance > 0:
                    weak += 1
                if form == "unknown":
                    unknown_sites.append(f"{path}:{lineno + 1}")
    return used, forms, weak, unknown_sites, literal_only, len(dart)


def normalize(value):
    """Подчёркивания в markdown-документе местами съедены курсивом."""
    return value.replace("*", "_").replace("\\", "").strip()


def doc_gaps(doc_text, code_values):
    doc_keys = set(re.findall(r"`([^`]+)`", doc_text))
    code_norm = {normalize(v) for v in code_values}
    gaps = []
    for key in sorted(doc_keys):
        norm = normalize(key)
        if norm in code_norm:
            continue
        base = norm.split("$")[0].split("(")[0].rstrip("_")
        # короткая база схлопывает разные ключи в один (`need_(id)` -> `need`
        # совпало бы с `needs_navbar`) — считаем совпадением только длинную
        if len(base) >= MIN_PREFIX and any(v.startswith(base) for v in code_norm):
            continue
        gaps.append(key)
    return doc_keys, gaps


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        default=os.getenv("MOBILE_REPO", ""),
        help="корень репозитория мобильного приложения (или env MOBILE_REPO)",
    )
    parser.add_argument("--keys-file", default=DEFAULT_KEYS_FILE)
    parser.add_argument("--doc", default=DEFAULT_DOC)
    parser.add_argument(
        "--scan",
        default=DEFAULT_SCAN,
        help=f"каталоги исходников через запятую (по умолчанию {DEFAULT_SCAN})",
    )
    parser.add_argument("--format", choices=("text", "md"), default="text")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="вернуть 1, если есть мёртвые ключи или невидимые Appium формы",
    )
    args = parser.parse_args()

    if not args.repo:
        parser.error("укажи --repo или env MOBILE_REPO (см. docs/apps-repos.md)")
    root = pathlib.Path(args.repo).expanduser().resolve()
    keys_file = root / args.keys_file
    if not keys_file.is_file():
        parser.error(f"не найден реестр ключей: {keys_file}")

    consts, funcs = parse_registry(keys_file.read_text(encoding="utf-8"))
    registry = {**consts, **funcs}
    roots = [root / part.strip() for part in args.scan.split(",") if part.strip()]
    used, forms, weak, unknown_sites, literal_only, dart_count = scan_sources(
        roots, registry, keys_file
    )
    dead = sorted(n for n, count in used.items() if not count)

    doc_path = root / args.doc
    doc_keys, gaps = ((), []) if not doc_path.is_file() else doc_gaps(
        doc_path.read_text(encoding="utf-8"), registry.values()
    )

    bullet = "- " if args.format == "md" else "  "
    head = "## " if args.format == "md" else ""
    print(f"{head}Аудит тестовых ключей: {root.name}")
    print()
    print(f"{bullet}каталоги: {', '.join(str(r.relative_to(root)) for r in roots)}")
    print(f"{bullet}dart-файлов просмотрено: {dart_count}")
    print(f"{bullet}ключей в реестре: {len(registry)} "
          f"(константы {len(consts)}, генераторы по id {len(funcs)})")
    print(f"{bullet}применены в коде: {len(registry) - len(dead)}")
    print(f"{bullet}объявлены, но НЕ применены: {len(dead)}")
    print()
    print(f"{head}Форма применения")
    print()
    labels = {
        "valuekey": "ValueKey/Key — нативный Appium НЕ видит",
        "semantics": "Semantics(identifier:) — Appium видит",
        "unknown": "не распознано, проверить вручную",
    }
    for form, count in forms.most_common():
        print(f"{bullet}{count}: {labels[form]}")
    if weak:
        print(f"{bullet}из них {weak} опознаны по строке ВЫШЕ места применения — "
              f"вердикт эвристический, проверить глазами")
    if literal_only:
        print()
        print(f"{head}Значение встречается литералом — проверить глазами")
        print()
        print(f"{bullet}не доказательство применения: совпадение может быть "
              f"путём роута, именем фичи или текстом")
        for name in literal_only:
            print(f"{bullet}`{name}` = `{registry[name]}`")
    if unknown_sites:
        print()
        print(f"{head}Не распознанные места")
        print()
        for site in unknown_sites:
            print(f"{bullet}{os.path.relpath(site, root)}")
    if dead:
        print()
        print(f"{head}Ключи без локатора в приложении")
        print()
        for name in dead:
            print(f"{bullet}`{name}` = `{registry[name]}`")
    if doc_keys:
        print()
        print(f"{head}Расхождения с {args.doc}")
        print()
        print(f"{bullet}ключей в документе: {len(doc_keys)}, "
              f"без соответствия в реестре: {len(gaps)}")
        for key in gaps:
            print(f"{bullet}`{key}`")

    if not args.strict:
        return 0
    return 1 if (dead or forms.get("valuekey")) else 0


if __name__ == "__main__":
    sys.exit(main())
