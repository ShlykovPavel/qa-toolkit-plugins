#!/usr/bin/env python3
"""Сверка API-клиентов src/ с OpenAPI-спекой — механически, а не глазами.

Зачем: `compileall` проверяет синтаксис, `coverage_check.py` — что у каждого
тега спеки есть пакет. Между этими двумя проверками помещается почти всё,
чем на практике ломается сгенерированный клиентский слой: вызов HttpClient
без обязательного аргумента, тип в аннотации, который нигде не определён,
модель ответа не от той схемы, потерянные query-параметры, придуманное тело
запроса. Всё это ловится сверкой AST клиентов со спекой — без стенда и без
запуска тестов.

Запускать интерпретатором проекта (нужен PyYAML для YAML-спек и импорт
config для проверки импортируемости):

    .venv/bin/python ${CLAUDE_PLUGIN_ROOT}/bin/api_client_check.py --spec specs/api.json --package src/api

Выход: 0 — ошибок нет (предупреждения не влияют), 1 — есть ошибки.

Категории ошибок (ломают код или расходятся со спекой):
  ИМПОРТ                 модуль клиента не импортируется (NameError и т.п.)
  АННОТАЦИЯ              тип в аннотации не определён и не импортирован
  СИГНАТУРА HttpClient   вызов без обязательного аргумента → TypeError
  НЕТ В СПЕКЕ            клиент ходит по пути/методу, которых в спеке нет
  ЭНДПОИНТ БЕЗ КЛИЕНТА   операция спеки не покрыта ни одним методом
  КОД ОТВЕТА             status_code по умолчанию не из спеки
  НЕТ РАННЕГО RETURN     парсинг модели без раннего return при status_code>=400
  QUERY В URL            query-строка собрана вручную, а не через query_params
  НЕ ТА МОДЕЛЬ           парсится не та схема, что объявлена в ответе операции
  ПОЛЯ МОДЕЛИ            состав полей модели расходится со схемой спеки
  ТЕЛО ЗАПРОСА           поля тела, которых нет в requestBody операции

Категории предупреждений (не ломают, но обычно стоит поправить):
  QUERY НЕ ПРОБРОШЕН, ИМЯ МЕТОДА, ДУБЛЬ DTO, NULLABLE БЕЗ OPTIONAL,
  ОТВЕТ БЕЗ МОДЕЛИ, МОДЕЛЬ БЕЗ СХЕМЫ, ТЕЛО БЕЗ ОБЯЗАТЕЛЬНЫХ ПОЛЕЙ,
  URL НЕ РАЗОБРАН (путь собран не из BASE_URL — метод не сверен со спекой)
"""

import argparse
import ast
import builtins
import importlib
import os
import pathlib
import re
import sys
import typing
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spec_loader import SpecLoadError, load_spec  # noqa: E402

HTTP_METHODS = ("get", "post", "put", "patch", "delete")
ERRORS = (
    "ИМПОРТ", "АННОТАЦИЯ", "СИГНАТУРА HttpClient", "НЕТ В СПЕКЕ",
    "ЭНДПОИНТ БЕЗ КЛИЕНТА", "КОД ОТВЕТА", "НЕТ РАННЕГО RETURN", "QUERY В URL",
    "НЕ ТА МОДЕЛЬ", "ПОЛЯ МОДЕЛИ", "ТЕЛО ЗАПРОСА",
)
JSON_MEDIA = ("application/json", "text/json", "text/plain", "application/*+json")
MACHINE_NAME = re.compile(r"_\d+$")


def type_of(schema: dict) -> set:
    """Типы схемы множеством: в OpenAPI 3.0 это строка, в 3.1 — список."""
    declared = (schema or {}).get("type")
    if isinstance(declared, list):
        return set(declared)
    return {declared} if declared else set()


def is_nullable(schema: dict) -> bool:
    """`nullable: true` (3.0) или `null` в списке типов (3.1)."""
    return bool((schema or {}).get("nullable")) or "null" in type_of(schema)


