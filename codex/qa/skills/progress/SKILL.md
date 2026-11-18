---
name: "progress"
description: "Обзор задач командой `/qa:progress`: что идёт, что ждёт человека, что ждёт других (разработчика, стенд),   что закрыто за неделю — по карточкам задач в базе знаний. Используй, когда человек спрашивает «что у нас   открыто?», «что по задачам?», «что висит?», «что от меня нужно?», «что закрыли за неделю?», и по команде   `/qa:progress`. Только показывает: ничего не запускает и не меняет. Продолжить работу — `qa:next`,   взять задачу — `qa:task`."
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
