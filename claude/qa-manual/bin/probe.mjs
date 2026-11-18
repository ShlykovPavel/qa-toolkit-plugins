#!/usr/bin/env node
/**
 * probe.mjs — детерминированные проверки страницы через Chrome DevTools Protocol.
 *
 * Смысл: не тащить DOM в контекст модели, а посчитать выводы в браузере и напечатать
 * короткий JSON. Полный accessibility-снапшот страницы стоит тысячи токенов на шаг,
 * отчёт этого скрипта — десятки строк. Модель читает выводы, а не разметку.
 *
 *   node probe.mjs <url> [опции]
 *
 *   --crawl <N>        обойти до N внутренних ссылок с этой страницы (0 = только она)
 *   --viewport <имя>   mobile (390x844) | tablet (820x1180) | desktop (1440x900)
 *   --width/--height   свой размер вместо пресета
 *   --wait <мс>        пауза после навигации, по умолчанию 4000
 *   --js '<код>'       выполнить перед проверками (закрыть баннер, открыть меню)
 *   --repeat <N>       прогнать каждую страницу N раз и показать стабильность находок
 *   --inventory        выгрузить список ссылок и кнопок (для сравнения ролей)
 *   --full             не сворачивать длинные списки до трёх примеров
 *   --dump <каталог>   сложить текст и HTML каждой страницы файлами, в отчёт — пути и длины
 *   --port <порт>      CDP-порт, по умолчанию 9222
 *   --keep             не гасить Chrome после прогона (быстрее для серии)
 *
 * Примеры:
 *   node probe.mjs https://example.com
 *   node probe.mjs https://example.com --crawl 15 --viewport mobile
 *   node probe.mjs https://example.com/checkout --js 'document.querySelector(".cookie-ok")?.click()'
 *   node probe.mjs https://example.com --repeat 5      # плавает или воспроизводится всегда
 *   node probe.mjs https://example.com --inventory     # что доступно под этой ролью
 *
 * Выход — JSON в stdout. Ненулевой код возврата, только если страница не открылась:
 * найденные проблемы это не ошибка выполнения, их решает человек или вызывающий агент.
 */

import { spawn, spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';

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
if (!argv.length || argv.includes('--help') || argv.includes('-h')) {
  console.error('usage: node probe.mjs <url> [--crawl N] [--viewport mobile|tablet|desktop]');
  console.error('                     [--width px] [--height px] [--wait мс] [--js "код"]');
  console.error('                     [--full] [--dump каталог] [--port 9222] [--keep]');
  process.exit(1);
}

const startUrl = argv[0];
const opt = (name, def) => {
  const i = argv.indexOf(name);
  return i === -1 ? def : argv[i + 1];
};

const VIEWPORTS = {
  mobile: [390, 844],
  tablet: [820, 1180],
  desktop: [1440, 900],
};
const preset = VIEWPORTS[opt('--viewport', 'desktop')] ?? VIEWPORTS.desktop;
const width = Number(opt('--width', preset[0]));
const height = Number(opt('--height', preset[1]));
const waitMs = Number(opt('--wait', 4000));
const crawl = Number(opt('--crawl', 0));
const js = opt('--js', null);
const port = Number(opt('--port', 9222));
const repeat = Math.max(1, Number(opt('--repeat', 1)));
const inventory = argv.includes('--inventory');
const full = argv.includes('--full');
const dumpDir = opt('--dump', null);
const keepBrowser = argv.includes('--keep');

if (dumpDir) mkdirSync(dumpDir, { recursive: true });

const CHROME = [
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
  '/usr/bin/google-chrome',
  '/usr/bin/chromium',
  '/usr/bin/chromium-browser',
].find((p) => existsSync(p));

const cdpAlive = async () => {
  try {
    const r = await fetch(`http://127.0.0.1:${port}/json/version`, { signal: AbortSignal.timeout(700) });
    return r.ok;
  } catch {
    return false;
  }
};

let startedBrowser = false;
if (!(await cdpAlive())) {
  if (!CHROME) {
    console.error('Не найден Chrome/Chromium. Поставь Chrome или укажи --port уже запущенного.');
    process.exit(1);
  }
  spawn(
    CHROME,
    [
      '--headless=new',
      '--disable-gpu',
      '--hide-scrollbars',
      `--remote-debugging-port=${port}`,
      `--user-data-dir=/tmp/probe-mjs-profile-${port}`,
      'about:blank',
    ],
    { detached: true, stdio: 'ignore' },
  ).unref();
  startedBrowser = true;

  const deadline = Date.now() + 15000;
  while (!(await cdpAlive())) {
    if (Date.now() > deadline) {
      console.error(`Chrome не поднял CDP на порту ${port} за 15 с`);
      process.exit(1);
    }
    await new Promise((r) => setTimeout(r, 250));
  }
}

// --- подключение к вкладке -------------------------------------------------

const tab = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })).json();
const ws = new WebSocket(tab.webSocketDebuggerUrl);
await new Promise((res, rej) => {
  ws.onopen = res;
  ws.onerror = () => rej(new Error('не удалось подключиться к CDP'));
});

