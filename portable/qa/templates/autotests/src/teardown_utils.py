"""Громкое сообщение об отказе уборки — вместо print, который pytest глотает.

ЗАЧЕМ ОТДЕЛЬНЫЙ МОДУЛЬ
Teardown-фикстуры обязаны быть терпимыми: упавшее удаление не должно ронять
уже прошедший тест. Отсюда типовой `except ... : print(...)`. Проблема в том,
что pytest захватывает stdout и у ПРОШЕДШИХ тестов выбрасывает его (под
`pytest -n 4` тем более), поэтому неудалённый ресурс становится невидимым: в
отчёте «все зелёные», а на стенде растёт мусор.

Типовая картина: прогон «все passed», при этом DELETE в teardown дважды
ответил 500 (например, deadlock в БД), ресурсы остались, и в отчёте ни следа —
находится только сравнением списков сущностей до и после.

Поэтому диагностика уборки идёт туда, что pytest НЕ захватывает:
  - `logs/log_*.log` через `Logger.write_log_to_file` — пишется прямо в файл;
  - `warnings.warn` — попадает в сводку pytest даже на полностью зелёном
    прогоне (`warnings summary`).

Использование в teardown любой фикстуры:

    from src.teardown_utils import report_teardown_failure

    try:
        ExampleResource.delete(resource_id)
    except Exception as e:  # noqa: BLE001 — teardown обязан быть терпимым
        report_teardown_failure(f"ресурс {resource_id} не удалён: {e}")
"""

import warnings

from logger import Logger

#: Сколько символов текста ошибки оставлять. Стенд может вернуть многокилобайтный
#: стектрейс — целиком они забивают и лог, и сводку варнингов, а для
#: опознания причины хватает начала.
ERROR_TEXT_LIMIT = 300

#: Признаки ответа «ресурса уже нет». Такой отказ уборки — НЕ проблема:
#: задача teardown'а — чтобы ресурса не осталось, а он и так отсутствует
#: (обычно его удалил сам тест, а cleaner добивает список). Поднимать по этому
#: поводу warning вредно: 4 шумных предупреждения на прогон обесценивают
#: сводку, и настоящая утечка в ней теряется.
#: Форк дописывает сюда формулировку «не найдено» своего API.
ALREADY_ABSENT_MARKERS = ('"status":404', "Resource not found", "Ресурс не найден")


def report_teardown_failure(message: str) -> None:
    """Сообщить об отказе уборки в лог прогона И предупреждением pytest.

    message — что именно не удалилось, с id ресурса: по нему человек убирает
    остаток руками, поэтому id обязателен.

    Исключение — «ресурса уже нет» (404): пишется только в лог, без warning,
    см. ALREADY_ABSENT_MARKERS.
    """
    text = str(message)[:ERROR_TEXT_LIMIT]
    if any(marker in str(message) for marker in ALREADY_ABSENT_MARKERS):
        Logger.write_log_to_file(f"\nTEARDOWN: ресурса уже нет, уборка не нужна: {text}\n")
        return
    Logger.write_log_to_file(f"\nTEARDOWN FAILURE: {text}\n")
    warnings.warn(f"Уборка не удалась: {text}", stacklevel=2)
