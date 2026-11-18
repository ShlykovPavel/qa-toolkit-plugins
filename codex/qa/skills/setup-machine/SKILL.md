---
name: "setup-machine"
description: "Довести машину до готовности к QA-проекту командой `/qa:setup-machine`: прогнать проверку оснащения,   показать недостачу одним сообщением и поставить недостающее по одному пункту, на каждый — «да» человека   (в том числе собрать `.venv` автотестов и поставить зависимости); про `.env` — только какие переменные нужны и   где их взять. Используй, когда человек просит: `/qa:setup-machine`, «настроить машину», «поставить   зависимости», «собрать venv», «чего не хватает на машине» (в том числе в ответ на твоё упоминание недостачи   при старте сессии — сам по этому сообщению не запускай). Не для развёртывания проекта (`/qa:init`) и не для заполнения `.env`."
---

> Codex runtime (adapter v3). This section overrides Claude-specific runtime instructions below.
> Source procedures and Claude project files stay shared; do not rewrite them for Codex.

- Resolve `PLUGIN_ROOT` to this installed plugin's directory (two levels above the skill directory).
  Include `export PLUGIN_ROOT=<resolved absolute path>` in each shell invocation using the variable.
  Codex does not promise plugin `bin/` on PATH; call its scripts by full package-relative path.
  Shared `qa-*` helpers belong to the installed `qa` plugin; resolve that root separately when needed.
- Ask the human using the available Codex question tool or a normal message; preserve required approvals.
- Named agent roles are available as `skills/role-<name>/SKILL.md`. Read the role and pass its full procedure
  to `spawn_agent` when available. Do not use Claude `subagent_type` or assume a named profile is registered.
  Otherwise perform the same roles sequentially. Inherit the current model unless the human specifies one.
- `qa-init.py` and `qa-sync.py` in this distribution create/update both Claude files and Codex companions.
  Claude plugin installation is separate: do not execute `claude plugin install/update` to repair Codex.
  Install/update Codex from the user bundle as described in README.md; no workshop checkout is required.
- At the end of a QA turn verify lab evidence was saved. Hooks collect on Stop/Interrupt/SessionEnd,
  and catch up on SessionStart. If hooks did not run, call the installed qa/bin/qa_codex.py
  `catch-up --cwd <QA-root>` before the task's normal Git commit. Evidence stages only its own files.
  `lab: off` disables collection. Never claim saved evidence or successful installation without checking.



# `/qa:setup-machine` — недостающее на этой машине, по одному

Механику делает скрипт `${PLUGIN_ROOT}/bin/qa-machine.py` (зови по имени, он в PATH): опись, прогон `preflight`, сборка `.venv`. Ты —
показываешь, спрашиваешь, ставишь после «да», отчитываешься. Что чего стоит и чем ставится, не выдумываешь: берёшь из
вывода скрипта (колонки таблицы оснащения «Без неё» и «Как ставить»).

**Правила на весь заход:**
- Ничего не ставишь без прямого «да» человека на **этот** пункт в этом заходе. «Да» на один пункт — не «да» на
  следующий. Молчание, «ну давай всё» до показа команды — не ответ на пункт: покажи команду и спроси.
- `.env` не создаёшь, не читаешь, не правишь и значений не спрашиваешь — ни `.env`, ни `.env.example` не открываешь.
  Имена переменных берёшь из описи. Прислал человек значения в чат — никуда их не пишешь, напомни положить в файл
  самому.
- Команду из «Как ставить» запускаешь как написана. Упала — покажи последние строки вывода и спроси, что дальше; в
  обход (`sudo`, `--break-system-packages`, другой менеджер пакетов, скачать руками) сам не идёшь.
- Всё, что меняет эта процедура, — машинное: `.venv`, `.preflight-ok`, инструменты в системе. В git ничего не
  коммитишь.
- Всё, что видит человек, — на его языке; пока он не написал ни слова текстом — по-русски.

## Шаг 1 — опись

`${PLUGIN_ROOT}/bin/qa-machine.py survey` из папки сессии (скрипт сам находит папки-роли проекта: корень или папку роли с соседом).
Прогон идёт секунды: в каждой папке с таблицей оснащения он запускает `preflight` и обновляет маркер этой машины.

- Код 2 — это не QA-проект: скажи и предложи `/qa:init`, заход кончается.
- Код 0 — всё на месте: скажи одной строкой «машина готова: оснащение проверено, `.venv` и `.env` на месте» и
  добавь строки `folders[].preflight.notes`, если есть. Заход кончается.
- Код 1 — пункты в `items`. У папки `preflight.code` = 2 — таблица не разобралась: покажи `preflight.error` как есть.

## Шаг 2 — одно сообщение с недостачей

Одним сообщением, по папкам (`folder`), по пункту на строку: что (`what`), почему (`why`), что без него закрыто
(`without`), и кто ставит:
- **ставлю я, после твоего «да»** — `kind: venv` и `kind: tool`, у которых `install` — готовая команда;
- **только ты** — `kind: env` (всегда); `tool`, у которого `install` пуст или не команда, а действие человека:
  нужен `sudo`, пароль или вход в учётку, App Store или скачать с сайта, скрипт из сети (`curl … | sh`), «ставит
  ЧЕЛОВЕК», склонировать чужой репо, «приезжает с репозиторием» (значит, файла нет в клоне — спросить у команды).

Для `env`: имена из `names` (пусто — «таблица требует `.env`, имён в ней нет»), где взять — `example: true`:
«`cp .env.example .env` в папке `<folder>` и заполнить руками; значения — у того, кто ведёт стенд, или в менеджере
паролей команды». Строки `folders[].preflight.notes` — в конце сообщения, как есть.

В конце сообщения — порядок: сначала `.venv` (от него зависят строки про pytest), потом инструменты по списку.

## Шаг 3 — по одному, с «да» на каждый

Для каждого пункта «ставлю я», по порядку, спроси человека и дождись ответа. В вопросе — что ставишь, точная
команда, в какой папке она идёт и что она меняет (папку проекта или систему); варианты: «да», «пропустить», «стоп».
- **«да»** — запусти команду. Для `venv` — `install` как есть (`${PLUGIN_ROOT}/bin/qa-machine.py venv <папка>`); с `--recreate` скажи
  в вопросе, что старая папка `.venv` очищается целиком. Для `tool` — команда из `install` в папке `folder` (без
  хвоста про платформу вроде «, macOS»). В рецепте несколько вариантов («`corepack enable` либо `npm i -g yarn`») —
  спроси, какой, и запускай только выбранный. Покажи итог одной-двумя строками.
- `venv` ответил кодом 2 — покажи причину как есть. «Python ниже минимума» — спроси, какой python взять (варианты —
  что есть в PATH: `python3.12`, `python3.13`…), и повтори с `--python` после «да».
- `venv` напечатал строку про браузер playwright — это отдельный пункт: спроси так же, как любой другой.
- **«пропустить»** — дальше по списку. **«стоп»** — сразу к шагу 4.

## Шаг 4 — отчёт

Снова `${PLUGIN_ROOT}/bin/qa-machine.py survey` и одним сообщением: что поставлено в этом заходе, что осталось (с `without` — что без
него закрыто) и кто это делает — ты после «да» в следующий раз или человек сам (`.env`, установки с `sudo` и
прочее из шага 2). Проверено наличие и запуск инструментов, не корректность их работы — скажи это одной строкой,
если что-то ставил. Всё на месте — при следующем старте сессии предупреждения о машине не будет.
