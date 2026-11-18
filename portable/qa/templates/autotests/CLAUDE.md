# CLAUDE.md — Project Guide for Claude Code

This is a **forkable framework template** for AI-assisted test automation.
Layers in this project:

- backend API (pytest + requests) — the core, always present;
<!-- слой: frontend -->
- browser frontend (one library per project: Selenium or Playwright);
<!-- /слой -->
<!-- слой: mobile -->
- native Appium mobile (UiAutomator2/XCUITest; covers native Android/iOS and
  Flutter via Semantics);
<!-- /слой -->

It is intentionally abstract: core infrastructure is real and reusable, while
everything named `example_*` is a canonical sample to copy and adapt.
**No live stand is wired to this template** — tests here are patterns, not
runnable suites; a fork connects them to a real project.

**Read this file first. For deeper detail, follow the links to specific docs below.**

**Правила работы — скилл `qa:rules`.** Вызови его в начале сессии, до первой работы с вики,
спекой API или трекером: там «сам или помощник», поиск и выборки из спеки, секреты, коммиты и
политика трекера. Правила кода этого репо — ниже и в `.claude/rules/`.

---

## Project Layout (one-liner per entry)

```
config.py               — reads ALL settings from env vars (no hardcoded values)
logger.py               — logs every HTTP request/response and mobile action to file
pytest.ini              — pytest config (markers: smoke/regression + one per UI layer)
плагины qa-auto и qa    — скрипты обвязки лежат в bin/ плагинов, в PATH; зовутся по имени, без scripts/:
  openapi_slice.py      — срез большой OpenAPI-спеки по тегу/пути (JSON/YAML; полную спеку в контекст не тащить)
  coverage_check.py     — сверка тегов спеки с пакетами клиентов src/ (полнота покрытия — механически, не руками)
  api_client_check.py   — сверка КЛИЕНТОВ со спекой: импорт модулей, пути/методы/коды, query, тела, поля моделей
  spec_loader.py        — чтение спеки (JSON/YAML) — общее для скриптов обвязки
<!-- слой: frontend -->
  dump_dom.py           — дамп DOM живой страницы с лестницей локаторов (+--walkthrough: человек ведёт сценарий)
<!-- /слой -->
<!-- слой: mobile -->
  dump_ui_tree.py       — дамп UI-дерева мобильного экрана через Appium (+walkthrough: человек или --script-файл агента, --reset-app)
<!-- /слой -->
  preflight.py          — (плагин qa) проверка оснащения машины по разделу «Оснащение машины» docs/toolchain.md (маркер .preflight-ok, привязан к хосту)
<!-- слой: mobile -->
  mobile_keys_audit.py  — аудит ключей Flutter-репо: видны ли они Appium, какие объявлены и не применены
<!-- /слой -->
scripts/check_no_sleep.py — гейт make verify: слепые паузы (time.sleep, wait_for_timeout) в тестовом слое (+test_check_no_sleep.py)
scripts/test_*.py        — тесты обвязки: вручную `.venv/bin/python -m pytest scripts/ -q`, в CI — джоб scripts-tests
docs/toolchain.md       — что поставить на НОВУЮ машину: таблица оснащения (разбирает preflight.py; глазами читать не нужно)
<!-- слой: ui -->
docs/locator-conventions.md — контракт стабильных локаторов с разработчиками (+AI-промпт)
docs/apps-repos.md      — реестр репо продукта вне проекта (админка, мобилка) + что агенту в них можно (читать по требованию)
<!-- /слой -->
docs/articles/            — статьи для тестировщика (обзоры инструментов; оглавление в README папки)
.gitlab-ci.yml          — CI-заготовка для форка: verify / smoke (MR) / regression (schedule) / report
src/http_methods.py     — CENTRAL HTTP client (HttpClient): auto-injects tokens, Allure steps, timeouts
src/common_models.py    — общие pydantic-конверты ответов (ResponseId, PageResult, TokensPair); домены ИМПОРТИРУЮТ, не копируют; форк правит под свой API
src/example_auth.py     — EXAMPLE auth client: login + storing tokens in access_folder
src/db_config.py        — lazy engines + context managers: primary_session(), secondary_session()
src/db_functions.py     — DB helpers (DbInfo): get_value_where (preferred), get_latest_value, update_record
src/data_generators.py  — unique test data generators (id, email, phone, name)
src/deep_merge_json.py  — deep-merges two dicts; used to override specific body fields in tests
src/custom_decorators.py— @deprecated (warning) and @deprecated_test (skip)
src/wait_utils.py       — wait_until(): polling instead of time.sleep
src/example_resource/   — EXAMPLE API client + pydantic models.py — COPY THIS to add a new API domain
Tests/conftest.py       — session fixtures: auth bootstrap (adapt per fork)
Tests/{Smoke,Regression}_tests/ — EXAMPLE happy-path и полный CRUD+негативы (раскладка — .claude/rules/tests.md)
<!-- слой: frontend -->
Tests/Frontend_tests/, frontend/ — браузерный слой (раскладка — .claude/rules/frontend.md)
<!-- /слой -->
<!-- слой: mobile -->
Tests/Mobile_tests/, Appium/ — мобильный слой (раскладка — .claude/rules/mobile.md)
<!-- /слой -->
```

