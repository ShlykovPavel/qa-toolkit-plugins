---
name: "sync"
description: "Довести файлы, скопированные в QA-проект из шаблона плагина (`CLAUDE.md`, `.claude/rules/`, ядро `src/`,   гейты CI, `.claude/settings.json`, а в корне — карту `CLAUDE.md`, `.gitignore` и разрешения), до новой   версии плагина командой `/qa:sync`: нетронутое — молча,   правленое — добавкой шаблона в файл человека, с вопросом, новое и убранное — по ответу, паспорт и тексты скилла — только сказать,   что поменялось. Используй, когда просят обновить проект до новой версии плагина или шаблона, «подтянуть   шаблон», когда `/qa:init` или отчёт говорит «шаблон старше плагина». Не для обновления самих плагинов   (это `claude plugin update`) и не для смены схемы данных (`/qa:migrate`)."
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



# `/qa:sync` — шаблон новой версии в проект

Механику делает скрипт `${PLUGIN_ROOT}/bin/qa-sync.py` (зови по имени, он в PATH): опись, diff, запись, манифест. Ты —
показываешь, спрашиваешь формами, собираешь решения, коммитишь. Числа, группы и строки отчёта не считаешь и
не пересказываешь своими словами — берёшь готовыми из вывода скрипта.

**Правила на весь заход:**
- До «да» на план (форма 9) — ни одной записи: только `plan`, `diff` и вопросы.
- Файлы проекта сам не правишь: всё пишет `${PLUGIN_ROOT}/bin/qa-sync.py apply`. Не пушишь.
- Каждое «да» — прямой ответ человека в этом заходе. Файл без ответа — не вписываешь в решения: он
  остаётся как есть, и следующий sync спросит снова. «Оставить» — это ответ (`keep`, у разрешения — `keep_allow`), «Не добавлять» — тоже (`no_offer`), не пропуск: разрешение, плагин или поле без ответа sync тоже спросит снова.
- **Основа — всегда файл человека.** Sync добавляет в него то, что добавил шаблон; заменить файл шаблоном —
  последний вариант формы, с числом строк, которые пропадут. Добавку шаблона заменой не называй и заменить
  шаблоном первым не предлагай: проект человека — не заготовка под шаблон.
- Всё, что видит человек, — на его языке; пока он не написал ни слова текстом — по-русски.
- Формы — `${PLUGIN_ROOT}/skills/sync/references/forms.md`, открывай по этому пути, как написан.

## Шаг 1 — какие репо

- В текущей папке есть `.qa/project.yaml` — это репо, sync только для него (корень — `/qa:sync` из корня,
  скажи это в отчёте).
- Нет — это корень: репо — подпапки с `.qa/project.yaml`, и **сам корень** — его карта `CLAUDE.md`,
  `.gitignore`, разрешения и учёт `.qa/root.json` (ниже — «корень»). Нет таких подпапок — это не QA-проект:
  скажи и предложи `/qa:init`, заход кончается.

## Шаг 2 — опись

Для каждого репо `${PLUGIN_ROOT}/bin/qa-sync.py plan <репо>`. Код 2 — стоп по этому репо: покажи человеку текст ошибки как
есть (другая схема — нужен `/qa:migrate`; незакоммиченные правки, чужое в индексе или правленый settings.json корня — закоммитить или отложить; не в git проекта — сказать человеку, `git init` сам не делай; проект на шаблоне
новее плагина — сначала обновить плагин; маркер, манифест или settings.json — симлинк) и переходи к
следующему. Из корня — ещё `${PLUGIN_ROOT}/bin/qa-sync.py plan-root <корень>` (код 2 — так же: покажи ошибку, корень
пропусти). Покажи одним сообщением `report_lines` каждого репо, по строке, под именем репо, и корня — под
«корень». Строки «settings.json корня» у репо — про плагины и каталог корня: у двух репо могут повториться —
покажи один раз.

