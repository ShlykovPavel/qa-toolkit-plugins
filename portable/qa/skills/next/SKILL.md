---
name: "next"
description: "Продолжить работу по задачам с того места, где остановились, командой `/qa:next`: прочитать карточки   задач в базе знаний, назвать задачу и её следующий шаг и продолжить. Используй в начале сессии, после   перерыва или на другой машине, когда человек спрашивает «что дальше?», «на чём остановились?»,   «продолжаем?», «продолжи» — и из разговора не ясно, какую задачу, — и по команде `/qa:next`. Задача   названа номером или ссылкой — это `qa:task`; нужен только обзор без запуска — `qa:progress`."
---

> Portable QA procedures. This section takes precedence over application-specific instructions below.

- Resolve PLUGIN_ROOT to this package directory (two parents above this SKILL.md).
  Resolve shared qa helpers in the sibling qa package; preserve the whole portable directory layout.
  Run bundled scripts by absolute path; do not assume bin is on PATH.
- A named skill such as qa:rules means read the sibling qa/skills/rules/SKILL.md.
  Agent procedures are also skills named role-<name>. Read the procedure and delegate if supported;
  otherwise perform that procedure sequentially. Use the host's actual tools and ask the user normally.
- These are procedures and helpers, not a native plugin for every application. No hooks run automatically.
  Claude-specific settings, installation commands and project templates need a host-specific integration.
  Do not run Claude or Codex installers to configure another host. Report unsupported steps explicitly.



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
