#!/usr/bin/env node
/**
 * drive.mjs — пошаговое управление УЖЕ ОТКРЫТОЙ вкладкой Chrome через CDP.
 *
 * Зачем отдельно от probe.mjs: тот на каждый запуск открывает новую вкладку и закрывает её
 * в конце, поэтому состояние между вызовами не живёт — заполнить форму одним вызовом и
 * нажать кнопку другим невозможно. Здесь наоборот: скрипт подключается к существующей
 * вкладке, делает один шаг и уходит, ничего не закрывая. Состояние страницы (маршрут SPA,
 * скролл, введённые значения, открытые модалки) сохраняется между вызовами — проверено.
 *
 * Это канал для CLI, где встроенного браузера нет: один вызов = один шаг сценария.
 *
 *   node drive.mjs <команда> [аргументы] [--port 9222]
 *
 *   open <url> [--width N]  перейти по адресу в текущей вкладке (и поставить сборщик ошибок)
 *   state                   где я: url, title, h1, скролл, вьюпорт, собранные ошибки
 *   resize <Ш> [В]          сменить размер окна, не уже 500 px (рабочий размер задай при запуске)
 *
 * Мобильной ширины здесь нет намеренно: эмуляция вьюпорта на чужой вкладке необратима.
 * Мобильный экран — probe.mjs/shot.mjs с --viewport mobile (своя вкладка, те же куки) или
 * встроенный браузер агента, если нужен пошаговый мобильный сценарий.
 *   read [--limit N]        что на странице: заголовки и интерактивные элементы с текстом
 *   text [--chars N]        видимый текст страницы (по умолчанию 1500 символов)
 *   dump <файл>             весь текст страницы в файл, в вывод — путь и длина
 *   click --text <строка>   клик по элементу, чей текст содержит строку
 *   click --sel <css>       клик по селектору
 *   type --sel <css> <текст>  ввести текст в поле
 *   key <имя>               нажать клавишу: Enter, Escape, Tab, ArrowDown
 *   scroll <px|top|bottom>  прокрутить
 *   shot <файл.png>         снимок текущего состояния страницы целиком
 *   eval <js>               выполнить выражение и вернуть значение
 *
 * Клики и ввод идут через `Input.*`, то есть тем же путём, что настоящие мышь и клавиатура:
 * страница не отличает их от действий человека. `el.click()` и синтетические `Event` этого
 * не дают — часть обработчиков их игнорирует, и «кнопка не работает» оказывается артефактом
 * автоматизации, а не дефектом.
 *
 * Примеры:
 *   node drive.mjs open https://example.com/catalog
 *   node drive.mjs read
 *   node drive.mjs click --text "Фильтры"
 *   node drive.mjs type --sel 'input[type=search]' 'стойка'
 *   node drive.mjs key Enter
 *   node drive.mjs state
 *
 * Вкладку и браузер скрипт не закрывает никогда: она чужая. Сессия в ней — та, в которой
 * залогинился человек, поэтому это же и канал к авторизованным экранам.
 */

import { spawnSync } from 'node:child_process';
import { writeFileSync, appendFileSync, mkdirSync, readdirSync, existsSync } from 'node:fs';

// Глобальный WebSocket в Node 20 живёт за флагом — перезапускаем себя с ним.
if (typeof WebSocket === 'undefined') {
  const r = spawnSync(
    process.execPath,
    ['--experimental-websocket', new URL(import.meta.url).pathname, ...process.argv.slice(2)],
    { stdio: 'inherit' },
  );
  process.exit(r.status ?? 1);
}

