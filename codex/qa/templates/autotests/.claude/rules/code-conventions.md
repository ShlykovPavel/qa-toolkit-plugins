---
paths:
  - "src/**/*.py"
  - "Tests/**/*.py"
---

# Конвенции кода: клиенты, ответы, БД

Правило грузится, когда агент читает файл в `src/` или `Tests/`. Глубже —
[docs/api-layer.md](../../docs/api-layer.md) и [docs/db.md](../../docs/db.md).

## Токены живут в `HttpClient.access_folder` — имена задаёт проект

Никогда не передавай токен руками, используй параметр `access=`:

```python
from src.http_methods import HttpClient

HttpClient.get(url, access="admin")   # берёт access_folder["admin"]
```

Фиксированного списка ролей НЕТ: имена решают auth-фикстуры форка («admin»,
«user», «manager», ...). Образец — `src/example_auth.py`: логин → токен в
`access_folder` под выбранным именем. Отсутствующий токен падает сразу —
**не лови это исключение**, чини auth-фикстуру. Не-Bearer авторизация
(cookie, api-key) → правь `HttpClient._build_headers`.

## `deep_merge` для тела и `status_code` для негативных

Методы клиентов принимают `**kwargs` (переопределить поля тела) и
`status_code=` (ожидаемый код ответа):

```python
ExampleResource.create(name="my name", description="custom desc")
ExampleResource.get(999999, status_code=404)     # негативный тест
```

Ответы разбираются в pydantic-модели (`models.py` рядом с клиентом, общие
конверты — из `src/common_models.py`): тест читает атрибуты (`resource.name`),
а не ключи словаря. Тела запросов остаются обычными словарями.
**При ожидаемой ошибке (`status_code >= 400`) метод возвращает None** — не
разыменовывай результат.

## Две БД, короткие сессии через контекстные менеджеры

```python
from src import db_config
from src.db_functions import DbInfo

with db_config.primary_session() as session:      # основная БД
    uid = DbInfo.get_value_where(session, "accounts", "uid", "email", email)
```

`secondary_session()` — для второй БД (включается `DB_SECONDARY` в `.env`).
Предпочитай `DbInfo.get_value_where` (поиск по известному ключу) вместо
`get_latest_value`: «последняя строка» ломается при параллельном прогоне.
Значения всегда идут связанными параметрами.

**Удалённые имена — не использовать:** `primary_db_session`,
`secondary_db_session` (заменены контекстными менеджерами), `http_method`
(→ `HttpClient`), `get_db_info` (→ `DbInfo`), `driver_functions`
(→ `DriverFunctions`), `Button_actions` / `ButtonActions` /
`get_element_by_value_key` (→ `ScreenActions` с `get_element`),
`Button_finder` (→ `ButtonFinder`).
<!-- слой: mobile -->
Старая папка `Flutter_tests` → `Tests/Mobile_tests`.
<!-- /слой -->

## `example_*` копируют, а не расширяют

Новый API-домен → копия `src/example_resource/`. Сами `example_*` файлы
остаются нетронутыми эталонами.

## Никакого хардкода

URL, пароли, ключи и креды БД — только через `config.py` и `os.getenv()`.
Это же проверяет хук `check_no_hardcode.py` плагина `qa-auto` на запись.