let seq = 0;
const pending = new Map();
let collected = { console: [], network: [] };

ws.onmessage = (m) => {
  const msg = JSON.parse(m.data);
  if (msg.id && pending.has(msg.id)) {
    pending.get(msg.id)(msg.result);
    pending.delete(msg.id);
    return;
  }
  // Ошибки страницы и неудачные запросы копим сами: это то, чего не видно в DOM.
  if (msg.method === 'Log.entryAdded') {
    const e = msg.params.entry;
    if (e.level === 'error' || e.level === 'warning') {
      collected.console.push({ level: e.level, text: (e.text || '').slice(0, 200), url: e.url });
    }
  }
  if (msg.method === 'Runtime.exceptionThrown') {
    const d = msg.params.exceptionDetails;
    collected.console.push({
      level: 'error',
      text: (d.exception?.description || d.text || '').split('\n')[0].slice(0, 200),
    });
  }
  if (msg.method === 'Network.responseReceived') {
    const { status, url } = msg.params.response;
    if (status >= 400) collected.network.push({ status, url: url.slice(0, 160) });
  }
  if (msg.method === 'Network.loadingFailed') {
    if (!msg.params.canceled) {
      collected.network.push({ status: 'failed', error: msg.params.errorText });
    }
  }
};

const send = (method, params = {}) =>
  new Promise((res) => {
    const id = ++seq;
    pending.set(id, res);
    ws.send(JSON.stringify({ id, method, params }));
  });

await send('Page.enable');
await send('Log.enable');
await send('Runtime.enable');
await send('Network.enable');
// mobile: true заставляет Chrome применять собственную логику device emulation, и
// заданная ширина до страницы не доходит — innerWidth оказывается чужим (например 393
// вместо 320), а проверки молча меряют не тот экран. Поэтому ширину задаём в
// «десктопном» режиме, где она применяется буквально, а тач включаем отдельно:
// для вёрстки важна именно ширина, а для тач-целей — наличие сенсорного ввода.
await send('Emulation.setDeviceMetricsOverride', {
  width,
  height,
  deviceScaleFactor: 1,
  mobile: false,
});
if (width < 768) {
  await send('Emulation.setTouchEmulationEnabled', { enabled: true, maxTouchPoints: 5 });
}

// --- проверки, исполняемые внутри страницы ---------------------------------
//
// Всё, что можно посчитать в браузере, считаем там: наружу уходят только выводы.
// Каждая проверка возвращает список коротких описаний, пригодных для чтения человеком.