const argv = process.argv.slice(2);
const HELP = `usage: node drive.mjs <команда> [аргументы] [--port 9222]

  open <url>                перейти по адресу в текущей вкладке
  state                     url, title, h1, скролл, вьюпорт, собранные ошибки
  resize <Ш> [В]            сменить размер окна (не уже 500 px — ограничение Chrome)
  read [--limit N]          заголовки и интерактивные элементы
  text [--chars N]          видимый текст страницы
  dump <файл>               весь текст страницы в файл
  click --text <строка>     клик по элементу с таким текстом
  click --sel <css>         клик по селектору
  type --sel <css> <текст>  ввести текст в поле
  key <имя>                 Enter | Escape | Tab | ArrowDown | ArrowUp
  scroll <px|top|bottom>    прокрутить
  shot <файл.png>           снимок текущего состояния целиком
  eval <js>                 выполнить выражение

  --save <каталог>          сохранять сырой вывод КАЖДОЙ команды файлом в этот каталог
                            (то же самое делает переменная окружения DRIVE_EVIDENCE_DIR)`;

if (!argv.length || argv.includes('--help') || argv.includes('-h')) {
  console.error(HELP);
  process.exit(1);
}

const opt = (name, def) => {
  const i = argv.indexOf(name);
  return i === -1 ? def : argv[i + 1];
};
const port = Number(opt('--port', 9222));
const cmd = argv[0];
// Позиционные аргументы — всё, что не команда, не флаг и не значение флага.
const positional = [];
for (let i = 1; i < argv.length; i++) {
  if (argv[i].startsWith('--')) {
    i++; // значение флага
    continue;
  }
  positional.push(argv[i]);
}

const fail = (msg) => {
  console.error(msg);
  process.exit(1);
};

// Команду проверяем до подключения: иначе опечатка в ней выглядит как «нет Chrome на порту»,
// и человек лезет поднимать браузер вместо того, чтобы поправить букву.
const COMMANDS = ['open', 'state', 'read', 'text', 'dump', 'click', 'type', 'key', 'scroll', 'shot', 'eval', 'resize'];
if (!COMMANDS.includes(cmd)) fail(`неизвестная команда: ${cmd}\n\n${HELP}`);

/**
 * Сохранение наблюдения — механикой, а не дисциплиной.
 *
 * Замерено на четырёх заходах подряд: правило «сырой
 * вывод инструмента уходит в файл первым действием» написано трижды и не удержалось ни разу.
 * Проигрывает оно всегда одинаково — наблюдение выглядит очевидным, «я это только что видел»
 * стопроцентно верно, следующим действием уходит другой вызов, а через полчаса скептик просит
 * артефакт, и то же самое приходится переснимать заново (в заходе 37 — половина рабочего окна).
 *
 * Поэтому файл пишет скрипт, а не агент. Объявлен каталог сырья захода — сохраняется вывод
 * КАЖДОЙ команды, включая провалившиеся: неудачное наблюдение — тоже данные. Не объявлен —
 * скрипт ведёт себя ровно как раньше.
 */
const evidenceDir = opt('--save', process.env.DRIVE_EVIDENCE_DIR ?? null);
let evidenceFile = null;

// Молча не сохранять — худший исход из возможных: заход уверен, что сырьё пишется, а его нет.
if (argv.includes('--save') && !evidenceDir) fail('нужен каталог: drive.mjs <команда> --save <каталог>');

if (evidenceDir) {
  try {
    if (!existsSync(evidenceDir)) mkdirSync(evidenceDir, { recursive: true });
    const seq = readdirSync(evidenceDir).filter((f) => /^\d{3}-/.test(f)).length + 1;
    const stamp = new Date().toISOString();
    evidenceFile = `${evidenceDir}/${String(seq).padStart(3, '0')}-${cmd}.txt`;
    // Шапка происхождения: без неё дамп через день не отличить от дампа соседнего кейса.
    writeFileSync(
      evidenceFile,
      `# drive.mjs ${stamp}\n# команда: node drive.mjs ${argv.join(' ')}\n# порт: ${port}\n---\n`,
    );
    console.error(`сырьё: ${evidenceFile}`);
  } catch (e) {
    // Сорванное сохранение не должно ронять сам шаг — но и молчать о нём нельзя.
    console.error(`ВНИМАНИЕ: сырьё не сохраняется (${e.message}) — дампы придётся снимать руками`);
    evidenceFile = null;
  }
}

