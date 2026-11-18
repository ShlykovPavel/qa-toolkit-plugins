---
name: "hello"
description: "Проверка, что плагин qa подключён и видит свои скрипты. Вызывается только явно как /qa:hello."
disable-model-invocation: true
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



# hello

Выполни команду `${PLUGIN_ROOT}/bin/qa-hello` и перепиши её вывод без изменений. Если команда не найдена,
так и скажи: значит, плагин загружен без своей папки `bin/`.