Во всех репо только «без изменений» и пусто в `settings.drop_allow`, `offer_allow`, `offer_plugins`,
`offer_market`, а у корня `from` = `to`, `map.group` — `same`, `edited` или `declined`, пусто в `gitignore` и
`settings` — скажи «проект уже на шаблоне <версия>», заход кончается.

## Шаг 3 — вопросы

По каждому файлу, где нужно решение, по порядку групп `merge`, `own_changed`, `new`, `new_occupied`,
`removed`, `deleted`, потом `settings.drop_allow`, `settings.offer_allow`, `settings.offer_plugins`, `settings.offer_market`
и у корня `root.settings.offer_plugins`, `root.settings.offer_market` (одно и то же у двух репо — спроси один раз):
1. `${PLUGIN_ROOT}/bin/qa-sync.py diff <репо> <файл>` — покажи вывод как есть, в блоке кода.
2. Форма из `forms.md` по группе и по `carry` в выводе `plan`: файла в `carry` нет или его `left` — 0 — правка
   шаблона встаёт в файл человека сама (форма 1 у `merge`, 3 у `own_changed`); `left` больше 0 — форма 2.
   Числа `<N>`, `<M>` вопроса — из `loss` плана. До 4 файлов в одной форме — тогда сначала все их diff, потом
   форма.
3. «Собрать вместе» (форма 2) — ставишь на место то, что не встало само; текст не сочиняешь:
   - `${PLUGIN_ROOT}/bin/qa-sync.py draft <репо> <файл> <временный файл>` (scratchpad или временная папка, не проект): в файле —
     файл человека, куда уже перенесено всё, что встало; `left` — куски правки шаблона: `old` — как это место
     было в шаблоне, `new` — как стало;
   - по каждому куску найди в файле человека место, которому отвечает `old`, и поставь рядом то, что шаблон
     добавил (есть в `new`, нет в `old`), — правкой временного файла. Строки человека не переписываешь и не
     удаляешь, своего текста не дописываешь; шаблон только переформулировал то, что у человека сказано
     по-своему, — оставь как у человека и скажи это одной строкой;
   - покажи `${PLUGIN_ROOT}/bin/qa-sync.py diff <репо> <файл> --text <временный файл>` как есть; спроси текстом: «так? что
     поправить?»; правки — в файл и снова `diff --text`, пока не скажет «да». Его «да» — решение `text`;
     передумал — задай форму ещё раз.

Группы `update`, `skill_text`, `binary`, `removed_edited`, `unknown`, `unsafe` не спрашиваешь: они уже в `report_lines`.
Попросит человек показать файл из них — `${PLUGIN_ROOT}/bin/qa-sync.py diff` (кроме `unsafe`: путь за пределы репо или через
симлинк, sync его не читает и не пишет).

**Корень** — после репо, по выводу `plan-root`:
1. `settings.drop_allow` — форма 8, `settings.offer_allow` — форма 8б (в них — «`.claude/settings.json`
   корня»). `add_allow` и `gitignore` не спрашиваешь — они молча, уже в `report_lines`.
2. Карта — по `map.group`, перед вопросом `${PLUGIN_ROOT}/bin/qa-sync.py diff-root <корень>` как есть, в блоке кода: `merge`,
   правка шаблона встаёт сама (`map_carry` — null или его `left` — 0) — форма 1; `left` больше 0 — форма 11;
   `unknown` — форма 10, `deleted` — форма 7. Остальные группы не спрашиваешь. `<N>`, `<M>` — из `map_loss`.