const PAGE_CHECKS = `(() => {
  const vis = (el) => {
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden' || Number(s.opacity) === 0) return false;
    // Содержимое свёрнутого <details> занимает место в разметке, но пользователю его нет:
    // без этой проверки пункты закрытого меню попадают в отчёт как «кликабельное без имени».
    const d = el.closest('details');
    if (d && !d.open && !el.closest('summary')) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const label = (el) => {
    const t = (el.innerText || el.getAttribute('alt') || el.getAttribute('aria-label') || '').trim();
    return t ? t.replace(/\\s+/g, ' ').slice(0, 60) : '<' + el.tagName.toLowerCase() + '>';
  };
  const out = {};
  const vw = window.innerWidth;

  // Горизонтальный скролл — самый заметный визуальный дефект адаптива.
  const docW = document.documentElement.scrollWidth;
  if (docW > vw + 1) {
    const culprits = [];
    for (const el of document.querySelectorAll('body *')) {
      if (!vis(el)) continue;
      const r = el.getBoundingClientRect();
      if (r.right > vw + 1 && r.width <= docW) {
        culprits.push(label(el) + ' → выходит на ' + Math.round(r.right - vw) + 'px');
        if (culprits.length >= 5) break;
      }
    }
    out.horizontalOverflow = { overflowPx: docW - vw, viewport: vw, culprits };
  }

  // Обрезанный текст: контейнер прячет то, что в нём не поместилось.
  // Многоточие и line-clamp — это осознанное решение дизайнера, а не дефект: текст
  // сокращён видимым для пользователя способом. Дефект — когда текст срезан по глифу.
  const clipped = [];
  for (const el of document.querySelectorAll('body *')) {
    if (!vis(el)) continue;
    const s = getComputedStyle(el);
    if (s.overflow === 'visible' && s.overflowX === 'visible' && s.overflowY === 'visible') continue;
    if (s.textOverflow === 'ellipsis') continue;
    if (s.webkitLineClamp && s.webkitLineClamp !== 'none') continue;
    const hasOwnText = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim().length > 3);
    if (!hasOwnText) continue;
    if (el.scrollWidth > el.clientWidth + 2 || el.scrollHeight > el.clientHeight + 2) {
      clipped.push(label(el));
      if (clipped.length >= 8) break;
    }
  }
  if (clipped.length) out.clippedText = clipped;

  // Битые изображения: загрузка завершилась, но пикселей нет.
  const broken = [...document.images]
    .filter((i) => i.complete && i.naturalWidth === 0)
    .map((i) => (i.currentSrc || i.src || '<без src>').slice(0, 120));
  if (broken.length) out.brokenImages = broken;

  // Ссылки-заглушки: выглядят кликабельными, никуда не ведут.
  const dead = [...document.querySelectorAll('a')]
    .filter((a) => {
      const h = (a.getAttribute('href') || '').trim();
      return h === '' || h === '#' || h.startsWith('javascript:void');
    })
    .filter(vis)
    .map(label);
  if (dead.length) out.placeholderLinks = [...new Set(dead)];

  // Одинаковый href у разных по смыслу ссылок — типичный незаполненный конфиг.
  const byHref = {};
  for (const a of document.querySelectorAll('a[href]')) {
    const h = a.getAttribute('href');
    if (!h || h === '#' || h.startsWith('/') === false && h.startsWith('http') === false) continue;
    (byHref[h] ||= []).push(label(a));
  }
  const suspiciousDupes = Object.entries(byHref)
    .filter(([, ls]) => ls.length >= 4 && new Set(ls).size >= 3)
    .map(([h, ls]) => h.slice(0, 100) + ' ← ' + ls.length + ' разных ссылок');
  if (suspiciousDupes.length) out.sameHrefManyLinks = suspiciousDupes;

  // Пустая страница: каркас отрисован, содержимого нет.
  const main = document.querySelector('main') || document.body;
  const mainText = (main.innerText || '').trim();
  if (mainText.length < 20) out.emptyContent = { chars: mainText.length };

  // Непереведённые ключи локализации, просочившиеся в текст.
  const keyLike = new Set();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const t = n.textContent.trim();
    if (/^[a-z][a-z0-9_]*(\\.[a-z0-9_]+){1,}$/i.test(t) && t.length < 60) keyLike.add(t);
    if (/^[A-Z][A-Z0-9_]{4,}$/.test(t)) keyLike.add(t);
  }
  if (keyLike.size) out.untranslatedKeys = [...keyLike];

  // Документ-уровень: заголовок, h1, язык, дубли id.
  const meta = {};
  if (!document.title || !document.title.trim()) meta.missingTitle = true;
  const h1 = document.querySelectorAll('h1');
  if (h1.length === 0) meta.missingH1 = true;
  if (h1.length > 1) meta.multipleH1 = h1.length;
  if (!document.documentElement.lang) meta.missingLang = true;
  const ids = {};
  for (const el of document.querySelectorAll('[id]')) ids[el.id] = (ids[el.id] || 0) + 1;
  const dupes = Object.entries(ids).filter(([, c]) => c > 1).map(([i, c]) => i + ' ×' + c);
  if (dupes.length) meta.duplicateIds = dupes;
  if (Object.keys(meta).length) out.documentIssues = meta;

  // Смешанный контент: http-ресурсы на https-странице браузер заблокирует.
  if (location.protocol === 'https:') {
    const mixed = [...document.querySelectorAll('[src], [href]')]
      .map((el) => el.getAttribute('src') || el.getAttribute('href'))
      .filter((u) => u && u.startsWith('http://'))
      .slice(0, 5);
    if (mixed.length) out.mixedContent = mixed;
  }

  // Кликабельное без доступного имени — и для a11y, и как признак недорисованной кнопки.
  const nameless = [...document.querySelectorAll('button, a[href], [role="button"]')]
    .filter(vis)
    .filter((el) => !(el.innerText || '').trim() && !el.getAttribute('aria-label') && !el.querySelector('img[alt]:not([alt=""])'))
    .map((el) => '<' + el.tagName.toLowerCase() + '> ' + (el.className || '').toString().slice(0, 40));
  if (nameless.length) out.namelessControls = nameless.slice(0, 8);

  // Мелкие тач-цели заметны только на узком экране.
  if (vw < 768) {
    const small = [...document.querySelectorAll('button, a[href], input, [role="button"]')]
      .filter(vis)
      .filter((el) => {
        const r = el.getBoundingClientRect();
        return r.width < 32 || r.height < 32;
      })
      .map(label);
    if (small.length) out.smallTouchTargets = [...new Set(small)].slice(0, 8);
  }

  // Скелетоны, застрявшие после загрузки, — частый признак неудавшегося запроса.
  // Настоящий скелетон — пустая плашка на месте будущего контента. Тот же класс
  // (shimmer, а иногда и skeleton) часто носит декоративная анимация по готовому
  // тексту — если внутри есть текст, это оформление, а не незавершённая загрузка.
  const skeletons = [...document.querySelectorAll('[class*="skeleton" i], [class*="shimmer" i], [aria-busy="true"]')]
    .filter(vis)
    .filter((el) => !(el.innerText || '').trim()).length;
  if (skeletons) out.stuckSkeletons = skeletons;

  out._page = {
    title: document.title || null,
    h1: h1[0] ? h1[0].innerText.trim().slice(0, 80) : null,
    textChars: mainText.length,
    docHeight: document.documentElement.scrollHeight,
    actualWidth: vw, // проверки верны только если совпадает с заданной шириной
  };

  // Внутренние ссылки для обхода.
  out._links = [...new Set(
    [...document.querySelectorAll('a[href]')]
      .map((a) => a.href)
      .filter((h) => h.startsWith(location.origin))
      .map((h) => h.split('#')[0]),
  )];

  // Инвентарь доступного: что видно и на что можно нажать на этой странице.
  // Снятый под разными ролями, он сравнивается построчно — и разница показывает,
  // что роль видит лишнего или недополучает.
  out._inventory = {
    links: [...new Set([...document.querySelectorAll('a[href]')]
      .filter(vis)
      .map((a) => label(a) + ' → ' + a.getAttribute('href')))].sort(),
    controls: [...new Set([...document.querySelectorAll('button, [role="button"], input[type="submit"]')]
      .filter(vis)
      .map(label))].sort(),
  };

  return JSON.stringify(out);
})()`;

