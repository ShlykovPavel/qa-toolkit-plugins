"""Хелперы для чтения/обновления состояния БД в тестах.

Правила безопасности:
  - Значения ВСЕГДА передаются bound-параметрами (:value) — экранирование
    берёт на себя драйвер, кавычки в данных ничего не ломают.
  - Имена таблиц/колонок нельзя передать параметром, поэтому они проходят
    валидацию _check_identifier (только буквы/цифры/подчёркивание).

Правило для параллельного прогона (pytest-xdist):
  Предпочитайте выборку по известному ключу (get_value_where) выборке
  «последней строки» (get_latest_value): при параллельном прогоне последняя
  строка таблицы может принадлежать другому тесту.
"""

import re

from sqlalchemy import text
from sqlalchemy.orm import Session

_IDENTIFIER_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def _check_identifier(name: str) -> str:
    """Валидирует имя таблицы/колонки перед подстановкой в SQL."""
    if not isinstance(name, str) or not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Недопустимое имя таблицы/колонки: {name!r}")
    return name


class DbInfo:

    @staticmethod
    def get_value_where(session: Session, table_name: str, column_name: str,
                        where_column: str, where_value) -> object:
        """Значение column_name из строки, где where_column = where_value.

        Если таких строк несколько — берётся последняя по id.
        Это ОСНОВНОЙ способ читать состояние БД в тестах: выборка по ключу
        безопасна при параллельном прогоне.
        """
        table = _check_identifier(table_name)
        column = _check_identifier(column_name)
        where_col = _check_identifier(where_column)
        query = text(
            f'SELECT "{column}" FROM {table} '
            f'WHERE "{where_col}" = :value ORDER BY id DESC LIMIT 1'
        )
        result = session.execute(query, {'value': where_value}).fetchone()
        return result[0] if result else None

    @staticmethod
    def get_all_by_column(session: Session, table_name: str,
                          column_name: str, column_value) -> list:
        """Все строки, где column_name = column_value."""
        table = _check_identifier(table_name)
        column = _check_identifier(column_name)
        query = text(f'SELECT * FROM {table} WHERE "{column}" = :value')
        return session.execute(query, {'value': column_value}).fetchall()

    @staticmethod
    def get_latest_value(session: Session, table_name: str, column_name: str) -> object:
        """Значение column_name из последней (по id) строки таблицы.

        Внимание: при параллельном прогоне «последняя строка» может принадлежать
        другому тесту. Используйте только когда ключа для WHERE физически нет,
        иначе — get_value_where.
        """
        table = _check_identifier(table_name)
        column = _check_identifier(column_name)
        query = text(f'SELECT "{column}" FROM {table} ORDER BY id DESC LIMIT 1')
        result = session.execute(query).fetchone()
        return result[0] if result else None

    @staticmethod
    def get_second_latest_value(session: Session, table_name: str, column_name: str) -> object:
        """Значение column_name из предпоследней (по id) строки таблицы.

        То же предупреждение о параллельном прогоне, что и у get_latest_value.
        """
        table = _check_identifier(table_name)
        column = _check_identifier(column_name)
        query = text(f'SELECT "{column}" FROM {table} ORDER BY id DESC LIMIT 2 OFFSET 1')
        result = session.execute(query).fetchone()
        return result[0] if result else None

    @staticmethod
    def update_record(session: Session, table_name: str, column_name: str,
                      column_value, record_id: int) -> None:
        """Обновляет одну колонку строки по id.

        Commit делает контекстный менеджер сессии (db_config.primary_session).
        """
        table = _check_identifier(table_name)
        column = _check_identifier(column_name)
        query = text(f'UPDATE {table} SET "{column}" = :value WHERE id = :record_id')
        session.execute(query, {'value': column_value, 'record_id': record_id})
