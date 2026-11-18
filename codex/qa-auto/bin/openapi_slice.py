#!/usr/bin/env python3
"""Срез OpenAPI-спеки: компактный кусок под один ресурс вместо целой спеки.

Полная спека реального проекта в контекст агента не влезает, поэтому скиллы
всегда работают со срезом: выбранные операции (по тегу и/или подстроке пути)
плюс ТОЛЬКО те components, на которые эти операции транзитивно ссылаются
через $ref.

Спека принимается и JSON, и YAML (чтение — spec_loader.py рядом; для YAML
нужен PyYAML из requirements.txt).

Примеры:
    python3 ${CLAUDE_PLUGIN_ROOT}/bin/openapi_slice.py --spec swagger.json --list-tags
    python3 ${CLAUDE_PLUGIN_ROOT}/bin/openapi_slice.py --spec swagger.json --tag Contracts
    python3 ${CLAUDE_PLUGIN_ROOT}/bin/openapi_slice.py --spec https://stand/openapi.json \\
        --path /api/tasks --out slice.json
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spec_loader import SpecLoadError, load_spec  # noqa: E402

HTTP_METHODS = ("get", "post", "put", "patch", "delete", "head", "options", "trace")


def iter_operations(spec: dict):
    """Итерирует (путь, метод, операция, параметры уровня пути)."""
    for path, path_item in spec.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue
        path_level_params = path_item.get("parameters", [])
        for method in HTTP_METHODS:
            operation = path_item.get(method)
            if isinstance(operation, dict):
                yield path, method, operation, path_level_params


def list_tags(spec: dict) -> dict:
    """Считает операции по тегам: {тег: число операций}."""
    counts = {}
    for _path, _method, operation, _params in iter_operations(spec):
        for tag in operation.get("tags") or ["<без тега>"]:
            counts[tag] = counts.get(tag, 0) + 1
    return counts


def collect_ref_strings(node, acc: set):
    """Рекурсивно собирает значения всех "$ref" внутри узла."""
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            acc.add(ref)
        for value in node.values():
            collect_ref_strings(value, acc)
    elif isinstance(node, list):
        for item in node:
            collect_ref_strings(item, acc)


def resolve_components(spec: dict, seed_refs: set) -> dict:
    """Транзитивно разрешает $ref в components (schema → schema → ...).

    Возвращает {секция: {имя: определение}} только для реально используемых
    компонентов. Посещённые ссылки запоминаются — циклические схемы
    (Task.subtasks → Task) не зацикливают обход.
    """
    components = spec.get("components", {})
    resolved = {}
    visited = set()
    queue = list(seed_refs)
    while queue:
        ref = queue.pop()
        if ref in visited:
            continue
        visited.add(ref)
        parts = ref.split("/")  # "#/components/schemas/Contract"
        if len(parts) != 4 or parts[0] != "#" or parts[1] != "components":
            print(f"ПРЕДУПРЕЖДЕНИЕ: пропущен нестандартный $ref: {ref}",
                  file=sys.stderr)
            continue
        section, name = parts[2], parts[3]
        definition = components.get(section, {}).get(name)
        if definition is None:
            print(f"ПРЕДУПРЕЖДЕНИЕ: $ref не найден в components: {ref}",
                  file=sys.stderr)
            continue
        resolved.setdefault(section, {})[name] = definition
        nested = set()
        collect_ref_strings(definition, nested)
        queue.extend(nested - visited)
    return resolved


def build_slice(spec: dict, tags: list, path_substrings: list) -> dict:
    """Собирает срез: операции, попавшие под фильтры, + их components."""
    operations = []
    refs = set()
    for path, method, operation, path_level_params in iter_operations(spec):
        by_tag = bool(set(operation.get("tags", [])) & set(tags))
        by_path = any(sub in path for sub in path_substrings)
        if not (by_tag or by_path):
            continue
        entry = {
            "method": method.upper(),
            "path": path,
            "tags": operation.get("tags", []),
        }
        for field in ("summary", "description", "operationId", "security",
                      "requestBody", "responses", "deprecated"):
            if field in operation:
                entry[field] = operation[field]
        merged_params = path_level_params + operation.get("parameters", [])
        if merged_params:
            entry["parameters"] = merged_params
        operations.append(entry)
        collect_ref_strings(entry, refs)
    return {
        "info": {key: spec.get("info", {}).get(key)
                 for key in ("title", "version") if spec.get("info", {}).get(key)},
        "servers": spec.get("servers", []),
        "selected_by": {"tags": tags, "path_substrings": path_substrings},
        "operations": operations,
        "components": resolve_components(spec, refs),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Компактный срез OpenAPI-спеки по тегу или подстроке пути. "
                    "Сначала посмотри теги (--list-tags), потом режь (--tag/--path).")
    parser.add_argument("--spec", required=True,
                        help="Путь к файлу спеки или URL (http/https)")
    parser.add_argument("--list-tags", action="store_true",
                        help="Показать теги и число операций в каждом")
    parser.add_argument("--tag", action="append", default=[],
                        help="Тег для среза (можно указывать несколько раз)")
    parser.add_argument("--path", action="append", default=[],
                        help="Подстрока пути для среза (можно несколько раз)")
    parser.add_argument("--out", help="Записать срез в файл вместо stdout")
    args = parser.parse_args()

    try:
        spec = load_spec(args.spec)
    except SpecLoadError as error:
        print(f"ОШИБКА: {error}", file=sys.stderr)
        return 1

    if args.list_tags:
        counts = list_tags(spec)
        for tag, count in sorted(counts.items(), key=lambda item: -item[1]):
            print(f"{tag}: {count}")
        return 0

    if not args.tag and not args.path:
        parser.error("нужен --list-tags, --tag или --path")

    slice_data = build_slice(spec, args.tag, args.path)
    if not slice_data["operations"]:
        available = ", ".join(sorted(list_tags(spec)))
        print(f"ОШИБКА: под фильтры не попала ни одна операция. "
              f"Доступные теги: {available}", file=sys.stderr)
        return 1

    output = json.dumps(slice_data, ensure_ascii=False, indent=2)
    if args.out:
        # Директория срезов (_specs/) в .gitignore, поэтому в свежем форке
        # её нет — создаём, а не падаем FileNotFoundError.
        parent = os.path.dirname(os.path.abspath(args.out))
        os.makedirs(parent, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as out_file:
            out_file.write(output + "\n")
        print(f"Срез записан: {args.out} "
              f"({len(slice_data['operations'])} операций)", file=sys.stderr)
    else:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