# --------------------------------------------------------------------------
# Спека
# --------------------------------------------------------------------------

def normalize_path(path: str) -> str:
    """`/api/items/{itemId}` → `/api/items/{}` — имя параметра не значимо."""
    return re.sub(r"\{[^}]*\}", "{}", path)


def media_schema(node: dict) -> dict:
    """Схема тела/ответа из первого знакомого media-type."""
    content = (node or {}).get("content") or {}
    for media in JSON_MEDIA:
        if media in content:
            return content[media].get("schema") or {}
    return {}


def ref_name(schema: dict) -> str:
    """Имя схемы из $ref — самой или элемента массива."""
    if not schema:
        return ""
    direct = schema.get("$ref", "").rsplit("/", 1)[-1]
    if direct:
        return direct
    items = schema.get("items") or {}
    return items.get("$ref", "").rsplit("/", 1)[-1]


class Spec:
    """Операции и схемы спеки в форме, удобной для сверки с кодом."""

    def __init__(self, spec: dict):
        self.schemas = (spec.get("components") or {}).get("schemas") or {}
        self.operations = {}
        for path, path_item in (spec.get("paths") or {}).items():
            if not isinstance(path_item, dict):
                continue
            shared = path_item.get("parameters") or []
            for method in HTTP_METHODS:
                operation = path_item.get(method)
                if not isinstance(operation, dict):
                    continue
                ok_codes = sorted(code for code in operation.get("responses") or {}
                                  if str(code).startswith("2"))
                response = media_schema((operation.get("responses") or {}).get(
                    ok_codes[0], {})) if ok_codes else {}
                body = media_schema(operation.get("requestBody") or {})
                body_ref = body.get("$ref", "").rsplit("/", 1)[-1]
                self.operations[(normalize_path(path), method)] = {
                    "path": path,
                    "codes": ok_codes,
                    "response_ref": ref_name(response),
                    "is_array": "array" in type_of(response),
                    # структурный ответ = объект/массив/$ref; скаляр и пустое
                    # тело разбирать в модель нечем и не нужно
                    "structured_response": bool(
                        ref_name(response) or type_of(response) & {"array", "object"}
                        or response.get("properties")),
                    "query": [p.get("name") for p in shared + (operation.get("parameters") or [])
                              if p.get("in") == "query"],
                    "body_ref": body_ref,
                    "body_props": list(self.properties(body_ref) if body_ref
                                       else (body.get("properties") or {})),
                    "body_required": (self.schemas.get(body_ref, {}).get("required", [])
                                      if body_ref else body.get("required", [])),
                    "tags": operation.get("tags") or [],
                }

    def properties(self, name: str, seen=frozenset()) -> dict:
        """Свойства схемы с разворотом allOf-наследования."""
        schema = self.schemas.get(name) or {}
        props = dict(schema.get("properties") or {})
        for part in schema.get("allOf") or []:
            parent = part.get("$ref", "").rsplit("/", 1)[-1]
            if parent and parent not in seen:
                props.update(self.properties(parent, seen | {parent}))
            else:
                props.update(part.get("properties") or {})
        return props


# --------------------------------------------------------------------------
# Разбор клиента
# --------------------------------------------------------------------------

def literal_url(node: ast.AST) -> str:
    """Восстанавливает URL из `BASE_URL + "..."` и f-строк. `¿` — неизвестное."""
    if isinstance(node, ast.Constant):
        return str(node.value)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return literal_url(node.left) + literal_url(node.right)
    if isinstance(node, ast.Name):
        return "" if node.id == "BASE_URL" else "¿"
    if isinstance(node, ast.JoinedStr):
        out = ""
        for value in node.values:
            if isinstance(value, ast.Constant):
                out += str(value.value)
            elif (isinstance(value, ast.FormattedValue)
                  and isinstance(value.value, ast.Name)
                  and value.value.id == "BASE_URL"):
                out += ""
            else:
                out += "{}"
        return out
    return "¿"


