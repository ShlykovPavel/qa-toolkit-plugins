#!/usr/bin/env bash
# chrome-debug.sh — поднять Chrome с CDP-портом и рабочим размером окна.
#
# Это канал к авторизованным экранам и к пошаговым прогонам через drive.mjs: человек
# логинится в этом окне руками, дальше скрипты работают в его сессии.
#
# Размер окна задаётся ЗДЕСЬ, при запуске, и дальше не трогается. Переопределять вьюпорт
# на живой вкладке через CDP — плохая идея: оно меняет картинку человеку, переживает
# отключение и снимается только пересчётом от границ окна. Нужен другой размер — закрой
# окно и подними с другим, это одна команда.
#
#   chrome-debug.sh [url] [--port N] [--size ШxВ] [--profile путь]
#
#   --size 1440x900   размер окна, по умолчанию 1440x1000 (вьюпорт выйдет ~1440x900:
#                     интерфейс браузера съедает примерно 90 px высоты)
#   --size 400x900    узкое окно для проверки мобильной вёрстки
#
# Профиль по умолчанию отдельный (~/.chrome-debug-profile), а не личный: прогоны не трогают
# личные вкладки, пароли и историю человека.

set -e

PORT=9222
SIZE=1440x1000
PROFILE_DIR="${HOME}/.chrome-debug-profile"
URL=about:blank

while [ $# -gt 0 ]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --size) SIZE="$2"; shift 2 ;;
    --profile) PROFILE_DIR="$2"; shift 2 ;;
    -h|--help) sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) URL="$1"; shift ;;
  esac
done

WIDTH="${SIZE%x*}"
HEIGHT="${SIZE#*x}"

find_chrome() {
  for c in \
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    "/Applications/Chromium.app/Contents/MacOS/Chromium" \
    "$(command -v google-chrome 2>/dev/null)" \
    "$(command -v google-chrome-stable 2>/dev/null)" \
    "$(command -v chromium 2>/dev/null)" \
    "$(command -v chromium-browser 2>/dev/null)"; do
    [ -n "$c" ] && [ -x "$c" ] && echo "$c" && return
  done
}

CHROME="$(find_chrome)"
[ -z "$CHROME" ] && { echo "❌ Chrome не найден. Поставь Google Chrome или Chromium."; exit 1; }

# Порт занят — показываем ЧЕМ, а не просто «уже запущен»: анонимный headless и залогиненное
# окно человека внешне неразличимы, и молчание об этом стоит потом ложных выводов.
if curl -s --max-time 2 "http://127.0.0.1:${PORT}/json/version" >/dev/null 2>&1; then
  echo "⚠️  На порту ${PORT} уже кто-то есть. Профиль этого Chrome:"
  ps ax -o command | grep "[r]emote-debugging-port=${PORT}" | head -1 |
    grep -o "user-data-dir=[^ ]*" | sed 's/^/    /' || echo "    определить не удалось"
  echo "    Вкладки:"
  curl -s "http://127.0.0.1:${PORT}/json/list" |
    python3 -c "import json,sys;[print('     ',t.get('url','')[:80]) for t in json.load(sys.stdin) if t.get('type')=='page']" 2>/dev/null
  echo
  echo "    Это НЕ значит, что в нём есть сессия: проверь рендером защищённой страницы."
  echo "    Нужен чистый — возьми свободный порт: --port 9333"
  exit 0
fi

mkdir -p "${PROFILE_DIR}"

"${CHROME}" \
  --remote-debugging-port="${PORT}" \
  --user-data-dir="${PROFILE_DIR}" \
  --window-size="${WIDTH},${HEIGHT}" \
  --window-position=0,0 \
  --no-first-run \
  --no-default-browser-check \
  --disable-background-networking \
  --disable-sync \
  --disable-default-apps \
  "${URL}" >/dev/null 2>&1 &

for _ in $(seq 1 20); do
  if curl -s --max-time 1 "http://127.0.0.1:${PORT}/json/version" >/dev/null 2>&1; then
    echo "✅ Chrome на http://127.0.0.1:${PORT}, окно ${WIDTH}x${HEIGHT}, профиль ${PROFILE_DIR}"
    echo
    echo "   Залогинься в окне руками, если нужны закрытые экраны, потом:"
    echo "     drive.mjs open <url>           # пошагово, состояние живёт между вызовами"
    echo "     probe.mjs <url> --port ${PORT}   # проверки одной страницы"
    echo
    echo "   Проверить, что сессия жива: открой защищённую страницу и посмотри h1."
    exit 0
  fi
  sleep 0.4
done

echo "❌ CDP на порту ${PORT} не поднялся за 8 с."
exit 1