---

## Core invariants (детали — в path-scoped правилах)

Четыре инварианта, которые нужны ДО того, как открыт хоть один файл:

1. **Токены — через `access=`**, не руками: `HttpClient.get(url, access="admin")`.
   Список ролей не фиксирован, его задают auth-фикстуры форка.
2. **`example_*` копируют, а не расширяют.** Эталоны остаются нетронутыми.
3. **Тестовые данные не живут в `scope='session'`** и не передаются между
   тестами общими словарями: каждый тест независим и параллелится.
4. **Никакого хардкода** URL, паролей и ключей — только `config.py` / `os.getenv()`.

Всё остальное — как именно работают клиенты, конверты ответов, БД, фикстуры,
page objects и локаторы — лежит в `.claude/rules/` и **подгружается само**,
когда агент читает файл соответствующего слоя:

| Правило | Срабатывает на |
|---|---|
| `code-conventions.md` | `src/**/*.py`, `Tests/**/*.py` |
| `tests.md` | `Tests/**/*.py` |
<!-- слой: frontend -->
| `frontend.md` | `frontend/**/*.py`, `Tests/Frontend_tests/**/*.py` |
<!-- /слой -->
<!-- слой: mobile -->
| `mobile.md` | `Appium/**/*.py`, `Tests/Mobile_tests/**/*.py` |
<!-- /слой -->

Правила с `paths:` не занимают контекст, пока слой не тронут. Работа МИМО
скилла (правка руками, агент `qa-auto:test-fixer`) получает конвенции так же — это
единственный механизм, который на неё распространяется.

## Quick Reference: What To Do When...

| Task | Where to look |
|---|---|
| Add a new API resource | [docs/api-layer.md](docs/api-layer.md) |
| Add smoke or regression tests | [docs/tests.md](docs/tests.md) |
<!-- слой: mobile -->
| Add a mobile screen / mobile test | [docs/mobile.md](docs/mobile.md) |
<!-- /слой -->
<!-- слой: frontend -->
| Add a frontend test | [docs/frontend.md](docs/frontend.md) |
<!-- /слой -->
| Understand fixtures and conftest | [docs/fixtures.md](docs/fixtures.md) |
| Check DB state in a test | [docs/db.md](docs/db.md) |
| Set up CI / nightly runs in a fork | [.gitlab-ci.yml](.gitlab-ci.yml) + [docs/tests.md](docs/tests.md) |
<!-- слой: ui -->
| Agree stable locators with devs | [docs/locator-conventions.md](docs/locator-conventions.md) |
| Work inside the product repos (add locators to app code) | [docs/apps-repos.md](docs/apps-repos.md) |
<!-- /слой -->

---

## Skill routing map — какой скилл брать