def annotation_names(node: ast.AST):
    """Имена типов, использованных в аннотации (Optional[List[Foo]] → Foo)."""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            yield sub.id
        elif isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            yield sub.value  # строковая аннотация


def module_defined_names(tree: ast.Module):
    """Всё, что модуль определяет или импортирует на верхнем уровне."""
    names = set(dir(builtins)) | set(vars(typing))
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            names.update((alias.asname or alias.name).split(".")[0] for alias in node.names)
        elif isinstance(node, ast.Assign):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
    return names


def http_client_signatures(root: pathlib.Path) -> dict:
    """{метод: [обязательные позиционные аргументы]} из src/http_methods.py."""
    source = (root / "src" / "http_methods.py").read_text(encoding="utf-8")
    signatures = {}
    for node in ast.parse(source).body:
        if not (isinstance(node, ast.ClassDef) and node.name == "HttpClient"):
            continue
        for member in node.body:
            if isinstance(member, ast.FunctionDef) and member.name in HTTP_METHODS:
                args = [a.arg for a in member.args.args if a.arg not in ("cls", "self")]
                required = len(args) - len(member.args.defaults)
                signatures[member.name] = args[:required]
    return signatures


class Method:
    """Факты о методе клиента, извлечённые из AST."""

    def __init__(self, node: ast.FunctionDef, location: str):
        self.node = node
        self.location = location
        self.source = ast.unparse(node)
        self.url = self.verb = self.model = None
        self.positional = 0
        self.body_keyword = False
        self.query_keys = set()
        self.body_keys = set()
        self.query_passthrough = bool(re.search(r"query_params=\{[^}]*\*\*", self.source))

        for sub in ast.walk(node):
            if isinstance(sub, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == "url" for t in sub.targets):
                self.url = literal_url(sub.value)
            if not isinstance(sub, ast.Call) or not isinstance(sub.func, ast.Attribute):
                continue
            if sub.func.attr == "model_validate" and isinstance(sub.func.value, ast.Name):
                self.model = sub.func.value.id
            if (isinstance(sub.func.value, ast.Name) and sub.func.value.id == "HttpClient"
                    and sub.func.attr in HTTP_METHODS):
                self.verb = sub.func.attr
                self.positional = len(sub.args)
                for keyword in sub.keywords:
                    if keyword.arg == "body":
                        self.body_keyword = True
                        self.body_keys |= dict_keys(keyword.value)
                    if keyword.arg == "query_params":
                        self.query_keys |= dict_keys(keyword.value)
                if len(sub.args) > 1:
                    self.body_keys |= dict_keys(sub.args[1])

        # словарь params/default_body, собранный до вызова
        for sub in ast.walk(node):
            if isinstance(sub, ast.Assign) and isinstance(sub.targets[0], ast.Name):
                name, keys = sub.targets[0].id, dict_keys(sub.value)
                if name == "params":
                    self.query_keys |= keys
                elif name in ("body", "default_body"):
                    self.body_keys |= keys
            if isinstance(sub, ast.Subscript) and isinstance(sub.value, ast.Name) \
                    and isinstance(sub.slice, ast.Constant):
                target = self.query_keys if sub.value.id == "params" else (
                    self.body_keys if sub.value.id in ("body", "default_body") else None)
                if target is not None:
                    target.add(sub.slice.value)

        self.status_code = None
        defaults = node.args.defaults or []
        for arg, default in zip(node.args.args[::-1], defaults[::-1]):
            if arg.arg == "status_code":
                self.status_code = getattr(default, "value", None)

    @property
    def parses(self) -> bool:
        return "model_validate" in self.source or "parse_json" in self.source

    @property
    def has_early_return(self) -> bool:
        return "if status_code >= 400" in self.source


