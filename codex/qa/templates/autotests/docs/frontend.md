# Как писать фронтенд-тесты (две ветки: Selenium и Playwright)

Шаблон поддерживает ДВЕ библиотеки фронтенд-тестов. Выбор делает форк в
интервью `/setup-fork`; он записан в паспорте проекта
(`docs/project-profile.md`, фронт-секция, поле **«Библиотека
фронтенд-тестов: `selenium` | `playwright`»**). Поля нет → дефолт
`selenium`. Аргументы выбора — статья
[articles/selenium-or-playwright.md](articles/selenium-or-playwright.md).

**Правило ветвления (пока-ёке — не смешивать).** `/qa:init` кладёт в проект файлы
только выбранной ветки:

<!-- слой: selenium -->
Selenium-ветка: эталон page object —
`frontend/front_keys/example_service/example_admin_page_keys.py`, эталон теста —
`Tests/Frontend_tests/ExamplePage/`, лестница локаторов — раздел «Selenium-ветка»
ниже, ожидания — `finder_type` у ButtonFinder, дамп «глаз» — `dump_dom.py`
(дефолт `--locators css`), зависимости — requirements.txt. Тест не использует
`page`/`expect`.
<!-- /слой -->
<!-- слой: playwright -->
Playwright-ветка: эталон page object —
`frontend/pw_keys/example_service/example_admin_page_pw.py`, эталон теста —
`Tests/Frontend_tests/ExamplePagePW/`, лестница локаторов — раздел
«Playwright-ветка» ниже, ожидания — auto-wait + `expect()`, дамп «глаз» —
скрипт на playwright из `.venv` проекта (`dump_dom.py` требует selenium,
его в этой ветке нет), зависимости — `requirements-playwright.txt` и
`playwright install chromium`. Тест не использует `driver`/ButtonFinder.
<!-- /слой -->

---

## Архитектура (обе ветки)

```
<!-- слой: selenium -->
frontend/driver_factory.py                 # selenium: get_driver() по env (headless)
frontend/front_keys/element_finder.py      # selenium: ButtonFinder с ожиданиями
frontend/front_keys/<сервис>/<страница>_keys.py   # selenium page object
<!-- /слой -->
<!-- слой: playwright -->
frontend/pw_keys/<сервис>/<страница>_pw.py        # playwright page object
<!-- /слой -->
<!-- слой: selenium -->
dump_dom.py                        # «глаза»: дамп DOM, --locators css
Tests/Frontend_tests/conftest.py           # selenium: driver + скриншот-хук
<!-- /слой -->
Tests/Frontend_tests/<Страница>/           # тесты: своя директория + conftest + __init__.py
```

Общее для веток: один файл page object — одна страница/раздел UI, по
`@property` на элемент, **никакой логики — только локаторы**; тесты — в
своей директории с conftest и `__init__.py`.

## «Глаза»: дамп DOM и Playwright MCP (обе ветки)

Локаторы снимаются с живой страницы, не выдумываются.
<!-- слой: playwright -->
Дамп — скрипт на playwright (`/frontend-tests`, Шаг 2).
<!-- /слой -->
<!-- слой: selenium -->
Основной путь — `dump_dom.py` (работает везде, где есть venv и браузер):

```bash
dump_dom.py --url https://admin.example.com/users
dump_dom.py --url page.html --scope "#main" --wait 3 --out dump.json
```

Выход — JSON: интерактивные элементы (`a, button, input, select, textarea,
[role=button], [onclick]`, элементы с `data-testid`, а также
`[role=alert]/[role=status]` — тосты/индикаторы для проверок результата);
у каждого — tag, видимый текст, `visible` и кандидат-локатор по лестнице
выбранной ветки. Нет стабильного уникального локатора — кандидат-как-есть
с флагом `"fragile": true` (в тест идёт только с пометкой техдолга).
В конце сводка: всего / с testid / хрупких. Путь к html-файлу без схемы
резолвится от cwd в `file://` — относительные пути фикстур из паспорта
работают из корня репо.

Одиночный дамп по URL покрывает только страницы, доступные без состояния.
Страницы ЗА ЛОГИНОМ и состояния БЕЗ своего URL (модалки, тосты, шаги
визарда, ошибки валидации) снимаются **проходом сценария**
(`--walkthrough`) — одна живая не-headless сессия, человек ведёт сценарий,
скрипт снимает дамп+скриншот на каждый шаг. Все способы и рецепты — в
секции «Как показать агенту страницы — инструкция для человека» ниже;
агент предлагает выбор на старте.
<!-- /слой -->