Роутинг делает ГЛАВНЫЙ агент ДО входа в скилл, видя только `description`
скиллов и этот файл. Эта карта — **АВТОРИТЕТ по границам**: описания скиллов
и их Шаг 0 обязаны ей не противоречить. Сигнал маршрутизации живёт здесь и в
`description`/Шаг 0 скилла.

**Прежде чем выбирать — про тестера:**
- **Ключевое слово ≠ слой.** «Мобилка» может значить API за мобильным
  приложением, а не Appium-тест. Уровень неоднозначен → уточни ДО входа в скилл.
- **Серая зона между скиллами** → проговори выбор и trade-off тестеру, не иди
  молча и не кайся потом.
- Нет `docs/project-profile.md` → `/qa-auto:setup-fork` (гейт для всех скиллов ниже).

| Что нужно | Скилл |
|---|---|
| Форк не настроен / правка авторизации, ролей, паспорта | `/qa-auto:setup-fork` |
| Только КОД — API-клиенты + pydantic-модели по спеке, без тестов | `/qa-auto:api-clients` |
| Ревью СУЩЕСТВУЮЩИХ тестов (код не править) | `/qa-auto:review-tests` |
| Починка/отладка ПАДАЮЩИХ тестов | вне скиллов — напрямую / агент `qa-auto:test-fixer` |
| Дефект БЭКЕНДА/стенда (не теста) — оформить для разработчика | `/qa-auto:bug-report` |
| Новые тесты, ОДИН слой, один ресурс/сценарий/страница/экран | слоевой скилл ↓ |
| — API: ресурс, эндпоинт ИЛИ сквозной флоу из нескольких эндпоинтов одного сервиса | `/qa-auto:api-tests` |
<!-- слой: frontend -->
| — Веб-страница / UI-сценарий (Selenium/Playwright) | `/qa-auto:frontend-tests` |
<!-- /слой -->
<!-- слой: mobile -->
| — Экран / фича мобильного приложения (Appium) | `/qa-auto:mobile-tests` |
<!-- /слой -->
<!-- слой: frontend -->
| Локаторы в КОДЕ ПРОДУКТА (чужой репозиторий), веб-админка — `data-testid` | `/qa-auto:keys-admin` |
<!-- /слой -->
<!-- слой: mobile -->
| Локаторы в КОДЕ ПРОДУКТА, мобильное приложение — `Semantics(identifier:)` | `/qa-auto:keys-mobile` |
<!-- /слой -->
<!-- слой: ui -->
| Замечания ревьюера к НАШЕМУ MR с локаторами — ответить, внести правки раунда | тот keys-скилл, которым делался MR (`/qa-auto:keys-mobile` Шаг 11.1, `/qa-auto:keys-admin`): раунд — продолжение прогона с его гейтами и отчётом, а не «мелкая правка мимо скилла» |
<!-- /слой -->
| Полное покрытие ВСЕГО API тестами (все ресурсы спеки) | `/qa-auto:api-suite` |
| Покрытие на 2+ РАЗНЫХ слоях ИЛИ фича/тикет «по полному циклу» с фазами и ревью | `/qa-auto:test-flow` |

**Падение прогона — ЧЕЙ баг?** `qa-auto:test-fixer` и `/qa-auto:bug-report` триггерятся от
одного и того же «тесты красные», развилка по владельцу дефекта: баг в тесте
(фикстура, данные, порядок, забытый conftest) → `qa-auto:test-fixer`, чиним у себя;
дефект бэкенда/стенда (поведение противоречит спеке или паспорту) →
`/qa-auto:bug-report`, чинят там. Не уверен, чей — сначала отсев по Шагу 1
`/qa-auto:bug-report` (воспроизвести вне pytest), и только потом маршрут. Ветка
«молча подстроить тест под стенд» неверна в обоих случаях.

