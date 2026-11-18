"""Ожидания с поллингом — вместо слепых time.sleep.

Асинхронная пропагация данных между сервисами занимает непредсказуемое время:
sleep(10) либо тратит время зря, либо не хватает. Поллинг завершится, как
только условие выполнится, и упадёт с понятным сообщением, если не выполнится.
"""

import time
from typing import Callable, TypeVar

T = TypeVar('T')


def wait_until(condition: Callable[[], T], timeout: float = 30, interval: float = 1,
               message: str = "Условие не выполнено") -> T:
    """Вызывает condition, пока она не вернёт истинное значение, и возвращает его.

    ВАЖНО: условие должно возвращать truthy-значение при успехе. Если
    легитимный результат может быть falsy (0, False, "", []), оберните его:
    lambda: fn() is not None.

    ВАЖНО-2: если ждём ИЗМЕНЕНИЯ значения, условие должно проверять
    равенство целевому, а не факт наличия: старое значение обычно тоже
    truthy, и ожидание вернётся немедленно со старым результатом —
    несработавшее действие будет выглядеть как гонка.
        def _status_changed():
            status = Demands.get(demand_id).statusId
            return status if status == target_status_id else None

        wait_until(_status_changed, timeout=20, message="статус не сменился")

    Исключения внутри condition считаются «ещё не готово» и не прерывают
    ожидание (данные могли не доехать). По истечении timeout поднимает
    TimeoutError с message и текстом последней ошибки.

    Пример:
        uid = wait_until(
            lambda: DbInfo.get_value_where(s, "accounts", "uid", "email", email),
            timeout=30,
            message=f"uid для {email} не появился в БД",
        )
    """
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            result = condition()
            if result:
                return result
        except Exception as e:
            last_error = e
        time.sleep(interval)
    details = f" Последняя ошибка: {last_error}" if last_error else ""
    raise TimeoutError(f"{message} (таймаут {timeout} с).{details}")
