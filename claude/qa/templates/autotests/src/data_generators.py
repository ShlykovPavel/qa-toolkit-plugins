"""Генераторы уникальных тестовых данных.

Уникальность данных — обязательное условие независимости тестов и
параллельного прогона (pytest-xdist): два теста никогда не должны
конфликтовать за одну и ту же запись.
"""

import random


def generate_id(length: int = 10) -> str:
    """Случайная числовая строка заданной длины (например, внешний идентификатор)."""
    return "".join(str(random.randint(0, 9)) for _ in range(length))


def generate_phone_number() -> str:
    """Случайный телефон. Префикс/формат адаптируйте под свою локаль."""
    prefix = "+1"
    area_codes = ["212", "415", "650", "312", "646", "917"]
    area = random.choice(area_codes)
    number = "".join(str(random.randint(0, 9)) for _ in range(7))
    return f"{prefix}{area}{number}"


def generate_email() -> str:
    """Уникальный тестовый email."""
    suffix = "".join(str(random.randint(0, 9)) for _ in range(8))
    return f"autotest{suffix}@example.test"


def generate_name(prefix: str = "autotest") -> str:
    """Уникальное имя для создаваемых сущностей (ресурсы, проекты и т.п.)."""
    suffix = "".join(str(random.randint(0, 9)) for _ in range(6))
    return f"{prefix}_{suffix}"