// --- прогон одной страницы -------------------------------------------------

/**
 * Кладёт текст и разметку страницы файлами и возвращает пути с длинами.
 *
 * Зачем: выводы скрипта — производные числа, и проверить их постфактум нечем. Сырьё,
 * лежащее файлом с объявленной длиной, можно перечитать, процитировать в отчёте и
 * предъявить проверяющему. В контекст при этом попадает строка с путём, а не страница.
 * С --repeat в файлах останется последний прогон.
 */
async function dumpPage(url) {
  const grab = async (expr) => {
    const { result } = await send('Runtime.evaluate', { expression: expr, returnByValue: true });
    return typeof result?.value === 'string' ? result.value : '';
  };
  const text = await grab('document.body.innerText');
  const html = await grab('document.documentElement.outerHTML');
  let name;
  try {
    const u = new URL(url);
    name = (u.pathname + u.search).replace(/[^\w.-]+/g, '-').replace(/^-+|-+$/g, '');
  } catch {
    name = '';
  }
  const base = `${dumpDir}/${name || 'index'}`;
  writeFileSync(`${base}.txt`, text);
  writeFileSync(`${base}.html`, html);
  return { text: `${base}.txt`, textChars: text.length, html: `${base}.html`, htmlChars: html.length };
}

async function probePage(url) {
  collected = { console: [], network: [] };
  await send('Page.navigate', { url });
  await new Promise((r) => setTimeout(r, waitMs));

  if (js) {
    await send('Runtime.evaluate', { awaitPromise: true, expression: js });
    await new Promise((r) => setTimeout(r, 700));
  }

  // Прокрутка: ленивые картинки и секции с IntersectionObserver иначе не проявятся.
  await send('Runtime.evaluate', {
    awaitPromise: true,
    expression: `(async()=>{const h=document.documentElement.scrollHeight;
      for(let y=0;y<h;y+=700){window.scrollTo(0,y);await new Promise(r=>setTimeout(r,90));}
      window.scrollTo(0,0);await new Promise(r=>setTimeout(r,300));})()`,
  });

  const { result } = await send('Runtime.evaluate', { expression: PAGE_CHECKS, returnByValue: true });
  let checks = {};
  try {
    checks = JSON.parse(result?.value ?? '{}');
  } catch {
    checks = { _error: 'проверки не выполнились — страница могла не загрузиться' };
  }

  const page = checks._page ?? {};
  const links = checks._links ?? [];
  const inv = checks._inventory ?? null;
  delete checks._page;
  delete checks._links;
  delete checks._inventory;

  const cut = (arr) => (full || arr.length <= 3 ? arr : [...arr.slice(0, 3), `…ещё ${arr.length - 3}`]);
  for (const [k, v] of Object.entries(checks)) if (Array.isArray(v)) checks[k] = cut(v);

  const consoleErrors = collected.console.filter((c) => c.level === 'error');
  const findings = { ...checks };
  if (consoleErrors.length) findings.consoleErrors = cut(consoleErrors.map((c) => c.text));
  if (collected.network.length) {
    findings.failedRequests = cut(
      collected.network.map((n) => `${n.status} ${n.url ?? n.error ?? ''}`.trim()),
    );
  }

  const dump = dumpDir ? await dumpPage(url) : null;

  return {
    url,
    ...page,
    findings,
    issueCount: Object.keys(findings).length,
    ...(dump ? { dump } : {}),
    links,
    inventory: inv,
  };
}