// Пишем ровно то, что ушло в stdout/stderr, а не пересказ: перепечатка руками и есть та
// ошибка, от которой этот механизм защищает.
const record = (text) => {
  if (!evidenceFile) return;
  try {
    appendFileSync(evidenceFile, `${text}\n`);
  } catch {
    /* сохранение сорвалось по ходу — шаг важнее файла, о срыве уже сказано выше */
  }
};

const realLog = console.log.bind(console);
const realErr = console.error.bind(console);
console.log = (...args) => {
  const line = args.map((a) => (typeof a === 'string' ? a : String(a))).join(' ');
  record(line);
  realLog(...args);
};
console.error = (...args) => {
  const line = args.map((a) => (typeof a === 'string' ? a : String(a))).join(' ');
  // Строку про сам файл сырья в него же не пишем — она про механизм, а не про наблюдение.
  if (!line.startsWith('сырьё: ')) record(line);
  realErr(...args);
};

// --- подключение к существующей вкладке -------------------------------------

let tabs;
try {
  tabs = await (await fetch(`http://127.0.0.1:${port}/json/list`, { signal: AbortSignal.timeout(2000) })).json();
} catch {
  fail(
    `На порту ${port} нет Chrome с открытым CDP.\n` +
      'Подними его: Chrome --remote-debugging-port=' + port + ' --user-data-dir=<отдельный профиль>',
  );
}

let page = tabs.find((t) => t.type === 'page' && !t.url.startsWith('devtools://'));
if (!page) {
  // Ни одной обычной вкладки — открываем свою, она станет рабочей для следующих шагов.
  page = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })).json();
}

const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => {
  ws.onopen = res;
  ws.onerror = () => rej(new Error(`не удалось подключиться к вкладке на порту ${port}`));
});

let seq = 0;
const pending = new Map();
ws.onmessage = (m) => {
  const msg = JSON.parse(m.data);
  if (msg.id && pending.has(msg.id)) {
    pending.get(msg.id)(msg);
    pending.delete(msg.id);
  }
};
const send = (method, params = {}) =>
  new Promise((res) => {
    const id = ++seq;
    pending.set(id, res);
    ws.send(JSON.stringify({ id, method, params }));
  });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** Выполняет выражение в странице и возвращает значение (или бросает текст исключения). */
const evaluate = async (expression) => {
  const msg = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  const ex = msg.result?.exceptionDetails;
  if (ex) throw new Error(ex.exception?.description ?? ex.text ?? 'ошибка в выражении');
  return msg.result?.result?.value;
};

/**
 * Сборщик ошибок ставится в саму страницу и живёт в ней между вызовами скрипта, пока не
 * произойдёт полная перезагрузка. Иначе консольные ошибки не увидеть вовсе: они приходят
 * событиями, а этот процесс подключён к вкладке доли секунды.
 */
const COLLECTOR = `(()=>{if(window.__driveErrs)return 'уже стоит';window.__driveErrs=[];
  const push=(s)=>{if(window.__driveErrs.length<40)window.__driveErrs.push(String(s).slice(0,200))};
  addEventListener('error',e=>push('error: '+(e.message||e.type)));
  addEventListener('unhandledrejection',e=>push('promise: '+(e.reason&&e.reason.message||e.reason)));
  const ce=console.error.bind(console);console.error=(...a)=>{push('console: '+a.join(' '));ce(...a)};
  return 'поставлен'})()`;

/** Центр элемента в координатах вьюпорта — для настоящих событий мыши. */
const CENTER_OF = (finder) => `(()=>{const el=${finder};
  if(!el) return null;
  el.scrollIntoView({block:'center',inline:'center'});
  const r=el.getBoundingClientRect();
  if(r.width===0||r.height===0) return {hidden:true,label:(el.innerText||el.value||'').trim().slice(0,60)};
  return {x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2),
    tag:el.tagName.toLowerCase(),label:(el.innerText||el.value||el.getAttribute('aria-label')||'').trim().slice(0,60)}})()`;