def skipped(path: pathlib.Path, package: pathlib.Path) -> bool:
    """Служебное и `example_*`-эталоны не проверяем: они не домены спеки.

    Правило то же, что в coverage_check.py — эталоны шаблона пропускаются
    всегда, и файлы (`example_auth.py`), и директории.
    """
    inside = path.relative_to(package).parts
    return ("__pycache__" in path.parts
            or any(part.startswith("example_") for part in inside))


def dict_keys(node: ast.AST) -> set:
    """Строковые ключи словарного литерала (иначе — пусто)."""
    if isinstance(node, ast.Dict):
        return {k.value for k in node.keys if isinstance(k, ast.Constant)}
    return set()


# --------------------------------------------------------------------------
# Проверки
# --------------------------------------------------------------------------

class Report:
    def __init__(self):
        self.found = defaultdict(list)

    def add(self, category: str, message: str):
        self.found[category].append(message)

    def render(self, limit: int) -> int:
        errors = {c: v for c, v in self.found.items() if c in ERRORS}
        warnings = {c: v for c, v in self.found.items() if c not in ERRORS}
        for title, group in (("ОШИБКИ", errors), ("ПРЕДУПРЕЖДЕНИЯ", warnings)):
            if not group:
                continue
            print(f"\n{'=' * 8} {title} {'=' * 8}")
            for category in sorted(group):
                items = group[category]
                print(f"\n[{category}] — {len(items)}")
                for item in items[:limit]:
                    print(f"  {item}")
                if len(items) > limit:
                    print(f"  ... ещё {len(items) - limit} (см. --limit)")
        return sum(len(v) for v in errors.values())


def check_package(spec: Spec, package: pathlib.Path, root: pathlib.Path,
                  report: Report, skip_import: bool) -> tuple:
    signatures = http_client_signatures(root)
    aliases = collect_aliases(package)
    covered = set()
    methods = 0

    for module_path in sorted(package.rglob("*.py")):
        if skipped(module_path, package):
            continue
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        relative = module_path.relative_to(root)
        defined = module_defined_names(tree)

        # Аннотации проверяются во ВСЕХ модулях пакета, включая models.py:
        # тип, на который ссылается модель, но который никто не определил,
        # роняет импорт всего домена (Python вычисляет аннотации при def).
        for node in ast.walk(tree):
            annotation = getattr(node, "annotation", None) or getattr(node, "returns", None)
            if annotation is None:
                continue
            for name in annotation_names(annotation):
                if name not in defined:
                    report.add("АННОТАЦИЯ",
                               f"{relative}:{node.lineno}: тип `{name}` не определён "
                               f"и не импортирован в модуле")

        if module_path.name in ("__init__.py", "models.py"):
            continue

        for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
            for func in [n for n in cls.body if isinstance(n, ast.FunctionDef)]:
                methods += 1
                method = Method(func, f"{relative}:{func.lineno} {cls.name}.{func.name}")
                check_method(spec, method, signatures, aliases, report, covered)

        if not skip_import:
            module_name = str(module_path.relative_to(root).with_suffix("")).replace(os.sep, ".")
            try:
                importlib.import_module(module_name)
            except Exception as error:  # noqa: BLE001 — важно поймать любую
                report.add("ИМПОРТ", f"{relative}: {type(error).__name__}: {error}")

    for key, operation in spec.operations.items():
        if key not in covered:
            tags = ",".join(operation["tags"])
            report.add("ЭНДПОИНТ БЕЗ КЛИЕНТА",
                       f"{key[1].upper()} {operation['path']} [{tags}]")
    return methods, len(covered)


