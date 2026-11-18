---
name: "progress"
description: "Обзор задач командой `/qa:progress`: что идёт, что ждёт человека, что ждёт других (разработчика, стенд),   что закрыто за неделю — по карточкам задач в базе знаний. Используй, когда человек спрашивает «что у нас   открыто?», «что по задачам?», «что висит?», «что от меня нужно?», «что закрыли за неделю?», и по команде   `/qa:progress`. Только показывает: ничего не запускает и не меняет. Продолжить работу — `qa:next`,   взять задачу — `qa:task`."
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



# `/qa:progress` — что по задачам

Обзор готовым отдаёт скрипт: `${PLUGIN_ROOT}/bin/qa-task progress` (зови по имени, он в PATH; другой срок для закрытых —
`--days <N>`). Ты показываешь его человеку.

- **Группы, порядок и числа — из вывода, как есть.** Не пересчитываешь, не переставляешь, не сворачиваешь
  строки в пересказ и не добавляешь оценок («зависла», «пора закрыть»).
- Группа «ждут человека» — то, что нужно от него самого; скрипт ставит её первой.
- Человек спросил про одну задачу подробнее — `${PLUGIN_ROOT}/bin/qa-task show <id>`: шаги, что нужно от него, решения, ход.
- Ищет, делали ли что-то похожее, — `${PLUGIN_ROOT}/bin/qa-task find <слово>`: по всем карточкам, закрытые тоже.
- Ничего не запускаешь и в карточках не меняешь. Человек выбрал задачу — её ведёт `qa:task`.
- Код 2 — скажи причину из вывода как есть (чаще всего базы знаний в проекте нет). `задач нет` — так и
  скажи. Строка `пропущен <файл>` — чужой или битый файл в `tasks/`: назови его.
- Всё, что видит человек, — на его языке.
