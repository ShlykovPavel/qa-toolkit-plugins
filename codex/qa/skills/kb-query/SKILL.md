---
name: "kb-query"
description: "Ответ на вопрос по базе знаний проекта: найти нужные страницы через `index.md`, прочитать их   самому, ответить со ссылками на страницы и первоисточники, отделить «есть в источниках» от   «мой вывод» и «пробел в данных», назвать дату, на которой стоит ответ, и не сгладить   расхождения. Используй, когда спрашивают «что в базе про X», «что написано в вики про флоу,   статусы, лимиты, коды ошибок», просят найти правило, контракт или тест-кейс в базе знаний,   а также когда ответа в базе может не оказаться — тогда честное «нет» и откуда взять."
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



# Запрос к базе знаний

## Порядок

Пути в этом скилле — от корня вики; корень печатает `${PLUGIN_ROOT}/bin/qa-paths wiki` (папка может называться не
по шаблону).

1. Прочитать `index.md`, найти релевантные страницы, прочитать их.
2. Ответить со ссылками на страницы и первоисточники.
3. Явно отделять «есть в источниках» от «мой вывод» и «пробел в данных».
4. **Проверять свежесть**: по теме несколько источников разных дат — назвать дату того, на
   котором строится ответ. Расхождения не сглаживать: обе позиции с датами.
5. Ценный ответ предложить сохранить в `wiki/notes/` и залинковать.

## Искомого нет — это ответ

Проверил названные места (`index.md` → страница раздела, `raw/`) и не нашёл — скажи «нет» и
спроси, откуда взять. Обход базы в ширину не разворачивай: три исхода — страницы нет, но есть
сырьё (предложи ингест, скилл `kb-ingest`); нет ни страницы, ни сырья (назови, чего не хватает,
и попроси источник); база пуста (это непройденный онбординг проекта, а не пробел поиска).

## Сам читаешь или отдаёшь помощнику

Страницы `wiki/**`, `index.md`, `log.md` основной агент читает сам, какого бы размера они ни
были: дословность (даты, `AS-IS`/`TO-BE`, `## Расхождения`) в пересказе теряется, а распухшая
страница — повод её разделить. Помощнику отдают сырьё (`raw/**`, сваггер, API-спека) и поиск
(«где про X», обход, сверка). Писать в базу может только основной агент.

**Ты помощник, присланный с Task:**

- Только читаешь: ничего не создаёшь и не правишь (ни страниц, ни `## Расхождения`, ни
  `log.md`), не коммитишь, ингест не делаешь — из источника в `raw/` приносишь тезисы.
- Твой ответ — весь результат, человек его не увидит. Верни пути 2–3 страниц по вопросу —
  основной агент дочитает их сам — и выжимку: точные значения (статусы, лимиты, TTL, коды
  ошибок, эндпоинты), задачи трекера и даты документов, `AS-IS`/`TO-BE` с датой, «есть в
  источниках» / «мой вывод» / «пробел в данных», расхождения обеими позициями с датами.
- Тебя могут переспросить: нужна дословная цитата из большого файла `raw/` — достань её.

**Язык.** Страницы на языке, на котором уже написана вики (пустая — на языке человека);
идентификаторы — имена типов, коды ошибок, пути эндпоинтов — как в коде.

## Что где искать

Карта разделов базы и особенности домена — в `CLAUDE.md` самой базы знаний проекта. Жанры
страниц и их шаблоны — `../kb-ingest/references/page-conventions.md`.
