---
name: "next"
description: "Продолжить работу по задачам с того места, где остановились, командой `/qa:next`: прочитать карточки   задач в базе знаний, назвать задачу и её следующий шаг и продолжить. Используй в начале сессии, после   перерыва или на другой машине, когда человек спрашивает «что дальше?», «на чём остановились?»,   «продолжаем?», «продолжи» — и из разговора не ясно, какую задачу, — и по команде `/qa:next`. Задача   названа номером или ссылкой — это `qa:task`; нужен только обзор без запуска — `qa:progress`."
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



# `/qa:next` — с чего продолжить

Какую задачу продолжать и с какого шага, говорит скрипт: `${PLUGIN_ROOT}/bin/qa-task next` (зови по имени, он в PATH). Ты —
называешь это человеку и передаёшь задачу скиллу `qa:task`: дальше ведёт он.

**Правила:**
- Строки скрипта показываешь как есть: не пересказываешь, не пересчитываешь, не сортируешь по-своему.
- Выбор между задачами — за человеком. Скрипт вернул несколько — спрашиваешь, а не берёшь «самую свежую».
- Карточка пришла с другой машины (в её строке — имя другой машины): сырьё захода (`runs/` — журнал,
  тела ответов, дампы) в git не ездит, здесь его может не быть. Не ищи его и не восстанавливай по памяти:
  опирайся на карточку, отчёт и кейсы по её ссылкам; не хватает — скажи человеку, чего именно.
- Человек ждал задачу, а её нет в выводе — скажи: возможно, на этой машине не подтянут git. Сам
  `git pull` не делаешь.
- Строка `пропущен <файл>` — чужой или битый файл в `tasks/` (в том числе конфликт слияния git): назови
  его человеку одной строкой; сам не чинишь.
- Всё, что видит человек, — на его языке.

## По выводу `${PLUGIN_ROOT}/bin/qa-task next`

| Вывод | Что делаешь |
|---|---|
| Код 2 | Скажи причину из вывода как есть. «База знаний не найдена» — карточек задач здесь не ведут |
| `открытых задач нет` | Скажи это. Работа начнётся с новой задачи — её ведёт `qa:task` |
| Одна карточка: первая строка `<id> · идёт · …`, ниже `следующий шаг: …` | Скажи человеку одной строкой: какая задача, какой шаг следующий, когда и на какой машине с ней работали. Он просил продолжить — сразу вызови `qa:task` с этим id. Он спрашивал, что дальше, — ответь и спроси, продолжать ли |
| `идут: N — какую продолжать — решает человек` | Покажи строки и спроси одной строкой, какую. После ответа — `qa:task` с её id |
| `идущих задач нет`, ниже `ждут: N` | Покажи строки. Спроси, дождались ли чего-то из этого. Дождались — `${PLUGIN_ROOT}/bin/qa-task resume <id>`, затем `qa:task` с этим id |

В выводе есть и идущая задача, и блок `ждут: N` — после строки про идущую назови ждущие одной строкой: кого
и чего ждут.