/**
 * Прогоняет страницу repeat раз и отмечает, в скольких прогонах встретилась каждая находка.
 * Дефект, воспроизводящийся 2 раза из 5, — это не шум, который можно выбросить, и не
 * стабильный баг: это плавающий дефект, и в отчёте он должен называться именно так,
 * иначе разработчик не воспроизведёт его с первой попытки и закроет как ненайденный.
 */
async function probePageRepeated(url) {
  const runs = [];
  for (let i = 0; i < repeat; i++) runs.push(await probePage(url));
  const last = runs[runs.length - 1];
  if (repeat === 1) return last;

  const seenCount = {};
  for (const r of runs) for (const k of Object.keys(r.findings)) seenCount[k] = (seenCount[k] || 0) + 1;

  // Показываем объединение находок всех прогонов: то, что мелькнуло однажды, тоже важно.
  const merged = {};
  for (const r of runs) for (const [k, v] of Object.entries(r.findings)) if (!(k in merged)) merged[k] = v;

  const flaky = Object.entries(seenCount)
    .filter(([, c]) => c < repeat)
    .map(([k, c]) => `${k}: ${c}/${repeat}`);

  return {
    ...last,
    findings: merged,
    issueCount: Object.keys(merged).length,
    ...(flaky.length ? { unstable: flaky } : { stability: `все находки воспроизвелись ${repeat}/${repeat}` }),
  };
}