**Playwright MCP** (опция — «глаза» интерактивнее, нужен node/npx; обзор,
тулы и грабли — статья [articles/playwright-mcp.md](articles/playwright-mcp.md)):

```bash
claude mcp add playwright -- npx @playwright/mcp
```

и allowlist его инструментов `mcp__playwright` в `.claude/settings.json`
(применяет человек). Правило: **скилл использует Playwright MCP, если он
подключён и доступен, иначе — дамп скриптом своей ветки**; результат тот
же — локаторы только с живой страницы. MCP — глаза для ОБЕИХ веток (это
инструмент осмотра, не библиотека тестов).

Нюанс: `file://`-навигация у @playwright/mcp ЗАБЛОКИРОВАНА по умолчанию
(проверено 2026-07-12). Для статических file-фикстур используй дамп скриптом
(file:// ему не помеха) либо регистрируй сервер с флагом
`--allow-unrestricted-file-access`. Для обычных http(s)-страниц админки
ограничение не мешает. Библиотеки playwright это НЕ касается — file:// в
тестах работает.

## Как показать агенту страницы — инструкция для человека

Чтобы написать UI-тест, агент должен «увидеть» страницу: из каких
элементов она состоит и какие у них селекторы. Глаза агента — дамп DOM
(и скриншоты шагов в проходе сценария). Селекторы снимаются с живой
страницы, не выдумываются. Агент в начале работы сам предложит выбор;
шпаргалка, что выбирать:

| Твоя ситуация | Способ |
|---|---|
<!-- слой: selenium -->
| Страница открывается по URL без логина (или file-фикстура) | **А — одиночный дамп** (как в примерах выше) |
| Страница за логином; сценарий из нескольких шагов; состояния без своего URL — модалки, тосты, шаги визарда, ошибки валидации | **Б — проход сценария** (`--walkthrough`) |
<!-- /слой -->
| В Claude Code подключён Playwright MCP | **В — MCP-проход** (агент смотрит сам) |
| Страницы/стенда нет | **Г — автономный режим** по допущениям |

<!-- слой: selenium -->
Общее предусловие для А и Б: venv репозитория и установленный браузер
(Selenium Manager сам скачает драйвер, первый запуск ходит в сеть).
Итог рецептов А/Б — файл(ы), которые ты отдаёшь агенту, плюс словами:
что за страница и что за сценарий.

**Рецепт А — одиночный дамп по URL (страницы без состояния).**

```bash
dump_dom.py --url https://admin.example.com/users --out dump_users.json
```

Дамп каждой страницы сценария — отдельной командой. Отдать: json-файл(ы).

**Рецепт Б — проход сценария (`--walkthrough`) — за логином и для
состояний без URL.**

```bash
dump_dom.py --walkthrough dumps/create_user \
    --url https://admin.example.com/login          # стартовая страница (опционально)
```

Скрипт откроет ВИДИМОЕ окно браузера (HEADLESS форсируется в false) и
будет ждать тебя. Логинишься и ведёшь сценарий руками, **после каждого
шага** возвращаешься в терминал, пишешь короткое имя шага (например
`otkryl_formu`) и жмёшь Enter — скрипт снимает дамп DOM и скриншот
текущего состояния (модалка/тост на экране попадут в дамп). Пустой Enter
тоже работает (имя даст сам). Закончил — введи `q`. Сессия одна на весь
проход: логин и состояние страницы между шагами не теряются.
Отдать: папку `dumps/<имя_сценария>` целиком (внутри `step_NN_*.json`,
скриншоты и `steps.json` — из него агент восстановит и шаги, и селекторы;
шаги — почти готовые методы page object).
<!-- /слой -->

**Рецепт В — Playwright MCP (если подключён).** Дампы агент снимает сам:
живые http(s)-страницы он открывает и осматривает через MCP-инструменты
(снапшот + селекторы), логин и шаги можно вести в диалоге («шаг: открыл
форму» — агент снимает состояние). Отдавать ничего не нужно. Ограничение
file:// — см. нюанс выше.

**Рецепт Г — страницы нет.** Агент работает в автономном режиме: селекторы
из вводных и допущений, каждый помечен `ДОПУЩЕНИЕ`, в отчёте — строка
«сверить с живым DOM до прогона». Это худший режим — используй его, только
когда показать страницу действительно нечем.

## Что спросить у человека (обе ветки)

1. Какая библиотека в паспорте? Поля нет — уточнить/принять дефолт selenium.
2. Есть ли у фронта `data-testid` (или аналог)? Если нет — попросить добавить
   для ключевых элементов вместо охоты за хрупкими локаторами.
   Для playwright-ветки просьба та же; связанный label (for=/aria-label) —
   добавка для элементов, у которых ключа ещё нет.
3. URL страниц и роль/креды для входа.
4. Как реально выглядит DOM: локаторы снимаются с живой страницы
   (дамп скриптом / Playwright MCP / DevTools), не выдумываются.

## Принципы тестов (обе ветки)

- **Предусловия — через API, не через UI**: данные для проверки страницы
  создаются API-клиентами из `src/` (быстрее и стабильнее), UI проверяет
  отображение и взаимодействие. Нет нужного API-клиента — сначала
  клиент (`/api-clients`), а не UI-предусловия.
- Headless-режим по умолчанию, маркер `frontend` (объявлен в pytest.ini),
  модульный `pytestmark`, allure epic "Frontend".
- Тест живёт в своей директории `Tests/Frontend_tests/<Страница>/` с
  conftest и `__init__.py` — как домены API-слоя.
- Браузер НЕ создавать на уровне импорта/класса — только внутри
  function-фикстуры, иначе коллекция падает без браузера.

## Команды прогона (обе ветки)

```bash
make frontend                     # весь фронт-слой (маркер frontend)
pytest -x -q -m frontend Tests/Frontend_tests/<Страница>/   # один домен
```

В шаблоне фронтенд-тесты не гоняются (нет стенда) — прогон включается
в форке с заполненным `.env` (`FRONTEND_BASE_URL`, креды UI).

## Верификация (без живого стенда, обе ветки)

```bash
make verify   # компиляция + pytest --collect-only (фронт-тесты в коллекции)
```

Пример playwright-ветки защищён `pytest.importorskip("playwright")` —
коллекция зелёная и в окружении без playwright.

<!-- слой: selenium -->
---

# Selenium-ветка

## ButtonFinder: поиск с ожиданием

Каждый `find_element_by_*` ждёт элемент до 10 секунд (WebDriverWait) и
**поднимает AssertionError с понятным сообщением**, если не дождался —
None не возвращается никогда, «тихих» падений нет.

Второй параметр `finder_type` — условие ожидания:

| finder_type | Условие | Когда использовать |
|---|---|---|
| `"Dom_located"` (default) | элемент есть в DOM | чтение текста, проверки наличия |
| `"Clickable"` | элемент кликабелен | кнопки, ссылки — всё, по чему кликаем |
| `"Visible"` | элемент видим | тосты, модалки, индикаторы |
| `"Invisible"` | элемент невидим/исчез | ожидание закрытия модалки, спиннера |

## Лестница селекторов selenium-ветки (сверху вниз)

1. **data-атрибут** — `find_element_by_css_selector('[data-testid="save"]')`:
   у элемента есть `data-testid` — всегда он ([locator-conventions.md](locator-conventions.md))
2. `id` — `find_element_by_id("save-btn")`
3. `name` — `find_element_by_name("email")`
4. css-класс/селектор — `find_element_by_css_selector('.btn-save')`
5. xpath — только когда css не выражает условие
6. текст ссылки (`link_text`) — крайний случай: ломается при смене локализации

Найденный хрупкий селектор (по тексту, по индексу, по длинному xpath) —
фиксируй как техдолг в комментарии рядом.

## Рецепт нового page object (selenium)

```bash
cp frontend/front_keys/example_service/example_admin_page_keys.py \
   frontend/front_keys/<сервис>/<страница>_keys.py
```

```python
from frontend.front_keys.element_finder import ButtonFinder


class UsersPage(ButtonFinder):

    @property
    def create_user_button(self):
        return self.find_element_by_css_selector('[data-testid="create-user"]', "Clickable")

    @property
    def success_toast(self):
        return self.find_element_by_css_selector('.toast-success', "Visible")
```

- Имя класса — `<Страница>Page`, свойства — `snake_case` с суффиксом роли
  элемента (`_button`, `_input`, `_link`, `_toast`).
- Группируй свойства комментариями по разделам страницы (см. эталон).

## Driver-фабрика и env (selenium)

`frontend/driver_factory.py` → `get_driver()`. Настройки только из env:

| Переменная | Дефолт | Значения |
|---|---|---|
| `BROWSER` | `chrome` | `chrome` / `firefox` |
| `HEADLESS` | `true` | строки `true`/`false` (парсится `_env_flag`, не `bool()`) |
| `WINDOW_SIZE` | `1920x1080` | `<ширина>x<высота>` |
| `FRONTEND_BASE_URL` | — | базовый URL веб-интерфейса, читается через `config.py` |

Chrome поднимается с `--headless=new --no-sandbox --disable-gpu`.
Selenium Manager сам скачивает драйвер браузера (нужен установленный
браузер; первый запуск ходит в сеть за драйвером). Базовый URL фабрика
не знает — тесты берут `config.FRONTEND_BASE_URL`.

## Фикстуры selenium-ветки (Tests/Frontend_tests/conftest.py)

| Фикстура | Scope | Назначение |
|---|---|---|
| `driver` | function, НЕ autouse | `get_driver()` → yield → quit. Браузер дорог — тест берёт фикстуру параметром явно, только если нужен |
| `login_in_admin` (образец, закомментирован) | function | Логин в админку через UI: page object логина + креды из env — раскомментировать и адаптировать при форке |

Скриншот-хук `pytest_runtest_makereport` (там же): на падении в
`setup`/`call` прикладывает к Allure скриншот PNG и `page_source`.
Guard'ы обязательны — тест мог упасть до создания драйвера; драйвер
достаётся из `item.funcargs`, диагностика в try/except.
<!-- /слой -->
<!-- слой: playwright -->

---

# Playwright-ветка

## Установка (в форке, выбравшем playwright)

```bash
pip install -r requirements-playwright.txt
playwright install chromium
```

## Лестница локаторов playwright-ветки (сверху вниз)

1. **`get_by_test_id("admin_users_create_button")`** — у элемента есть
   `data-testid`: всегда он ([locator-conventions.md](locator-conventions.md) —
   по видимому тексту тесты не ищут).

Ключа нет — ступени ниже, и каждая — техдолг «попросить у фронтов data-testid»:

2. `get_by_role(role, name=...)` — роль + accessible name:
   `page.get_by_role("button", name="Сохранить")`
3. `get_by_label("Имя")` — инпуты со связанным label (for=/обёртка/aria-label)
4. `get_by_placeholder("Поиск по имени")` — когда label не связан
5. `locator("<css>")` / xpath — резерв

css-классы и xpath в playwright-ветке — НЕ норма, а сигнал недоступной
вёрстки.

## Ожидания: auto-wait + expect (никаких finder_type)

Действия (`click()`, `fill()`) сами ждут, пока элемент станет actionable.
Ожидаемый результат проверяй web-first ассертами:

| Проверка | Как |
|---|---|
| Тост/модалка появились | `expect(locator).to_be_visible()` |
| Элемент исчез | `expect(locator).to_be_hidden()` |
| Текст результата | `expect(locator).to_have_text("Пользователь создан")` |
| Значение поля | `expect(locator).to_have_value(...)` |

`time.sleep` и ручные poll-циклы запрещены — как и в selenium-ветке.

## Рецепт нового page object (playwright)

```bash
cp frontend/pw_keys/example_service/example_admin_page_pw.py \
   frontend/pw_keys/<сервис>/<страница>_pw.py
```

```python
from playwright.sync_api import Locator, Page


class UsersPagePw:

    def __init__(self, page: Page):
        self.page = page

    @property
    def create_user_button(self) -> Locator:
        return self.page.get_by_test_id("admin_users_create_button")

    @property
    def success_toast(self) -> Locator:
        # техдолг: у тоста нет data-testid — попросить у фронтов
        return self.page.get_by_role("alert")
```

Конвенции имён — те же, что в selenium-ветке (`<Страница>Pw`, суффиксы
`_button`/`_input`/`_toast`).

## Фикстуры playwright-ветки

Инфраструктуру даёт плагин `pytest-playwright`: фикстуры `page`, `context`,
`browser` из коробки, headless — дефолт, браузер — флагом
`--browser chromium|firefox|webkit`, скриншоты — `--screenshot
only-on-failure`. Своей driver-фабрики и скриншот-хука ветке НЕ нужно.
Директория теста начинается с `pytest.importorskip("playwright")`
(и conftest, и модуль теста) — иначе коллекция упадёт в окружении без
playwright. Эталон — `Tests/Frontend_tests/ExamplePagePW/`.
<!-- /слой -->

## Копилка ловушек проекта

Сюда скиллы дописывают ловушки, найденные в работе на этом проекте
(формат: «сигнатура → как избегать», одна строка на ловушку; дедуп
против уже записанных). Пока пусто.
