---
paths:
  - "frontend/**/*.py"
  - "Tests/Frontend_tests/**/*.py"
---

# Фронтенд-слой: page objects и локаторы

Правило грузится при чтении файлов `frontend/` и `Tests/Frontend_tests/`.
Полная процедура — [docs/frontend.md](../../docs/frontend.md).

## Библиотека одна — та, что выбрана при `/qa:init` и записана в паспорте

<!-- слой: selenium -->
Ветка `selenium`: page objects — `frontend/front_keys/` (база `ButtonFinder`);
драйвер — `frontend/driver_factory.py` (`BROWSER`, `HEADLESS` из env); ожидания —
`finder_type` по смыслу элемента; эталон тестов — `Tests/Frontend_tests/ExamplePage/`.
Тест не использует `page`/`expect` Playwright.
<!-- /слой -->
<!-- слой: playwright -->
Ветка `playwright`: page objects — `frontend/pw_keys/`; драйвер — фикстуры
pytest-playwright; ожидания — auto-wait + `expect()`; эталон тестов —
`Tests/Frontend_tests/ExamplePagePW/` (нужен `importorskip`). Тест не использует
`driver`/`ButtonFinder` и не знает про `finder_type`.
<!-- /слой -->

## Локаторы

Есть `data-testid` — локатор по нему (`docs/locator-conventions.md`). Ключа нет —
лестница из `docs/frontend.md`, первый доступный якорь; отсутствие ключа —
не повод брать хрупкий селектор молча: см. `docs/apps-repos.md`, при доступном
репозитории продукта локаторы ставит `/qa-auto:keys-admin`, и только потом пишется тест.

<!-- слой: selenium -->
Новая страница → копия `frontend/front_keys/example_service/example_admin_page_keys.py`
в `front_keys/<сервис>/`. Эталон не трогать.
<!-- /слой -->
<!-- слой: playwright -->
Новая страница → копия `frontend/pw_keys/example_service/example_admin_page_pw.py`
в `pw_keys/<сервис>/`. Эталон не трогать.
<!-- /слой -->

## Подготовка данных — через API, не через UI

Сущности для UI-сценария создаются API-клиентами из `src/`, а не кликами.