// --- обход -----------------------------------------------------------------

const budget = Math.max(1, crawl); // --crawl 0 означает «только стартовая страница»
const seen = new Set();
const queue = [startUrl];
const results = [];

while (queue.length && results.length < budget) {
  const url = queue.shift();
  const key = url.split('#')[0];
  if (seen.has(key)) continue;
  seen.add(key);

  const r = await probePageRepeated(url);
  const { links, inventory: inv, ...rest } = r;
  results.push(inventory ? { ...rest, inventory: inv } : rest);

  for (const l of links) {
    if (!seen.has(l) && !queue.includes(l) && queue.length + results.length < budget) queue.push(l);
  }
}

// Проблема, повторяющаяся на каждой странице, — это одна находка в общем шаблоне,
// а не N находок. Разводим их сразу, чтобы агент не заводил дубли.
const perPage = results.length;
const counts = {};
for (const r of results) for (const k of Object.keys(r.findings)) counts[k] = (counts[k] || 0) + 1;
const threshold = Math.max(2, Math.ceil(perPage * 0.6));
const sitewide = Object.entries(counts)
  .filter(([, c]) => perPage > 1 && c >= threshold)
  .map(([k]) => k);

// Если эмуляция не применилась, все замеры относятся к другому экрану, и молчание
// детекторов ничего не значит. Такое расхождение должно быть видно сразу, а не после
// того, как отчёт разошёлся по людям.
const wrongWidth = results.filter((r) => r.actualWidth && Math.abs(r.actualWidth - width) > 1);

const report = {
  probedAt: new Date().toISOString(),
  // Чей Chrome отвечал — часть результата. Свой headless всегда анонимен, чужой работает
  // под открытой в нём сессией. Без этой строки «поля нет» неотличимо от «я не залогинен».
  browser: startedBrowser ? `свой headless :${port}` : `чужой Chrome :${port}`,
  viewport: `${width}x${height}`,
  ...(wrongWidth.length
    ? {
        WARNING: `запрошена ширина ${width}, страница отрендерена в ${wrongWidth[0].actualWidth} — ` +
          'результатам по вёрстке верить нельзя',
      }
    : {}),
  pages: perPage,
  sitewideIssues: sitewide,
  results: results.map((r) => ({
    ...r,
    findings: Object.fromEntries(Object.entries(r.findings).filter(([k]) => !sitewide.includes(k))),
  })),
};
if (sitewide.length) {
  report.sitewideDetail = Object.fromEntries(sitewide.map((k) => [k, results[0].findings[k]]));
}

console.log(JSON.stringify(report, null, 1));

await send('Page.close');
if (startedBrowser && !keepBrowser) {
  // Ответ на Browser.close не приходит — браузер рвёт сокет раньше. Без гонки с таймаутом
  // верхнеуровневый await остаётся неразрешённым и Node уходит с кодом 13, хотя отчёт уже
  // напечатан. Обёртка с `set -e` считает такой прогон упавшим.
  await Promise.race([send('Browser.close'), new Promise((r) => setTimeout(r, 500))]);
}
ws.close();
process.exit(0);
