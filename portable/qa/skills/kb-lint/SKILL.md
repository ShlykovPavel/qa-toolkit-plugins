---
name: "kb-lint"
description: "Линт базы знаний проекта: найти противоречия между страницами и опровергнутые утверждения,   страницы-сироты и висячие вики-ссылки, понятия без своей страницы, утверждения без `sources`,   устаревшие статусы задач и пробелы, закрываемые новым источником. Отдаёт отчёт со списком   проблем и предложениями, правки — только после согласования. Используй, когда просят   «проверь базу», «прогони линт вики», «найди битые ссылки и страницы без источников»,   «посмотри, что в базе протухло»."
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
