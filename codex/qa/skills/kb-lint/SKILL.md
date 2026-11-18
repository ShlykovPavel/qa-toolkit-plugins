---
name: "kb-lint"
description: "Линт базы знаний проекта: найти противоречия между страницами и опровергнутые утверждения,   страницы-сироты и висячие вики-ссылки, понятия без своей страницы, утверждения без `sources`,   устаревшие статусы задач и пробелы, закрываемые новым источником. Отдаёт отчёт со списком   проблем и предложениями, правки — только после согласования. Используй, когда просят   «проверь базу», «прогони линт вики», «найди битые ссылки и страницы без источников»,   «посмотри, что в базе протухло»."
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



# Линт базы знаний

## Что ищем

По запросу («проверь базу»):

- противоречия между страницами и утверждения, которые новые источники опровергли;
- страницы-сироты и висячие ссылки;
- понятия без своей страницы;
- утверждения без `sources` (находка стенда — не пробел: её источник записан в ней самой —
  стенд, дата, тест или путь к репорту; реестр багов с `sources: []` тоже);
- **устаревшие статусы**: задачи в промежуточных статусах, у которых с даты источника
  прошло много времени — кандидаты на перепроверку;
- пробелы, закрываемые новым источником или вопросом к команде.

Отчёт со списком проблем и предложениями. Правки — после согласования.

## Противоречия — по телам связанных страниц

Шапок, `index.md` и грепа по датам для противоречий мало: они сидят в теле страницы, а
опровержение — в теле соседней. Для каждой страницы с правилами (разделы `domain/`, `flows/`,
`status/` и им подобные в карте базы):

1. Прочитать её тело и выписать проверяемые факты — сроки и частоты, лимиты, статусы, коды,
   даты решений.
2. Открыть страницы, на которые она ссылается (`[[…]]` в тексте, `## Связанное`, `sources`),
   прочитать их тела и сверить те же факты.
3. Разные значения без `## Расхождения` на странице — находка: обе цитаты с путями и датами.
   Расхождение, уже описанное в `## Расхождения`, — не находка.

База большая — раздай разделы помощникам на чтение (каждый возвращает пары цитат с путями),
а каждую пару перед отчётом перечитай сам.

---

## Как читать находки

Жанры страниц и обязательный frontmatter, по которому проверяются `sources`, `updated` и тип, —
`../kb-ingest/references/page-conventions.md`. Правку каждой находки предлагай рядом с ней:
что именно дописать, объединить, завести или перепроверить.
