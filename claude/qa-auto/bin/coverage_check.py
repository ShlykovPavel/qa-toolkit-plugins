#!/usr/bin/env python3
"""Сверка покрытия: теги OpenAPI-спеки против пакетов API-клиентов в src/.

Зачем: при десятках доменов «все покрыты» нельзя проверять пересчётом
руками — домен теряется молча, а паспорт продолжает заявлять полноту.
Скрипт сравнивает список тегов спеки со списком доменных пакетов и падает
(exit code 1), если у какого-то тега нет клиента.

Имена нормализуются (регистр, дефисы/подчёркивания игнорируются), поэтому
тег `text-unit-categories` совпадает с пакетом `text_unit_categories`.

Спека принимается и JSON, и YAML (чтение — spec_loader.py рядом; для YAML
нужен PyYAML из requirements.txt).

Примеры:
    python3 ${CLAUDE_PLUGIN_ROOT}/bin/coverage_check.py --spec specs/admin.swagger.json --package src/admin
    python3 ${CLAUDE_PLUGIN_ROOT}/bin/coverage_check.py --spec https://stand/openapi.json \\
        --package src/api --ignore health --ignore internal

`--ignore <тег>` — теги, которые сознательно не покрываются клиентами
(служебные health/metrics, авторизация, живущая в src/auth.py, и т.п.);
каждый ignore должен быть осознанным решением, зафиксированным в паспорте.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spec_loader import SpecLoadError, load_spec  # noqa: E402

HTTP_METHODS = ("get", "post", "put", "patch", "delete", "head", "options", "trace")


def normalize(name: str) -> str:
    """Нормализует имя для сравнения: регистр и разделители не значимы."""
    return name.lower().replace("-", "").replace("_", "")


def spec_tags(spec: dict) -> dict:
    """Собирает теги операций спеки: {нормализованное имя: исходный тег}."""
    tags = {}
    for path_item in spec.get("paths", {}).values():
        if not isinstance(path_item, dict):
            continue
        for method in HTTP_METHODS:
            operation = path_item.get(method)
            if isinstance(operation, dict):
                for tag in operation.get("tags") or []:
                    tags[normalize(tag)] = tag
    return tags


def package_domains(package_dir: str) -> dict:
    """Собирает доменные пакеты: {нормализованное имя: имя директории}.

    Доменом считается поддиректория с .py-файлами. Служебные и example-
    директории пропускаются: они не являются клиентами доменов спеки.
    """
    domains = {}
    for entry in sorted(os.listdir(package_dir)):
        full = os.path.join(package_dir, entry)
        if not os.path.isdir(full):
            continue
        if entry == "__pycache__" or entry.startswith("example_"):
            continue
        if not any(name.endswith(".py") for name in os.listdir(full)):
            continue
        domains[normalize(entry)] = entry
    return domains


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Сверяет теги OpenAPI-спеки с пакетами API-клиентов.")
    parser.add_argument("--spec", required=True,
                        help="путь к JSON-спеке или URL")
    parser.add_argument("--package", required=True,
                        help="директория доменных пакетов, напр. src/admin")
    parser.add_argument("--ignore", action="append", default=[],
                        help="тег, сознательно не покрываемый клиентом "
                             "(можно повторять)")
    args = parser.parse_args()

    try:
        spec = load_spec(args.spec)
    except SpecLoadError as error:
        print(f"ОШИБКА: {error}")
        return 1
    tags = spec_tags(spec)
    ignored = {normalize(tag) for tag in args.ignore}
    domains = package_domains(args.package)

    missing = sorted(tags[key] for key in tags
                     if key not in domains and key not in ignored)
    orphans = sorted(domains[key] for key in domains if key not in tags)
    covered = sum(1 for key in tags if key in domains)

    print(f"Спека: {args.spec} — тегов: {len(tags)}"
          + (f" (игнорируется: {len(ignored)})" if ignored else ""))
    print(f"Пакет: {args.package} — доменов: {len(domains)}, покрыто тегов: {covered}")

    if orphans:
        # Не ошибка: пакет мог остаться от старой версии спеки — но это
        # повод посмотреть, не переименовали ли тег.
        print(f"ВНИМАНИЕ — пакеты без тега в спеке: {', '.join(orphans)}")

    if missing:
        print(f"НЕ ПОКРЫТО — теги без клиента: {', '.join(missing)}")
        return 1

    print("OK — все теги спеки покрыты клиентами.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
