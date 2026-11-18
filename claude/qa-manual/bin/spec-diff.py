#!/usr/bin/env python3
"""Сверка снапшота OpenAPI с живой спецификацией.

Шаг 4 флоу: пока не известно, что снапшот совпадает с живым контрактом, вывод
«поля нет, значит не сделано» недоказуем.

    python3 spec-diff.py snapshot.json https://api.example.test/swagger/v1/swagger.json
    python3 spec-diff.py snapshot.json <url> --insecure
    python3 spec-diff.py snapshot.json <url> --schema RegisterRequest

Живая спека тянется через curl, а не через urllib: локальный Python может не иметь
корневых сертификатов, и тогда падает не проверка, а сам инструмент проверки.

Код возврата: 0 — расхождений нет, 1 — расхождения есть, 2 — не смог получить спеку.
"""

import argparse
import json
import subprocess
import sys


def fetch(url, insecure):
    cmd = ["curl", "-sS", "--fail", "--max-time", "60", url]
    if insecure:
        cmd.insert(1, "-k")
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    except FileNotFoundError:
        print("ОШИБКА: curl не найден в PATH", file=sys.stderr)
        sys.exit(2)
    except subprocess.CalledProcessError as exc:
        print("ОШИБКА: не удалось получить спеку: %s" % (exc.stderr or "").strip(), file=sys.stderr)
        sys.exit(2)
    try:
        return json.loads(out)
    except json.JSONDecodeError as exc:
        print("ОШИБКА: ответ не JSON (%s). Первые 200 символов: %s" % (exc, out[:200]), file=sys.stderr)
        sys.exit(2)


def load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except OSError as exc:
        print("ОШИБКА: не читается снапшот %s: %s" % (path, exc), file=sys.stderr)
        sys.exit(2)


def schemas(spec):
    return (spec.get("components") or {}).get("schemas") or spec.get("definitions") or {}


def props(schema):
    return sorted((schema.get("properties") or {}).keys())


def diff_sets(old, new):
    return sorted(set(new) - set(old)), sorted(set(old) - set(new))


def report_block(title, added, removed, limit):
    lines = []
    if added:
        lines.append("  добавлено в живой (%d): %s" % (len(added), ", ".join(added[:limit])))
        if len(added) > limit:
            lines.append("    ... ещё %d" % (len(added) - limit))
    if removed:
        lines.append("  пропало в живом (%d): %s" % (len(removed), ", ".join(removed[:limit])))
        if len(removed) > limit:
            lines.append("    ... ещё %d" % (len(removed) - limit))
    if lines:
        return ["%s:" % title] + lines
    return []


def main():
    ap = argparse.ArgumentParser(description="Сверка снапшота OpenAPI с живой спецификацией")
    ap.add_argument("snapshot", help="путь к файлу снапшота")
    ap.add_argument("url", help="адрес живой спеки")
    ap.add_argument("--insecure", action="store_true", help="не проверять сертификат стенда")
    ap.add_argument("--schema", action="append", default=[],
                    help="показать поля конкретной схемы целиком (можно несколько раз)")
    ap.add_argument("--limit", type=int, default=15, help="сколько имён печатать в списке")
    args = ap.parse_args()

    snap = load(args.snapshot)
    live = fetch(args.url, args.insecure)

    snap_paths, live_paths = snap.get("paths") or {}, live.get("paths") or {}
    snap_schemas, live_schemas = schemas(snap), schemas(live)

    out = []
    out.append("Снапшот: %s — путей %d, схем %d" % (args.snapshot, len(snap_paths), len(snap_schemas)))
    out.append("Живая:   %s — путей %d, схем %d" % (args.url, len(live_paths), len(live_schemas)))

    p_add, p_del = diff_sets(snap_paths, live_paths)
    s_add, s_del = diff_sets(snap_schemas, live_schemas)

    changed = {}
    for name in sorted(set(snap_schemas) & set(live_schemas)):
        a, d = diff_sets(props(snap_schemas[name]), props(live_schemas[name]))
        if a or d:
            changed[name] = (a, d)

    out += report_block("Пути", p_add, p_del, args.limit)
    out += report_block("Схемы", s_add, s_del, args.limit)

    if changed:
        out.append("Поля изменились в %d схемах:" % len(changed))
        for name, (a, d) in list(changed.items())[:args.limit]:
            bits = []
            if a:
                bits.append("+ " + ", ".join(a))
            if d:
                bits.append("- " + ", ".join(d))
            out.append("  %s: %s" % (name, "; ".join(bits)))
        if len(changed) > args.limit:
            out.append("  ... ещё %d схем" % (len(changed) - args.limit))

    for name in args.schema:
        for label, src in (("снапшот", snap_schemas), ("живая", live_schemas)):
            body = src.get(name)
            out.append("Схема %s (%s): %s" % (name, label,
                                              ", ".join(props(body)) if body else "НЕТ В СПЕКЕ"))

    has_diff = bool(p_add or p_del or s_add or s_del or changed)
    out.append("")
    if has_diff:
        out.append("РАСХОЖДЕНИЯ ЕСТЬ. Выводы «поля нет, значит не сделано» пока недоказуемы:")
        out.append("сначала разберись с расхождением — обнови снапшот или объясни разницу.")
    else:
        out.append("РАСХОЖДЕНИЙ НЕТ. Контракт можно читать по снапшоту, не дёргая стенд.")

    print("\n".join(out))
    sys.exit(1 if has_diff else 0)


if __name__ == "__main__":
    main()