<!-- слой: ui -->
**Локаторы или тесты?** `/qa-auto:keys-admin` и `/qa-auto:keys-mobile` правят ЧУЖОЙ
репозиторий продукта и не пишут ни одного теста; `/qa-auto:frontend-tests` и
`/qa-auto:mobile-tests` пишут тесты и не трогают код продукта. Порядок между ними
жёсткий: локатор → выкат на стенд → повторный дамп → тест
(`docs/apps-repos.md`). «У элементов нет стабильных локаторов» на входе в
тестовый скилл — развилка по доступу: **репозиторий продукта доступен**
(есть в `docs/apps-repos.md`) → сначала keys-скилл, потом тест;
**недоступен** → тест с пометкой техдолга плюс список недостающих
идентификаторов для их команды.
<!-- /слой -->

**Порог оркестраторов** (`api-suite`, `test-flow`) — это ФАН-АУТ: несколько
независимых единиц работы, которые надо координировать параллельно. Считается
по числу СЛОЁВ и РЕСУРСОВ, НЕ по числу эндпоинтов в одном сценарии: сквозной
флоу из пяти эндпоинтов одного сервиса — это один слой, один сценарий →
`/qa-auto:api-tests`, а не оркестратор.

---

## What I Must NOT Do

- **Never hardcode URLs, passwords, API keys, or DB credentials** — only `config.py` via `os.getenv()`
- **Never add `scope='session'` fixtures that create mutable test data** — sessions are shared
- **Never re-introduce project-specific business logic into the template** — forks add it, the template stays abstract
- **Never commit `.env`** — it's gitignored; use `.env.example` for new vars
- **Never call `db_config.primary_db_session` / `secondary_db_session`** — removed; use the context managers `db_config.primary_session()` / `secondary_session()`
- **Never use the old names** (`http_method`, `get_db_info`, `Button_actions`, …) — полный список замен в `.claude/rules/code-conventions.md`
- **Never pass data between tests via shared dicts** — fixtures return values; tests must stay order-independent

---

## Safety hook: hardcode guard

Запрет хардкода выше — не только текст: `check_no_hardcode.py` — PreToolUse-хук
плагина `qa-auto` (`Write|Edit`, включается вместе с плагином), который
блокирует запись литеральных URL и секретов в код тестов и клиентов (`Tests/`,
`src/` и папки слоёв UI) и любую запись в `.env`. Правила исключений и точные шаблоны — в самом
скрипте; строки с `os.getenv`/`config.`, комментарии и `example_*` проходят.
Хук страхует правки агента, но НЕ `git commit`.

---

## Оснащение машины: preflight

Что поставить на НОВУЮ машину — `docs/toolchain.md`: таблица «что / как
проверить / путь / минимум / без неё / как ставить». Она описывает ПРОЕКТ и
лежит в git; чем располагает конкретная машина, отвечает прогон, а не строка в
файле. Проверяет таблицу `preflight.py`:

```bash
preflight.py                # полный прогон
preflight.py --use-marker   # гейт в Шаге 0 скиллов: молчит, если ничего не менялось
```

Исход лежит в `.preflight-ok` — он привязан к ХОСТУ, в `.gitignore`, и на
другой машине недействителен целиком, включая зелёные строки. Коды возврата:
0 — всё на месте, 1 — есть недостачи, 2 — раздел не разобран.

**Скрипт ничего не ставит и не чинит**, и агент тоже: прогон печатает по
каждой недостаче «без неё» (какой класс работы закрыт) и «ставить» (рецепт) —
бери формулировку из ВЫВОДА, саму таблицу в контекст не тяни.

Форк заполняет таблицу под свои слои (в шаблоне — только ядро: `.venv`, pytest,
`.env`) и проставляет в шапке `docs/toolchain.md` «Обновлено» и «Подтверждён
человеком»: неподтверждённой таблице скрипт не доверяет и говорит об этом.

Граница измерения: проверено НАЛИЧИЕ и работоспособность запуска, не
корректность поведения — инструмент, который запускается и врёт, здесь
зелёный. Скрипт — часть плагина `qa`, в проекте его не правят: нашёл ошибку —
скажи человеку.