def check_method(spec: Spec, method: Method, signatures: dict, aliases: dict,
                 report: Report, covered: set):
    if method.url is None or method.verb is None:
        return  # не HTTP-метод клиента (хелпер) — не наше дело

    required = signatures.get(method.verb, [])
    if method.positional < len(required) and not method.body_keyword:
        report.add("СИГНАТУРА HttpClient",
                   f"{method.location}: HttpClient.{method.verb} требует {required}, "
                   f"передан(о) позиционных аргументов: {method.positional}")

    if "?" in method.url:
        report.add("QUERY В URL", f"{method.location}: {method.url}")

    if "¿" in method.url:
        # URL собран не из BASE_URL (второй сервис на своём хосте, хелпер):
        # сверять такой путь со спекой нечем — честно сообщаем, что метод
        # остался непроверенным, вместо ложного «нет в спеке».
        report.add("URL НЕ РАЗОБРАН",
                   f"{method.location}: путь собран не из BASE_URL — не сверен со спекой")
        return

    operation = spec.operations.get((method.url, method.verb))
    if operation is None:
        others = sorted(m for (p, m) in spec.operations if p == method.url)
        hint = f" (в спеке для этого пути есть: {others})" if others else ""
        report.add("НЕТ В СПЕКЕ",
                   f"{method.location}: {method.verb.upper()} {method.url}{hint}")
        return
    covered.add((method.url, method.verb))

    if method.status_code is not None and operation["codes"] \
            and str(method.status_code) not in operation["codes"]:
        report.add("КОД ОТВЕТА", f"{method.location}: клиент ждёт {method.status_code}, "
                                 f"спека — {operation['codes']}")

    if method.parses and not method.has_early_return:
        report.add("НЕТ РАННЕГО RETURN", method.location)

    missing_query = [q for q in operation["query"] if q not in method.query_keys]
    if missing_query and not method.query_passthrough:
        report.add("QUERY НЕ ПРОБРОШЕН", f"{method.location}: {missing_query}")

    check_body(method, operation, report)
    check_response(spec, method, operation, aliases, report)

    if MACHINE_NAME.search(method.node.name):
        report.add("ИМЯ МЕТОДА",
                   f"{method.location}: машинное имя — назовите метод по смыслу "
                   f"эндпоинта {operation['path']}")


def check_body(method: Method, operation: dict, report: Report):
    keys = method.body_keys
    if not keys:
        return
    if not operation["body_props"]:
        report.add("ТЕЛО ЗАПРОСА", f"{method.location}: шлёт {sorted(keys)}, "
                                   f"в спеке у операции нет requestBody")
        return
    extra = sorted(k for k in keys if k not in operation["body_props"])
    if extra:
        report.add("ТЕЛО ЗАПРОСА", f"{method.location}: полей {extra} нет "
                                   f"в схеме {operation['body_ref']}")
    if "model_dump" not in method.source:
        missing = [k for k in operation["body_required"] if k not in keys]
        if missing:
            report.add("ТЕЛО БЕЗ ОБЯЗАТЕЛЬНЫХ ПОЛЕЙ", f"{method.location}: {missing}")


def check_response(spec: Spec, method: Method, operation: dict, aliases: dict,
                   report: Report):
    if not operation["structured_response"]:
        return  # пусто или скаляр — разбирать нечего
    if method.model is None:
        shape = operation["response_ref"] or "объект/массив"
        report.add("ОТВЕТ БЕЗ МОДЕЛИ",
                   f"{method.location}: спека отдаёт {shape}, клиент его не разбирает")
        return
    parses_list = bool(re.search(r"for \w+ in data", method.source))
    if operation["is_array"] and not parses_list:
        report.add("НЕ ТА МОДЕЛЬ", f"{method.location}: спека отдаёт массив, "
                                   f"клиент парсит одиночный объект")
    if not operation["is_array"] and parses_list:
        report.add("НЕ ТА МОДЕЛЬ", f"{method.location}: спека отдаёт объект "
                                   f"{operation['response_ref']}, клиент парсит массив")
    if operation["response_ref"] and method.model not in aliases \
            and method.model != operation["response_ref"]:
        report.add("НЕ ТА МОДЕЛЬ", f"{method.location}: парсит {method.model}, "
                                   f"схема ответа в спеке — {operation['response_ref']}")


