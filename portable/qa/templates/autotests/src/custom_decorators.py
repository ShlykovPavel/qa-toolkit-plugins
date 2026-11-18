"""Пользовательские декораторы для тестов и хелперов."""

import functools
import warnings

import pytest


def deprecated_test(func):
    """Помечает тест как устаревший — pytest пропустит его с понятной причиной.

    Пример:
        @deprecated_test
        def test_old_flow(create_user):
            ...
    """
    return pytest.mark.skip(reason=f"Тест {func.__name__} устарел")(func)


def deprecated(func):
    """Помечает вспомогательную функцию как устаревшую.

    Функция продолжает работать, но при каждом вызове выдаёт DeprecationWarning —
    видно в выводе pytest (-W) и в логах, при этом ничего не ломается.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        warnings.warn(
            f"Функция {func.__name__} устарела и будет удалена",
            DeprecationWarning,
            stacklevel=2,
        )
        return func(*args, **kwargs)
    return wrapper