3. «Собрать вместе» (формы 10, 11) — собираешь карту с человеком, текст не сочиняешь:
   - `${PLUGIN_ROOT}/bin/qa-sync.py draft-root <корень> <файл>` — файл во временной папке (scratchpad или временная, не в
     проекте): основа уже в нём. Форма 11 (`basis`: `own`) — карта человека, куда уже перенесено всё, что
     встало само; `left` — куски правки шаблона (`old` — как было в шаблоне, `new` — как стало): ставишь
     добавленное шаблоном рядом с местом человека, как у файлов репо выше. Форма 10 (`basis`: `template`) —
     карта шаблона целиком; `own_lines` — строки человека, которых в шаблоне нет: каждая возвращается в основу
     на своё место. Где шаблон и человек говорят одно и то же разными словами — остаётся строка человека,
     **без вопроса**; сколько таких — одной строкой. Спрашиваешь только там, где они говорят разное. Основа
     пришла с маркерами `<<<<<<< сейчас` / `>>>>>>> шаблон` (`basis`: `merge`) — покажи обе стороны куска и
     спроси, что оставить; маркеров в файле не оставляй;
   - своего текста не дописываешь — только строки основы и человека;
   - покажи `${PLUGIN_ROOT}/bin/qa-sync.py diff-root <корень> --text <файл>` как есть; спроси текстом: «так? что поправить?»;
     правки — в файл и снова `diff-root --text`, пока не скажет «да». Его «да» — решение `map_text`;
     передумал — задай форму ещё раз.

## Шаг 4 — «да» и запись

1. Форма 9. «Ничего не делать» — заход кончается, ничего не записано.
2. «Применить» — репо **по очереди: `apply`, сразу его коммит (п. 3), потом следующий репо** (git один в
   корне — следующий `apply` остановится на незакоммиченном после предыдущего), **корень — последним**
   (п. 4). Для репо — решения в JSON по
   таблице «Ответы → решения» `forms.md` (в scratchpad или во временную папку, не в репо) и
   `${PLUGIN_ROOT}/bin/qa-sync.py apply <репо> <решения.json>`. Код 2 — покажи ошибку как есть: скорее всего проект поменялся
   после описи — повтори с шага 2 для этого репо. Ответы про корень (`root`) клади в решения каждого репо, где
   корень их предлагал: уже добавленное с первым репо второй `apply` пропустит.
3. Коммит репо, где `apply` прошёл и `git_add` не null (null — sync ничего не записал, коммита нет): `git add` — в папке репо (`cd <абсолютный путь репо>`, не относительный:
   папка сессии после него сменится) командой из `git_add` вывода `apply` как есть (выжимки
   сессий в коммит sync не идут), сообщение
   `qa:sync <from> → <to>` (из вывода `apply`), в теле — списки `updated`, `written`, `deleted`, `declined`
   и разрешения из `settings`; `waiting` — «без ответа, sync спросит снова». Проверь `git config user.name` и `user.email` до коммита; не заданы —
   скажи человеку, коммит не делай.
4. Корень: решения — в JSON по таблице «Ответы → решения по корню» `forms.md` и
   `${PLUGIN_ROOT}/bin/qa-sync.py apply-root <корень> <решения.json>` (решений нет — без файла). Код 2 — как у репо. `git_add`
   в выводе не пуст — коммит в корне этой командой как есть, сообщение `qa:sync корень <from> → <to>` (`from`
   пуст — «учёта не было»), в теле — `settings`, что с картой (`map`), строки `gitignore`, `waiting`. `git_add`
   null — коммита нет: при `git` false корень не в git — скажи в отчёте, что откат — руками; при `git` true
   записывать было нечего.

## Шаг 5 — отчёт

По корню: версия `from → to`, разрешения, что с картой и `.gitignore`, `waiting` (без ответа — sync спросит
снова), хэш коммита. Карта осталась с правками человека (добавлено в его карту, собрана вместе или «оставить
своё») — скажи: sync это помнит, следующую правку шаблона добавит в его карту.

По каждому репо: версия `from → to`, что обновлено молча, что по ответам, что осталось на человеке — строки
`report_lines` про «правьте сами» и «не узнать», `waiting` из вывода `apply` (без ответа — sync спросит снова) —
и хэш коммита. Поменял `apply` settings корня (`root` в выводе): git один в корне — он уже в `git_add` и в коммите sync;
у корня нет git — скажи, что это вне git: в коммит не попало, откат — руками. Плагины sync не обновляет:
если человек об этом спрашивает — `claude plugin update <плагин>@qa-toolkit --scope project` в корне (git один
в корне — только там; иначе в корне и в каждой папке репо).
