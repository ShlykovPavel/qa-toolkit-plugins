---
name: "kb-ingest"
description: "Ингест источника в базу знаний проекта: прочитать документ или выгрузку из `raw/`, принести   человеку тезисы с датой и статусом AS-IS/TO-BE, дождаться реакции и разложить по страницам   вики — конспект источника, затронутые сущности и флоу, глоссарий, индекс, лог, коммит   `ingest:`. Используй, когда просят заингестить, разобрать или «разложить по базе» новый   документ, спеку, снапшот сваггера, выгрузку из BookStack/Confluence/Notion, ТЗ или его новую   редакцию; когда в `raw/` лёг новый файл; когда обновился снапшот и нужна дельта. Сюда же —   «добавь это в вики», «занеси документ в базу знаний» и находки стенда: автотест, разбор   прогона или ручная проверка нашли правило продукта, расхождение с вики, баг или вопрос   продукту — «занеси находки в вики», «закрой контур»."
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



# Ингест источника в базу знаний

Человек курирует источники и принимает решения, страницы пишешь ты. Режим по умолчанию —
**supervised**: по одному источнику, с обсуждением, не пачками.

Пути в этом скилле — от корня вики. Корень вики и коллекцию проекта печатает `${PLUGIN_ROOT}/bin/qa-paths`
(`wiki`, `collection`): папки могут называться не по шаблону.

## Порядок

1. Открыть `${PLUGIN_ROOT}/skills/rules/references/wiki-and-collection.md`, раздел
   «Ингест»: чекпойнт и крупные источники. Прочитать источник из `raw/`. Найти его дату и статус
   (`AS-IS`/`TO-BE`) — без них не разрешить конфликт с уже накопленным.
2. **Обсудить с человеком** ключевые тезисы: что нового, что противоречит имеющемуся.
   Дождаться реакции — что усилить, что проигнорировать.
3. Написать `wiki/sources/s-<slug>.md`.
4. Обновить затронутые страницы — сущности, флоу, `glossary.md`, при необходимости
   `synthesis.md` и `status/*` (обычно 5–15 страниц); завести страницы новым сущностям.
5. Обновить `index.md`, дописать запись в `log.md`. Во вступлении `CLAUDE.md` вики ещё заглушка
   шаблона («пока пустая») — заменить её 2–3 предложениями о продукте: что это, для кого, какие роли.
6. Отчитаться: созданные и изменённые файлы, что поменялось по смыслу, какие противоречия
   всплыли.
7. Закоммитить: `ingest: <название источника>`.

Источник ничего не добавляет — сказать и не плодить страницу.

## `raw/` неизменяем

Источники в `raw/` только читаем: не правим и не удаляем. Исключение — если проект так решил
и записал в `CLAUDE.md` базы: машинные снапшоты API-спеки и **отслеживаемые** выгрузки внешней
вики (документ, который часто правят). Новая версия заменяет прежний файл под тем же именем тем
же коммитом, что и её ингест: в базе ровно одна версия — неактуальная рядом с актуальной даёт
ложные выводы, а копии раздувают `raw/`; прежняя остаётся в истории git. Что поменялось —
«История снапшотов» (для выгрузки — «История выгрузок») на странице источника. Прочие
источники: новая версия — новым файлом.

`wiki/` целиком твоя; `CLAUDE.md` базы, `index.md`, `log.md` — схема, каталог, хронология.

## Как писать страницы

Имена, frontmatter, тело страницы и шаблоны жанров — `references/page-conventions.md`.
Открой перед первой страницей захода.

## Находка стенда — не документ

В вики просят занести то, что увидели на стенде, — автотест, разбор прогона или ручная
проверка нашли правило продукта, расхождение с вики, баг или вопрос продукту. Источника в
`raw/` у такой находки нет, конспект не пишется. Порядок свой — `references/stand-finding.md`:
куда ложится каждый вид находки, что на странице не трогать, как заводится реестр багов.
Главное то же, что у ингеста: список человеку, дождаться «да», потом страницы, лог и коммит
`note:`. Раскладку уже показал приведший сюда скилл и получил «да» (пометка «раскладка
показана, „да“ получено») — второй раз не показывай, сразу пиши.

## Поменялся контракт — поправь коллекцию

Ингест поменял путь эндпоинта, поле, enum, код ошибки или порядок шагов флоу — найти
затронутые запросы в коллекции (`${PLUGIN_ROOT}/bin/qa-paths collection`) и поправить в той же сессии отдельным
коммитом: «вики говорит одно, коллекция шлёт другое» даёт ложные баги. Тест-кейсы живут в
`wiki/tests/test-*.md`, запросы к ним — в коллекции.

## Git

Одна осмысленная операция — один коммит: `ingest: …`, `note: …`, `lint: …`, `meta: …`.