const BY_TEXT = (needle) => `[...document.querySelectorAll('a,button,[role=button],label,summary,input[type=submit]')]
  .find(e=>((e.innerText||e.value||e.getAttribute('aria-label')||'')).toLowerCase().includes(${JSON.stringify(
    needle.toLowerCase(),
  )}))`;
const BY_SEL = (sel) => `document.querySelector(${JSON.stringify(sel)})`;

const realClick = async (finder) => {
  const box = await evaluate(CENTER_OF(finder));
  if (!box) fail('элемент не найден на странице');
  if (box.hidden) fail(`элемент найден, но не отрисован (нулевой размер): "${box.label}"`);
  await sleep(150); // scrollIntoView со smooth-поведением
  for (const type of ['mousePressed', 'mouseReleased']) {
    await send('Input.dispatchMouseEvent', {
      type,
      x: box.x,
      y: box.y,
      button: 'left',
      clickCount: 1,
      buttons: type === 'mousePressed' ? 1 : 0,
    });
  }
  return box;
};

const pageState = async () => {
  const s = await evaluate(`JSON.stringify({url:location.href,title:document.title,
    h1:(document.querySelector('h1')||{}).innerText||null,
    scrollY:Math.round(window.scrollY),viewport:innerWidth+'x'+innerHeight,
    docHeight:document.documentElement.scrollHeight,
    errors:(window.__driveErrs||null)})`);
  const st = JSON.parse(s);
  if (st.h1) st.h1 = st.h1.trim().slice(0, 80);
  if (st.errors === null) st.errors = 'сборщик не стоит — поставится при `open`';
  else if (!st.errors.length) st.errors = 'нет';
  return st;
};

const out = (obj) => console.log(JSON.stringify(obj, null, 1));
const chrome = `порт ${port}, вкладка ${page.url.slice(0, 60)}`;

// --- команды ----------------------------------------------------------------

