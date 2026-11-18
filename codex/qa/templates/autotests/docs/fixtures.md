# Карта фикстур и правила conftest

pytest разрешает фикстуры из conftest.py **той же директории и всех
родительских**. Уровни в этом шаблоне:

```
Tests/conftest.py                         # корень: авторизация, app_data
Tests/Regression_tests/<домен>/conftest.py  # фикстуры домена (create_*, *_cleaner)
<!-- слой: mobile -->
Tests/Mobile_tests/conftest.py            # мобильная инфраструктура
<!-- /слой -->
<!-- слой: selenium -->
Tests/Frontend_tests/conftest.py          # Selenium: driver + скриншот-хук
<!-- /слой -->
<!-- слой: frontend -->
Tests/Frontend_tests/<Страница>/conftest.py # фикстуры страницы (page object)
<!-- /слой -->
```

---

## Правила scope

| Scope | Для чего | Что ЗАПРЕЩЕНО |
|---|---|---|
| `session` | дорогая разовая подготовка: авторизация, подготовка окружения | создавать мутабельные тестовые данные |
| `function` (по умолчанию) | все тестовые данные: создать в setup, удалить в teardown через `yield` | — |

Фикстура **возвращает значение** (`yield resource_id`) — тест принимает его
параметром. Передача данных между тестами через общие словари запрещена.

## Корневой `Tests/conftest.py`

| Фикстура | Scope | Возвращает | Назначение |
|---|---|---|---|
| `app_data` | session | dict | Данные окружения на сессию (креды, ответы bootstrap'а). НЕ для тестовых данных |
| `initialize` | session, autouse | — | Бутстрап: логин через `ExampleAuth.login_as_admin()`, токен → `access_folder["admin"]`. **Адаптируется под проект при форке** |
| `re_login_as_admin` | function | accessToken | Повторная авторизация, если тест инвалидировал сессию |

## Доменные conftest (эталон: `Tests/Regression_tests/example_resource/conftest.py`)

| Фикстура | Scope | Возвращает | Назначение |
|---|---|---|---|
| `create_resource` | function | id ресурса | Создать до теста → yield id → удалить после (teardown терпим к 404) |
| `resource_cleaner` | function | list | Тест аппендит id созданного inline — teardown удаляет всё из списка |
| `smoke_resource` (Smoke_tests) | function | id ресурса | То же, что create_resource, для smoke |

**Каждому новому домену — свой conftest со своей парой `create_<домен>` /
`<домен>_cleaner`** (рецепт — [api-layer.md](api-layer.md), шаг 3). Дубли
маленьких фикстур по доменам — осознанное решение: наглядность важнее DRY.

<!-- слой: mobile -->
## Мобильный `Tests/Mobile_tests/conftest.py`

| Фикстура | Scope | Назначение |
|---|---|---|
| `mobile_data` | session | dict сессионных данных мобильных тестов |
| `launch_appium_server` | session, autouse | Appium-сервер: старт до сессии, стоп после |
| `register_signals` | session, autouse | SIGINT/SIGTERM → корректная остановка Appium |
| `launch_android_emulator` | session | Эмулятор + установка APK; стоп после сессии |
| `install_apk` | function | Установка APK на запущенный эмулятор |
| `screen_recording` | session | Запись экрана на всю сессию |
| `driver` | function, autouse | Свежий Appium-драйвер на каждый тест; quit после |
| `driver_second_session` | function | Драйвер с noReset=True (сохранённая сессия приложения) |

Там же: хук `pytest_runtest_makereport` — при падении прикладывает в Allure
скриншот + XML page_source (`DriverFunctions.attach_failure_diagnostics`,
с guard'ами). Закомментированные образцы: `initialize` для API-предусловий
и `login_in_app` для логина в приложение — раскомментировать и адаптировать
при форке.
<!-- /слой -->

<!-- слой: frontend -->
## Фронтенд
<!-- /слой -->
<!-- слой: selenium -->

`Tests/Frontend_tests/conftest.py`:

| Фикстура | Scope | Возвращает | Назначение |
|---|---|---|---|
| `driver` | function, НЕ autouse | Selenium-драйвер | `get_driver()` → yield → quit. Не autouse: браузер дорог, тест берёт фикстуру параметром явно |
| `example_admin_page` (ExamplePage/) | function | page object | Открывает `FRONTEND_BASE_URL`, возвращает `ExampleAdminPage(driver)` — образец фикстуры страницы |

Там же: скриншот-хук `pytest_runtest_makereport` (PNG + page_source в Allure
при падении, с guard'ами) и закомментированный образец `login_in_admin`
(логин в админку через UI — адаптировать при форке).
<!-- /слой -->
<!-- слой: playwright -->

Фикстуры `page`/`context`/`browser` даёт плагин pytest-playwright (см.
docs/frontend.md), свои не заводятся; эталон директории —
`Tests/Frontend_tests/ExamplePagePW/` (фикстура страницы
`example_admin_page_pw`, вся директория под `pytest.importorskip("playwright")`).
<!-- /слой -->

## Паттерны

**yield-teardown** — фикстура, создающая данные:
```python
@pytest.fixture()
def create_project():
    project_id = Projects.create(name=generate_name("project"))
    yield project_id                      # ← тест получает id
    try:
        Projects.delete(project_id)       # ← teardown после теста
    except Exception as e:
        report_teardown_failure(f"проект {project_id} не удалён: {e}")  # не print: pytest его глотает
```

**cleaner-список** — для данных, создаваемых в самом тесте:
```python
@pytest.fixture()
def project_cleaner():
    created_ids = []
    yield created_ids
    for pid in created_ids:
        try:
            Projects.delete(pid)
        except Exception as e:
            report_teardown_failure(f"проект {pid} не удалён: {e}")
```

**Переопределение autouse-фикстуры** — conftest поддиректории перекрывает
родительскую фикстуру с тем же именем (так мобильные тесты могут заменить
корневой `initialize` своим).

**Ожидание асинхронности внутри фикстуры** — `wait_until` + выборка по ключу:
```python
from src.wait_utils import wait_until
from src import db_config
from src.db_functions import DbInfo

wait_until(
    lambda: _record_ready(entity_id),
    timeout=30,
    message=f"Запись {entity_id} не появилась в БД",
)
```

## Ловушки

- Teardown не должен ронять тест: любые удаления — в try/except с логом.
- Teardown-порядок: фикстуры сворачиваются в обратном порядке объявления.
- autouse session-фикстуры выполняются даже для одного теста — не утяжеляй их.
- Фикстура не видна? Проверь, что conftest.py лежит в директории теста или выше.
