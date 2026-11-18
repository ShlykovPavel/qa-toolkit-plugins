"""Загрузка OpenAPI-спеки из файла или по URL — общая для скриптов bin/.

Зачем отдельный модуль: спеки в проектах бывают и JSON, и YAML (Swagger UI
отдаёт JSON, а выгрузки из репозитория разработчиков часто YAML), а логика
выбора парсера нужна всем скриптам обвязки одинаковая — дублировать её в
каждом значит однажды научить YAML только один из них.

JSON читается стандартной библиотекой. Для YAML нужен PyYAML (он есть в
requirements.txt); если модуль не установлен — скрипт падает с внятным
сообщением, а не с ImportError из середины трассировки.
"""

import json
import urllib.request

YAML_SUFFIXES = (".yaml", ".yml")


class SpecLoadError(Exception):
    """Спеку не удалось прочитать — сообщение уже готово для пользователя."""


def _parse_yaml(text: str, source: str) -> dict:
    try:
        import yaml
    except ImportError:
        raise SpecLoadError(
            f"Спека {source} — YAML, но модуль PyYAML не установлен.\n"
            "Установите зависимости проекта: pip install -r requirements.txt\n"
            "(или укажите JSON-версию спеки через --spec)")
    return yaml.safe_load(text)


def _looks_like_yaml(source: str, text: str) -> bool:
    """YAML определяется по расширению, а если его нет — по первому символу.

    JSON-документ всегда начинается с `{` или `[`; всё остальное разбираем
    как YAML (он надмножество JSON, так что ошибиться безопасно).
    """
    if source.lower().endswith(YAML_SUFFIXES):
        return True
    if source.lower().endswith(".json"):
        return False
    return not text.lstrip().startswith(("{", "["))


def load_spec(source: str) -> dict:
    """Читает спеку из файла или по URL (http/https). Формат — JSON или YAML."""
    if source.startswith(("http://", "https://")):
        with urllib.request.urlopen(source, timeout=30) as response:
            text = response.read().decode("utf-8")
    else:
        try:
            with open(source, encoding="utf-8") as spec_file:
                text = spec_file.read()
        except OSError as error:
            raise SpecLoadError(f"Не удалось прочитать спеку {source}: {error}")

    if _looks_like_yaml(source, text):
        spec = _parse_yaml(text, source)
    else:
        try:
            spec = json.loads(text)
        except json.JSONDecodeError as error:
            raise SpecLoadError(f"Спека {source} — не валидный JSON: {error}")

    if not isinstance(spec, dict) or "paths" not in spec:
        raise SpecLoadError(
            f"В {source} нет секции paths — это не похоже на OpenAPI-спеку.")
    return spec
