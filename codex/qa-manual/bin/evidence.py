#!/usr/bin/env python3
"""Сырьё прогона в едином виде: импорт, прогон, аудит объёма выборки, мутационная проба.

Формат `evidence.json` и правила описаны в references/runner-contract.md.

    # 1. привести отчёт раннера к единому виду
    python3 evidence.py import --runner bruno --report run.json -o evidence.json

    # 1'. либо выполнить запросы самому, когда машинного отчёта нет
    python3 evidence.py run --runner curl --requests requests.json -o evidence.json

    # 2. объём выборки, вакуумные кандидаты, пишущие запросы
    python3 evidence.py audit evidence.json

    # 3. мутационная проба: тот же набор на заведомо пустой выборке
    python3 evidence.py vacuum --baseline evidence.json --requests requests.json \
        --query from=2099-01-01 --query status=Rejected -o vacuum.json
    python3 evidence.py vacuum --baseline evidence.json --runner bruno \
        --cmd 'bru run "<Папка коллекции>" --env dev --env-var from=2099-01-01 -r --reporter-json empty.json' \
        --report empty.json -o vacuum.json

    # 4. строка стоимости захода для раздела «Метод» отчёта
    python3 evidence.py cost evidence.json vacuum.json --dir <каталог захода>

Только стандартная библиотека. Внешние запросы — через curl, чтобы отсутствие корневых
сертификатов у локального Python не ломало сам инструмент проверки.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

CASE_RE = re.compile(r"\bTC-\d+\b")
READ_METHODS = {"GET", "HEAD", "OPTIONS"}
TOTAL_KEYS = {"totalcount", "total", "count", "totalitems", "totalelements", "totalrecords"}


# ---------------------------------------------------------------- утилиты

def die(msg):
    print("ОШИБКА: %s" % msg, file=sys.stderr)
    sys.exit(2)


def load_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except OSError as exc:
        die("не читается %s: %s" % (path, exc))
    except json.JSONDecodeError as exc:
        die("%s не является JSON: %s" % (path, exc))


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)


# Сколько элементов списка обходим вглубь при подсчёте вложенных массивов.
SAMPLE_CAP = 25


def count_collections(body, prefix="", depth=0, acc=None):
    """Длина каждого массива в ответе: основа подсчёта объёма выборки.

    Внутрь элементов списка тоже заходим и суммируем: контейнер бывает непуст, а всё
    содержимое в нём пусто. Именно так «15 категорий» скрывали ноль элементов в каждой.
    """
    if acc is None:
        acc = {}
    if depth > 4 or len(acc) > 40:
        return acc
    if isinstance(body, dict):
        for key, value in body.items():
            path = "%s.%s" % (prefix, key) if prefix else key
            if isinstance(value, list):
                walk_list(value, path, depth, acc)
            elif isinstance(value, dict):
                count_collections(value, path, depth + 1, acc)
    elif isinstance(body, list):
        walk_list(body, prefix or "$", depth, acc)
    return acc


def walk_list(value, path, depth, acc):
    """Накапливает длину массива и длины вложенных в его элементы массивов.

    Складывать обязательно: у соседних элементов списка путь вложенного массива один и тот
    же (`categories[].items`), и присваивание оставило бы счёт последнего элемента вместо
    суммы. Замерено: 15 категорий с 14 вложенными элементами давали `items: 0`,
    потому что последняя категория пуста.
    """
    acc[path] = acc.get(path, 0) + len(value)
    for item in value[:SAMPLE_CAP]:
        if isinstance(item, dict):
            count_collections(item, path + "[]", depth + 1, acc)
    if len(value) > SAMPLE_CAP:
        # Вложенные счётчики под этим путём посчитаны не по всем элементам — говорим вслух,
        # иначе частичная сумма читается как полная.
        acc["~notCounted." + path] = len(value) - SAMPLE_CAP
    return acc


def find_total(body, depth=0):
    if depth > 3 or not isinstance(body, dict):
        return None
    for key, value in body.items():
        if key.lower() in TOTAL_KEYS and isinstance(value, bool) is False and isinstance(value, int):
            return value
    for value in body.values():
        if isinstance(value, dict):
            found = find_total(value, depth + 1)
            if found is not None:
                return found
    return None


def find_case(*texts):
    for text in texts:
        if not text:
            continue
        found = CASE_RE.search(str(text))
        if found:
            return found.group(0)
    return None


def bodies_path(out_path):
    base = os.path.dirname(os.path.abspath(out_path)) or "."
    # Мутационный прогон складывает тела отдельно: номера запросов у него те же, и при общем
    # каталоге пустые мутированные ответы молча ложились поверх baseline.
    stem = "bodies-mutated" if os.path.basename(out_path).endswith(".mutated.json") else "bodies"
    return os.path.join(base, stem)


def bodies_dir(out_path):
    path = bodies_path(out_path)
    os.makedirs(path, exist_ok=True)
    return path


def require_free_bodies(out_path, asked=None):
    """Отказ, если каталог тел уже занят прошлым прогоном.

    Тела нумеруются по порядку запросов, поэтому второй прогон в тот же каталог клал 001.json
    поверх первого молча, а сырьё первого продолжало на него ссылаться. Правило текстом
    («проверь каталог перед вызовом») повторно нарушалось на живых заходах, поэтому проверяет
    скрипт — до первого запроса и до запуска раннера. `asked` — путь -o, каким его дал
    человек, если тела лягут рядом с производным от него файлом (vacuum).
    """
    path = bodies_path(out_path)
    taken = os.listdir(path) if os.path.isdir(path) else []
    if not taken:
        return
    asked = asked or out_path
    base = os.path.dirname(asked)
    number = 2
    while os.path.exists(os.path.join(base, "progon-%d" % number)):
        number += 1
    die("каталог тел %s занят прошлым прогоном (файлов: %d) — новый прогон лёг бы поверх, "
        "и сырьё прошлого ссылалось бы на чужие тела. Ничего не выполнено. "
        "Каждому прогону — свой каталог: -o %s"
        % (path, len(taken), os.path.join(base, "progon-%d" % number, os.path.basename(asked))))


def write_body(out_path, index, body, raw_text):
    directory = bodies_dir(out_path)
    name = "%03d.json" % index
    full = os.path.join(directory, name)
    with open(full, "w", encoding="utf-8") as fh:
        if body is not None:
            json.dump(body, fh, ensure_ascii=False, indent=1)
        else:
            fh.write(raw_text or "")
    # Записываем тот каталог, в который реально положили: зашитое "bodies" уводило читателя
    # мутированного сырья на тело baseline — то есть ровно туда, откуда разводили каталоги.
    return os.path.join(os.path.basename(directory), name)


def make_record(index, out_path, name, case, role, method, url, status, body, raw_text,
                assertions, observed_at=None):
    method = (method or "GET").upper()
    counts = count_collections(body) if isinstance(body, (dict, list)) else {}
    return {
        "name": name,
        "case": case,
        "role": role,
        "method": method,
        "url": url,
        "status": status,
        # Момент наблюдения. Заполняется там, где запрос выполнял сам скрипт (run); при
        # импорте чужого отчёта остаётся null: время прогона знает раннер, а не импорт, и
        # подставлять сюда время импорта значит выдавать одно за другое.
        "observedAt": observed_at,
        "writing": method not in READ_METHODS,
        "bodyPath": write_body(out_path, index, body, raw_text),
        "counts": counts,
        "totalCount": find_total(body) if isinstance(body, dict) else None,
        "assertions": assertions,
    }


def totals(requests):
    flat = [a for r in requests for a in r["assertions"]]
    return {
        "requests": len(requests),
        "assertions": len(flat),
        "passed": sum(1 for a in flat if a["status"] == "pass"),
        "failed": sum(1 for a in flat if a["status"] != "pass"),
        "writing": sum(1 for r in requests if r["writing"]),
    }


# ---------------------------------------------------------------- import

def runner_results(report):
    """Плоский список результатов из отчёта CLI-раннера. Терпим к форме отчёта."""
    if isinstance(report, dict):
        if isinstance(report.get("results"), list):
            return report["results"]
        for key in ("iterations", "runs"):
            if isinstance(report.get(key), list):
                return [r for it in report[key] for r in (it.get("results") or [])]
        die("незнакомая форма отчёта, ключи верхнего уровня: %s" % ", ".join(sorted(report)))
    if isinstance(report, list):
        if report and isinstance(report[0], dict) and isinstance(report[0].get("results"), list):
            return [r for it in report for r in (it.get("results") or [])]
        return report
    die("отчёт не объект и не список")


def normalize_assertions(result):
    out = []
    for item in result.get("assertionResults") or []:
        name = " ".join(str(item.get(k, "")) for k in ("lhsExpr", "operator", "rhsExpr")).strip()
        out.append({
            "name": name or "assertion",
            "status": "pass" if item.get("status") == "pass" else "fail",
            "message": str(item.get("error") or ""),
        })
    for item in result.get("testResults") or []:
        out.append({
            "name": str(item.get("description") or "test"),
            "status": "pass" if item.get("status") == "pass" else "fail",
            "message": str(item.get("error") or ""),
        })
    return out


def cmd_import(args):
    report = load_json(args.report)
    results = runner_results(report)
    if not results:
        die("в отчёте ноль результатов — прогон не состоялся или отчёт не тот")
    require_free_bodies(args.output)

    requests = []
    for index, result in enumerate(results, 1):
        request = result.get("request") or {}
        response = result.get("response") or {}
        test = result.get("test") or {}
        name = (test.get("filename") or result.get("suitename") or result.get("name")
                or request.get("url") or "request %d" % index)
        body = response.get("data")
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except json.JSONDecodeError:
                pass
        assertions = normalize_assertions(result)
        requests.append(make_record(
            index, args.output, str(name),
            find_case(name, result.get("suitename"), *[a["name"] for a in assertions]),
            args.role, request.get("method"), request.get("url"),
            response.get("status"), body if isinstance(body, (dict, list)) else None,
            body if isinstance(body, str) else None, assertions,
        ))

    evidence = {
        "schemaVersion": 1,
        "runner": args.runner,
        "suite": args.suite,
        "env": args.env,
        "mutation": args.mutation,
        "requests": requests,
        "totals": totals(requests),
    }
    save_json(args.output, evidence)
    print("Импортировано запросов: %d, проверок: %d (прошло %d, упало %d). Тела ответов — в %s/"
          % (evidence["totals"]["requests"], evidence["totals"]["assertions"],
             evidence["totals"]["passed"], evidence["totals"]["failed"],
             os.path.basename(bodies_dir(args.output))))
    print("Дальше обязательно: python3 evidence.py audit %s" % args.output)
    return evidence


# ---------------------------------------------------------------- run (curl)

def curl_once(spec, insecure):
    method = (spec.get("method") or "GET").upper()
    url = os.path.expandvars(spec["url"])
    cmd = ["curl", "-sS", "--max-time", "60", "-X", method, url,
           "-w", "\n%{http_code}", "-o", "-"]
    if insecure:
        cmd.insert(1, "-k")
    headers = {k: os.path.expandvars(str(v)) for k, v in (spec.get("headers") or {}).items()}
    body = spec.get("body")
    if body is not None and not any(k.lower() == "content-type" for k in headers):
        headers["Content-Type"] = "application/json"
    for key, value in headers.items():
        cmd += ["-H", "%s: %s" % (key, value)]
    if body is not None:
        payload = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
        cmd += ["--data-binary", os.path.expandvars(payload)]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 and not proc.stdout:
        return url, None, None, (proc.stderr or "").strip()
    raw, _, code = proc.stdout.rpartition("\n")
    try:
        status = int(code.strip())
    except ValueError:
        status = None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = None
    return url, status, parsed, raw


def cmd_run(args):
    specs = load_json(args.requests)
    if not isinstance(specs, list) or not specs:
        die("файл запросов должен быть непустым списком объектов")
    require_free_bodies(args.output)

    requests = []
    for index, spec in enumerate(specs, 1):
        if not spec.get("url"):
            die("у запроса %d нет url" % index)
        if args.query:
            spec = dict(spec, url=apply_query(spec["url"], args.query))
        observed_at = datetime.now().astimezone().isoformat(timespec="seconds")
        url, status, body, raw = curl_once(spec, args.insecure)
        if status is None:
            print("ВНИМАНИЕ: запрос %s не выполнился: %s" % (spec.get("name") or url, raw), file=sys.stderr)
        requests.append(make_record(
            index, args.output, str(spec.get("name") or url),
            spec.get("case") or find_case(spec.get("name")), spec.get("role") or args.role,
            spec.get("method"), url, status, body, raw if body is None else None, [],
            observed_at,
        ))

    evidence = {
        "schemaVersion": 1,
        "runner": args.runner,
        "suite": args.suite,
        "env": args.env,
        "mutation": {"query": args.query} if args.query else None,
        "requests": requests,
        "totals": totals(requests),
    }
    save_json(args.output, evidence)
    print("Выполнено запросов: %d. Ожиданий не записано (у этого раннера их нет) — "
          "объём выборки считает audit, выводы обосновываются вручную."
          % evidence["totals"]["requests"])
    return evidence


# ---------------------------------------------------------------- audit

def sample_size(record):
    return max(record["counts"].values()) if record["counts"] else 0


def is_empty(record):
    if record["counts"] and max(record["counts"].values()) > 0:
        return False
    if record.get("totalCount"):
        return False
    return True


def cmd_audit(args):
    evidence = load_json(args.evidence)
    requests = evidence.get("requests") or []
    if not requests:
        die("в файле ноль запросов")

    flags = {"EMPTY_BUT_GREEN": [], "SINGLE_RECORD": [], "NO_CASE": [],
             "NO_ASSERTIONS": [], "WRITING": [], "HTTP_ERROR": []}

    print("Объём выборки по запросам")
    print("-" * 72)
    for record in requests:
        passed = sum(1 for a in record["assertions"] if a["status"] == "pass")
        failed = len(record["assertions"]) - passed
        size = sample_size(record)
        counts = ", ".join("%s=%d" % (k, v) for k, v in sorted(record["counts"].items())) or "нет массивов"
        print("%-40s %s %s  проверок %d/%d  %s"
              % (record["name"][:40], record["case"] or "TC-??", record["status"],
                 passed, len(record["assertions"]), counts))

        if record["assertions"] and failed == 0 and is_empty(record) and not record["writing"]:
            flags["EMPTY_BUT_GREEN"].append(record["name"])
        if size == 1:
            flags["SINGLE_RECORD"].append(record["name"])
        if not record["case"]:
            flags["NO_CASE"].append(record["name"])
        if not record["assertions"]:
            flags["NO_ASSERTIONS"].append(record["name"])
        if record["writing"]:
            flags["WRITING"].append("%s %s" % (record["method"], record["name"]))
        if isinstance(record["status"], int) and record["status"] >= 400:
            flags["HTTP_ERROR"].append("%s → %s" % (record["name"], record["status"]))

    print()
    print("Что требует внимания")
    print("-" * 72)
    messages = [
        ("EMPTY_BUT_GREEN", "ВАКУУМНО: выборка пуста, а проверки зелёные — эти выводы недоказуемы"),
        ("SINGLE_RECORD", "ОДНА ЗАПИСЬ: различие между ветками условия ненаблюдаемо, назови это в отчёте"),
        ("HTTP_ERROR", "КОД 4xx/5xx: объясни каждый или назови находкой"),
        ("NO_ASSERTIONS", "БЕЗ ОЖИДАНИЙ: ожидание не записано, вывод придётся обосновывать вручную"),
        ("NO_CASE", "БЕЗ НОМЕРА КЕЙСА: результат некуда вернуть на шаге 13"),
        ("WRITING", "ПИШУЩИЕ ЗАПРОСЫ: обязаны попасть в раздел «что изменилось на стенде»"),
    ]
    clean = True
    for key, text in messages:
        items = flags[key]
        if items:
            clean = False
            print("%s (%d):" % (text, len(items)))
            for item in items[:12]:
                print("   - %s" % item)
            if len(items) > 12:
                print("   ... ещё %d" % (len(items) - 12))
    if clean:
        print("Флагов нет. Это НЕ значит «всё проверено»: объём выборки всё равно указывается в отчёте.")

    print()
    print("Итого: %s" % json.dumps(evidence.get("totals") or {}, ensure_ascii=False))
    print("Следующий обязательный шаг — мутационная проба: evidence.py vacuum --baseline %s ..."
          % args.evidence)


# ---------------------------------------------------------------- vacuum

def apply_query(url, overrides):
    # повторяющийся ключ (?tagIds=A&tagIds=B) — легальная форма, в dict не схлопывать
    parts = urlsplit(url)
    pairs = parse_qsl(parts.query, keep_blank_values=True)
    override_pairs = []
    for pair in overrides:
        key, _, value = pair.partition("=")
        override_pairs.append((key, value))
    overridden = {key for key, _ in override_pairs}
    pairs = [(key, value) for key, value in pairs if key not in overridden]
    return urlunsplit((parts.scheme, parts.netloc, parts.path,
                       urlencode(pairs + override_pairs), parts.fragment))


def match_baseline(baseline, record):
    # только по имени/кейсу: позиционная подстановка молча даёт чужую базу сравнения
    for candidate in baseline:
        if record["case"] and candidate["case"] == record["case"] and candidate["name"] == record["name"]:
            return candidate
    for candidate in baseline:
        if candidate["name"] == record["name"]:
            return candidate
    return None


def cmd_vacuum(args):
    baseline = (load_json(args.baseline).get("requests") or [])
    if not baseline:
        die("в baseline ноль запросов")

    tmp_out = args.output + ".mutated.json"
    require_free_bodies(tmp_out, asked=args.output)
    if args.requests:
        if not args.query:
            die("для прогона по списку запросов нужен хотя бы один --query")
        mutated = cmd_run(argparse.Namespace(
            requests=args.requests, output=tmp_out, runner=args.runner, suite=args.suite,
            env=args.env, role=None, insecure=args.insecure, query=args.query))
    elif args.cmd:
        if not args.report:
            die("с --cmd нужен --report: путь к машинному отчёту, который создаст команда")
        print("Запускаю мутированный прогон: %s" % args.cmd)
        proc = subprocess.run(args.cmd, shell=True, capture_output=True, text=True)
        if proc.returncode != 0:
            print("(команда вернула %d — для проб это нормально, важен отчёт)" % proc.returncode)
        if not os.path.exists(args.report):
            die("отчёт %s не появился, проба не состоялась" % args.report)
        mutated = cmd_import(argparse.Namespace(
            report=args.report, output=tmp_out, runner=args.runner, suite=args.suite,
            env=args.env, role=None, mutation={"cmd": args.cmd, "query": args.query}))
    else:
        die("нужен либо --requests с --query, либо --cmd с --report")

    changed, empty, non_empty, survivors, newly_empty, unmatched = [], [], [], [], [], []
    for record in mutated["requests"]:
        base = match_baseline(baseline, record)
        if base is None:
            unmatched.append(record["name"])
        if base and base["url"] != record["url"]:
            changed.append({"name": record["name"], "was": base["url"], "now": record["url"]})
        if is_empty(record):
            empty.append(record["name"])
            if base and not is_empty(base):
                newly_empty.append(record["name"])
        else:
            non_empty.append({"name": record["name"], "counts": record["counts"]})
        for assertion in record["assertions"]:
            if assertion["status"] == "pass":
                survivors.append({"request": record["name"], "assertion": assertion["name"]})

    assertions_total = mutated["totals"]["assertions"]
    applied = bool(changed) or bool(newly_empty)
    result = {
        "baseline": args.baseline,
        "mutated": tmp_out,
        "mutation": {"query": args.query, "cmd": args.cmd},
        "mutationApplied": applied,
        "unmatchedBaseline": unmatched,
        "urlsChanged": changed[:20],
        "newlyEmpty": newly_empty,
        "emptyRequests": empty,
        "nonEmptyRequests": non_empty,
        "assertionsTotal": assertions_total,
        "assertionsSurvived": len(survivors),
        "survivors": survivors[:40],
    }
    save_json(args.output, result)

    print()
    print("Мутационная проба")
    print("-" * 72)
    if unmatched:
        print("БЕЗ БАЗЫ СРАВНЕНИЯ (%d): имена этих запросов не найдены в baseline —" % len(unmatched))
        print("сравнение «was/now» для них не проводилось. Совпадение имён обязательно:")
        for name in unmatched[:10]:
            print("   - %s" % name)
        if len(unmatched) > 10:
            print("   ... ещё %d" % (len(unmatched) - 10))
        print()
    if not applied:
        print("ПРОБА НЕ ПРИМЕНИЛАСЬ: ни один запрос не изменился и ни одна выборка не опустела.")
        print("Результат НЕДЕЙСТВИТЕЛЕН, вакуумность НЕ ИЗМЕРЕНА. Цифр про зелёные проверки")
        print("здесь нет намеренно: на неизменённых данных они ничего не означают.")
        print("Это претензия сама по себе — класс «артефакт инструмента».")
        if args.cmd:
            print("Проверь, что запросы раннера действительно читают подменяемую переменную:")
            print("подмена окружения не действует на параметр, зашитый в запрос строкой.")
        print()
        print("Подробности: %s" % args.output)
        sys.exit(1)

    print("Проба применилась: URL изменён у %d запросов, опустело впервые %d."
          % (len(changed), len(newly_empty)))
    print("Пустых выборок: %d из %d." % (len(empty), len(mutated["requests"])))
    if non_empty:
        print("НЕ опустели (на этих запросах проба не сработала, их вакуумность не измерена):")
        for item in non_empty[:10]:
            print("   - %s: %s" % (item["name"], item["counts"]))
    if assertions_total:
        print("ОСТАЛИСЬ ЗЕЛЁНЫМИ НА ПУСТОЙ ВЫБОРКЕ: %d из %d проверок."
              % (len(survivors), assertions_total))
        print("Это и есть измеренная вакуумность. Каждая такая проверка на реальных данных")
        print("тоже ничего не доказывает — либо добей данными, либо сними вывод.")
        for item in survivors[:15]:
            print("   - %s / %s" % (item["request"], item["assertion"]))
        if len(survivors) > 15:
            print("   ... ещё %d" % (len(survivors) - 15))
    else:
        print("Ожиданий в прогоне нет — вакуумность измеряется только по пустоте выборок.")
    print()
    print("Подробности: %s" % args.output)


# ---------------------------------------------------------------- cost

def human_size(size):
    for unit, step in (("МБ", 1024 * 1024), ("КБ", 1024)):
        if size >= step:
            return "%.1f %s" % (size / float(step), unit)
    return "%d Б" % size


def dump_volume(root):
    """Файлы каталога захода и их объём: сколько сырья заход реально произвёл.

    Скрытое не считаем — это служебное окружение, а не сырьё прогона.
    """
    total_files, total_size, by_entry = 0, 0, {}
    for base, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in names:
            if name.startswith("."):
                continue
            path = os.path.join(base, name)
            try:
                size = os.path.getsize(path)
            except OSError:
                continue
            rel = os.path.relpath(path, root)
            entry = rel.split(os.sep)[0] if os.sep in rel else "(корень каталога)"
            files, bytes_ = by_entry.get(entry, (0, 0))
            by_entry[entry] = (files + 1, bytes_ + size)
            total_files += 1
            total_size += size
    return total_files, total_size, by_entry


def cmd_cost(args):
    """Машинная часть строки стоимости захода. Остальное агент заполняет своим протоколом.

    Скрипт не принимает числа вызовов субагентов и вмешательств человека и не будет их
    принимать: наблюдает их только сам агент, а число, прошедшее через скрипт, читается
    в отчёте как измеренное.
    """
    runs, requests, writing, assertions = 0, 0, 0, 0
    for path in args.evidence:
        evidence = load_json(path)
        records = evidence.get("requests") or []
        runs += 1
        requests += len(records)
        writing += sum(1 for r in records if r.get("writing"))
        assertions += sum(len(r.get("assertions") or []) for r in records)

    root = args.dir
    if root is None:
        if not args.evidence:
            die("нечего считать: назови файлы сырья, каталог захода через --dir или оба")
        root = os.path.dirname(os.path.abspath(args.evidence[0])) or "."
    if not os.path.isdir(root):
        die("каталог захода не найден: %s" % root)
    files, size, by_entry = dump_volume(root)

    print("Каталог захода: %s" % os.path.abspath(root))
    print("-" * 72)
    for entry, (count, bytes_) in sorted(by_entry.items(), key=lambda kv: -kv[1][1]):
        print("%-40s %4d файл(ов)  %s" % (entry[:40], count, human_size(bytes_)))
    if not by_entry:
        print("пусто — сырья на диске нет, и в отчёте это пишется как есть")

    print()
    print("Строка для раздела «Метод» отчёта — скопируй и заполни угловые скобки:")
    print("-" * 72)
    print("**Стоимость захода:** прогонов раннера %d, запросов %d (пишущих %d), ожиданий %d; "
          "сырья %d файл(ов), %s; субагентов <N> (<роли с числами>); скептик <N> заходов, "
          "принято <N> претензий из <N>; вмешательств человека <N> (<что именно>)."
          % (runs, requests, writing, assertions, files, human_size(size)))
    print("-" * 72)
    print("Угловые скобки заполняются по протоколу захода, а не по памяти. Нечем подтвердить —")
    print("пиши «не считалось»: пропуск честнее выдуманного числа и виден на кривой стоимости.")
    print("Токенов и длительности здесь нет намеренно: расход контекста агенту не виден, а")
    print("время захода включает ожидание человека. Просить их — значит просить их выдумать.")


# ---------------------------------------------------------------- timeline

def file_events(root):
    """Время появления каждого файла сырья: якорь, который не зависит от памяти агента."""
    events = []
    for base, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in names:
            if name.startswith("."):
                continue
            path = os.path.join(base, name)
            try:
                stamp = os.path.getmtime(path)
            except OSError:
                continue
            events.append((stamp, os.path.relpath(path, root), "файл сырья"))
    return events


def git_events(repo, since):
    proc = subprocess.run(
        ["git", "-C", repo, "log", "--since=@%d" % int(since), "--pretty=%ct\t%h %s"],
        capture_output=True, text=True)
    if proc.returncode != 0:
        return []
    events = []
    for line in proc.stdout.splitlines():
        stamp, _, text = line.partition("\t")
        try:
            events.append((float(stamp), text, "коммит"))
        except ValueError:
            continue
    return events


def cmd_timeline(args):
    """Хронология захода по наблюдаемым меткам, а не по воспоминаниям.

    Замерено: заходы, писавшие хронологию задним числом, давали либо «оценка, не измерение»,
    либо не давали времён вовсе. Метки файлов и коммитов существуют независимо от сессии.
    """
    if not os.path.isdir(args.dir):
        die("каталог захода не найден: %s" % args.dir)

    events = file_events(args.dir)
    if not events:
        die("в каталоге захода нет файлов — хронологии не из чего собирать")

    since = min(stamp for stamp, _, _ in events)
    if args.repo:
        events += git_events(args.repo, since)
    events.sort(key=lambda e: e[0])

    fmt = "%Y-%m-%d %H:%M:%S"
    print("Хронология захода: %s" % os.path.abspath(args.dir))
    print("Время локальное, метки — mtime файлов и время коммитов. Оценок здесь нет.")
    print("-" * 72)
    shown = events if len(events) <= args.limit else events[:args.limit]
    for stamp, text, kind in shown:
        print("%s  %-13s %s" % (datetime.fromtimestamp(stamp).strftime(fmt), kind, text[:80]))
    if len(events) > len(shown):
        print("... ещё %d событий (--limit, чтобы показать больше)" % (len(events) - len(shown)))

    span = events[-1][0] - events[0][0]
    print("-" * 72)
    print("Окно наблюдаемых меток: %s → %s, это %d мин %02d с."
          % (datetime.fromtimestamp(events[0][0]).strftime(fmt),
             datetime.fromtimestamp(events[-1][0]).strftime(fmt),
             int(span // 60), int(span % 60)))
    print("Это НЕ длительность захода: до первого сохранённого файла работа уже шла (чтение")
    print("карточки, кейсы), а ожидание ответов человека внутрь окна входит наравне с работой.")
    print("В запись захода окно идёт как окно, с этой оговоркой, а не как «заход занял N минут».")


# ---------------------------------------------------------------- CLI

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)

    imp = sub.add_parser("import", help="отчёт раннера → evidence.json")
    imp.add_argument("--runner", default="bruno")
    imp.add_argument("--report", required=True, help="машинный отчёт прогона")
    imp.add_argument("-o", "--output", default="evidence.json")
    imp.add_argument("--role", default=None, help="роль, под которой шёл прогон")
    imp.add_argument("--suite", action="append", default=[], help="что гонял (для протокола)")
    imp.add_argument("--env", default=None)
    imp.set_defaults(func=cmd_import, mutation=None)

    run = sub.add_parser("run", help="выполнить запросы самому (когда машинного отчёта нет)")
    run.add_argument("--runner", default="curl")
    run.add_argument("--requests", required=True, help="JSON-список запросов")
    run.add_argument("-o", "--output", default="evidence.json")
    run.add_argument("--role", default=None)
    run.add_argument("--suite", action="append", default=[])
    run.add_argument("--env", default=None)
    run.add_argument("--insecure", action="store_true")
    run.add_argument("--query", action="append", default=[], help="подмена параметра: k=v")
    run.set_defaults(func=cmd_run)

    aud = sub.add_parser("audit", help="объём выборки, вакуумные кандидаты, пишущие запросы")
    aud.add_argument("evidence")
    aud.set_defaults(func=cmd_audit)

    vac = sub.add_parser("vacuum", help="мутационная проба на заведомо пустой выборке")
    vac.add_argument("--baseline", required=True, help="evidence.json обычного прогона")
    vac.add_argument("--requests", help="список запросов для повторного прогона через curl")
    vac.add_argument("--cmd", help="команда мутированного прогона раннером")
    vac.add_argument("--report", help="куда команда положит машинный отчёт")
    vac.add_argument("--query", action="append", default=[], help="подмена параметра: k=v")
    vac.add_argument("--runner", default="curl")
    vac.add_argument("--suite", action="append", default=[])
    vac.add_argument("--env", default=None)
    vac.add_argument("--insecure", action="store_true")
    vac.add_argument("-o", "--output", default="vacuum.json")
    vac.set_defaults(func=cmd_vacuum)

    cost = sub.add_parser("cost", help="строка стоимости захода для раздела «Метод» отчёта")
    cost.add_argument("evidence", nargs="*", help="все файлы сырья захода: baseline, мутированный, …")
    cost.add_argument("--dir", default=None,
                      help="каталог захода (по умолчанию — каталог первого файла сырья)")
    cost.set_defaults(func=cmd_cost)

    tl = sub.add_parser("timeline", help="хронология захода по меткам файлов и коммитов")
    tl.add_argument("--dir", required=True, help="каталог захода с сырьём")
    tl.add_argument("--repo", default=None,
                    help="каталог репозитория: добавить коммиты, сделанные с начала захода")
    tl.add_argument("--limit", type=int, default=60, help="сколько событий печатать")
    tl.set_defaults(func=cmd_timeline)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