def collect_aliases(package: pathlib.Path) -> dict:
    """Алиасы вида `FooPage = PageResult[FooDto]` — их имя со спекой не сверяем."""
    aliases = {}
    for models in package.rglob("models.py"):
        for node in ast.parse(models.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Subscript) \
                    and isinstance(node.targets[0], ast.Name):
                aliases[node.targets[0].id] = ast.unparse(node.value)
    return aliases


def check_models(spec: Spec, package: pathlib.Path, root: pathlib.Path, report: Report):
    by_name = defaultdict(list)
    for models in sorted(package.rglob("models.py")):
        if skipped(models, package):
            continue
        relative = models.relative_to(root)
        for node in ast.parse(models.read_text(encoding="utf-8")).body:
            if not isinstance(node, ast.ClassDef):
                continue
            by_name[node.name].append(models.parent.name)
            schema_props = spec.properties(node.name)
            if not schema_props:
                report.add("МОДЕЛЬ БЕЗ СХЕМЫ", f"{relative}::{node.name} — "
                                               f"нет одноимённой схемы в спеке")
                continue
            fields = {st.target.id: (ast.unparse(st.annotation), st.value is not None)
                      for st in node.body if isinstance(st, ast.AnnAssign)}
            extra = sorted(set(fields) - set(schema_props))
            missing = sorted(set(schema_props) - set(fields))
            if extra or missing:
                report.add("ПОЛЯ МОДЕЛИ", f"{relative}::{node.name}: "
                                          f"лишние={extra} отсутствуют={missing}")
            for field, (annotation, has_default) in fields.items():
                prop = schema_props.get(field) or {}
                if is_nullable(prop) and not (annotation.startswith("Optional") or has_default):
                    report.add("NULLABLE БЕЗ OPTIONAL", f"{relative}::{node.name}.{field}")

    for name, domains in sorted(by_name.items()):
        if len(domains) > 1:
            report.add("ДУБЛЬ DTO", f"{name}: {domains} — повторяющуюся схему "
                                    f"выносите в src/common_models.py")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Сверяет API-клиенты src/ с OpenAPI-спекой.")
    parser.add_argument("--spec", required=True, help="путь к спеке (JSON/YAML) или URL")
    parser.add_argument("--package", required=True,
                        help="директория доменных пакетов, напр. src/api")
    parser.add_argument("--skip-import", action="store_true",
                        help="не импортировать модули (если окружение не собрано)")
    parser.add_argument("--limit", type=int, default=20,
                        help="сколько находок печатать в категории (по умолчанию 20)")
    args = parser.parse_args()

    root = pathlib.Path.cwd().resolve()  # корень проекта: скрипт лежит в плагине
    package = pathlib.Path(args.package).resolve()
    if not package.is_dir():
        print(f"Нет директории пакета: {package}")
        return 1
    if not package.is_relative_to(root):
        print(f"Пакет {package} вне корня репозитория {root} — "
              f"клиенты проверяются только внутри проекта.")
        return 1
    sys.path.insert(0, str(root))

    try:
        spec = Spec(load_spec(args.spec))
    except SpecLoadError as error:
        print(error)
        return 1

    report = Report()
    methods, covered = check_package(spec, package, root, report, args.skip_import)
    check_models(spec, package, root, report)

    print(f"Спека: {args.spec} — операций: {len(spec.operations)}")
    print(f"Пакет: {package} — методов: {methods}, покрыто операций: {covered}")

    if methods == 0:
        print(f"\nВ {package} нет методов API-клиентов. Проверьте --package: "
              f"ожидается директория доменных пакетов (напр. src/api), "
              f"а внутри — <домен>/<домен>.py.")
        return 1

    errors = report.render(args.limit)
    if errors:
        print(f"\nОШИБОК: {errors}. Клиентский слой не готов.")
        return 1
    warnings = sum(len(v) for v in report.found.values())
    print(f"\nOK — ошибок нет"
          + (f" (предупреждений: {warnings})." if warnings else "."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