try {
  switch (cmd) {
    case 'open': {
      const url = positional[0] ?? fail('нужен адрес: drive.mjs open <url>');
      await send('Page.enable');
      await send('Page.navigate', { url });
      await sleep(Number(opt('--wait', 4000)));
      await evaluate(COLLECTOR);
      // Размер окна не трогаем: он задан при запуске Chrome и принадлежит человеку. Но
      // печатаем его всегда — наблюдение без объявленной ширины невоспроизводимо.
      out({ chrome, шаг: `открыт ${url}`, ...(await pageState()) });
      break;
    }

    case 'state':
      out({ chrome, ...(await pageState()) });
      break;

    /**
     * Меняет размер САМОГО ОКНА, а не эмулирует вьюпорт.
     *
     * Эмуляция через Emulation.setDeviceMetricsOverride здесь была ошибкой: она подменяет
     * картинку человеку, переживает отключение сессии и не снимается обратным вызовом —
     * только пересчётом от границ окна. Размер окна честнее: что видит человек, то видит и
     * скрипт, и следующий заход измерит настоящую ширину.
     *
     * Рабочий размер вообще правильнее задавать при запуске (`chrome-debug.sh --size`), а
     * эта команда — на случай, когда окно уже поднято, а ширину надо сменить по ходу.
     */
    case 'resize': {
      const w = Number(positional[0] ?? fail('нужна ширина: drive.mjs resize 1440 [900]'));
      const h = Number(positional[1] ?? 900);
      const win = await send('Browser.getWindowForTarget');
      const id = win.result?.windowId;
      const b = win.result?.bounds;
      if (!id) fail('окно не найдено: у headless-вкладки границ может не быть — задай размер при запуске');

      // Интерфейс браузера съедает высоту, а полоса прокрутки — ширину. Меряем разницу на
      // текущем окне и компенсируем, чтобы запрошенное совпало с вьюпортом, а не с рамкой.
      const st0 = await pageState();
      const [iw0, ih0] = st0.viewport.split('x').map(Number);
      const dW = Math.max(0, (b?.width ?? iw0) - iw0);
      const dH = Math.max(0, (b?.height ?? ih0) - ih0);

      await send('Browser.setWindowBounds', {
        windowId: id,
        bounds: { windowState: 'normal', width: w + dW, height: h + dH },
      });
      await sleep(500);
      const st = await pageState();
      const [iw] = st.viewport.split('x').map(Number);
      out({
        chrome,
        окно: `${w + dW}x${h + dH}`,
        ...st,
        ...(Math.abs(iw - w) > 4
          ? { WARNING: `запрошена ширина ${w}, вьюпорт ${st.viewport} — выводам по вёрстке не верить` }
          : {}),
      });
      break;
    }

    /*
     * Команды эмуляции вьюпорта здесь СОЗНАТЕЛЬНО НЕТ.
     *
     * Emulation.setDeviceMetricsOverride на чужой вкладке необратим. Проверено на живом
     * Chrome: из нового подключения переопределение не снимают ни clearDeviceMetricsOverride,
     * ни setDeviceMetricsOverride(0,0), ни то же самое плюс навигация. Пересчёт от границ окна
     * возвращает правильную ширину лишь до первого перехода, после которого 390 px возвращается.
     * Единственный способ получить чистый вьюпорт — НОВАЯ вкладка.
     *
     * Поэтому мобильная ширина берётся так:
     *   - разово, в том числе под сессией человека:
     *       probe.mjs <url> --viewport mobile --port 9222
     *       shot.mjs  <url> кадр.png --viewport mobile --port 9222
     *     оба работают в своей одноразовой вкладке того же Chrome (значит те же куки и тот же
     *     вход) и закрывают её за собой — окно человека не затрагивается;
     *   - пошаговым сценарием: во встроенном браузере агента, он умеет 390 px и держит состояние.
     *
     * Окно шире 500 px меняется честно и обратимо — командой resize выше.
     */

    case 'read': {
      const limit = Number(opt('--limit', 40));
      const data = await evaluate(`(()=>{const vis=e=>{const r=e.getBoundingClientRect();
        return r.width>0&&r.height>0&&getComputedStyle(e).visibility!=='hidden'};
        const lbl=e=>((e.innerText||e.value||e.getAttribute('aria-label')||e.placeholder||'').trim().replace(/\\s+/g,' ')).slice(0,50);
        const items=[];
        for(const e of document.querySelectorAll('a[href],button,[role=button],input,select,textarea')){
          if(!vis(e))continue;
          const t=e.tagName.toLowerCase();
          const kind=t==='a'?'ссылка':t==='button'||e.getAttribute('role')==='button'?'кнопка':'поле';
          const extra=t==='a'?' → '+e.getAttribute('href'):t==='input'&&e.type?' ['+e.type+']':'';
          items.push(kind+' "'+lbl(e)+'"'+extra);
        }
        const heads=[...document.querySelectorAll('h1,h2,h3')].filter(vis).map(h=>h.tagName.toLowerCase()+': '+h.innerText.trim().replace(/\\s+/g,' ').slice(0,60));
        return JSON.stringify({heads:heads.slice(0,15),items:[...new Set(items)],total:items.length})})()`);
      const d = JSON.parse(data);
      out({
        chrome,
        заголовки: d.heads,
        элементов: d.total,
        элементы: d.items.slice(0, limit),
        ...(d.items.length > limit ? { обрезано: `показано ${limit} из ${d.items.length} уникальных` } : {}),
      });
      break;
    }

    case 'text': {
      const chars = Number(opt('--chars', 1500));
      const t = await evaluate('document.body.innerText');
      console.log(`(всего ${t.length} символов, показано ${Math.min(chars, t.length)})\n---\n${t.slice(0, chars)}`);
      break;
    }

    case 'dump': {
      const file = positional[0] ?? fail('нужен путь: drive.mjs dump <файл>');
      const t = await evaluate('document.body.innerText');
      writeFileSync(file, t);
      out({ chrome, файл: file, символов: t.length });
      break;
    }

    case 'click': {
      const byText = opt('--text', null);
      const bySel = opt('--sel', null);
      if (!byText && !bySel) fail('нужен --text <строка> или --sel <css>');
      const before = await pageState();
      const box = await realClick(byText ? BY_TEXT(byText) : BY_SEL(bySel));
      await sleep(Number(opt('--wait', 1200)));
      const after = await pageState();
      out({
        chrome,
        клик: `${box.tag} "${box.label}" в (${box.x},${box.y})`,
        изменилось:
          before.url !== after.url
            ? `url: ${before.url} → ${after.url}`
            : before.title !== after.title
              ? `title: ${before.title} → ${after.title}`
              : before.docHeight !== after.docHeight
                ? `высота страницы: ${before.docHeight} → ${after.docHeight}`
                : 'ни url, ни title, ни высота — возможно, изменение внутри блока',
        ...after,
      });
      break;
    }

    case 'type': {
      const sel = opt('--sel', null) ?? fail('нужен --sel <css>');
      const value = positional[0] ?? fail('нужен текст: drive.mjs type --sel <css> <текст>');
      const box = await realClick(BY_SEL(sel)); // фокус настоящим кликом
      await send('Input.insertText', { text: value });
      await sleep(400);
      const got = await evaluate(`(${BY_SEL(sel)}||{}).value ?? null`);
      out({ chrome, поле: `${box.tag} "${box.label}"`, введено: value, вЗначении: got });
      break;
    }

    case 'key': {
      const name = positional[0] ?? fail('нужно имя клавиши');
      const KEYS = {
        Enter: { key: 'Enter', code: 'Enter', keyCode: 13, text: '\r' },
        Escape: { key: 'Escape', code: 'Escape', keyCode: 27 },
        Tab: { key: 'Tab', code: 'Tab', keyCode: 9 },
        ArrowDown: { key: 'ArrowDown', code: 'ArrowDown', keyCode: 40 },
        ArrowUp: { key: 'ArrowUp', code: 'ArrowUp', keyCode: 38 },
      };
      const k = KEYS[name] ?? fail(`неизвестная клавиша: ${name}. Есть: ${Object.keys(KEYS).join(', ')}`);
      await send('Input.dispatchKeyEvent', { type: 'keyDown', ...k });
      await send('Input.dispatchKeyEvent', { type: 'keyUp', ...k });
      await sleep(Number(opt('--wait', 1200)));
      out({ chrome, нажато: name, ...(await pageState()) });
      break;
    }

    case 'scroll': {
      const to = positional[0] ?? 'bottom';
      const expr =
        to === 'top'
          ? 'window.scrollTo(0,0)'
          : to === 'bottom'
            ? 'window.scrollTo(0,document.documentElement.scrollHeight)'
            : `window.scrollBy(0,${Number(to) || 600})`;
      await evaluate(expr);
      await sleep(500);
      out({ chrome, прокрутка: to, ...(await pageState()) });
      break;
    }

    case 'shot': {
      const file = positional[0] ?? fail('нужен путь: drive.mjs shot <файл.png>');
      // Метрики вкладки не переопределяем: вкладка чужая, менять её размер нельзя.
      const msg = await send('Page.captureScreenshot', {
        format: 'png',
        captureBeyondViewport: !argv.includes('--viewport-only'),
        fromSurface: true,
      });
      const data = msg.result?.data;
      if (!data) fail('снимок не получился — вкладка могла быть свёрнута');
      const buf = Buffer.from(data, 'base64');
      writeFileSync(file, buf);
      const st = await pageState();
      out({ chrome, файл: file, байт: buf.length, вьюпорт: st.viewport, высота: st.docHeight });
      break;
    }

    case 'eval': {
      const expr = positional[0] ?? fail('нужно выражение');
      out({ chrome, значение: await evaluate(expr) });
      break;
    }

    default:
      console.error(`неизвестная команда: ${cmd}\n\n${HELP}`);
      ws.close();
      process.exit(1);
  }
} catch (e) {
  console.error(`шаг не выполнен: ${e.message}`);
  ws.close();
  process.exit(1);
}

// Вкладку и браузер не закрываем — они чужие, и следующий вызов продолжит с этого места.
ws.close();
process.exit(0);
