"""Подключения к базам данных.

Движки создаются лениво: импорт модуля не требует доступных БД и заданных
переменных окружения — `pytest --collect-only` работает без .env.

Сессии короткоживущие — берите их через контекстные менеджеры:

    from src import db_config
    from src.db_functions import DbInfo

    with db_config.primary_session() as session:
        value = DbInfo.get_value_where(session, "accounts", "uid", "email", email)

Контекстный менеджер сам делает commit при успехе, rollback при ошибке
и всегда закрывает сессию — упавший запрос не оставит соединение
в сломанном состоянии для следующих тестов.
"""

from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

import config

_engines: dict = {}


def _get_engine(name: str, url: Optional[str]) -> Engine:
    if name not in _engines:
        if not url:
            raise RuntimeError(
                f"Строка подключения для БД '{name}' не задана. "
                f"Заполните переменную окружения в .env (см. .env.example)."
            )
        # pool_pre_ping отбрасывает мёртвые соединения (стенд мог перезапуститься)
        _engines[name] = create_engine(url, pool_pre_ping=True)
    return _engines[name]


@contextmanager
def primary_session() -> Iterator[Session]:
    """Короткоживущая сессия основной БД сервиса."""
    session = sessionmaker(bind=_get_engine('primary', config.DB_PRIMARY))()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def secondary_session() -> Iterator[Session]:
    """Короткоживущая сессия второй БД (пример — включите DB_SECONDARY в .env)."""
    session = sessionmaker(bind=_get_engine('secondary', config.DB_SECONDARY))()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
