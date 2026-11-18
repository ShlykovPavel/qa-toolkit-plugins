#!/usr/bin/env node
/**
 * shot.mjs — полностраничный скриншот страницы через Chrome DevTools Protocol.
 *
 * Зачем не `chrome --headless --screenshot`: тот снимает ровно окно, поэтому длинную
 * страницу приходится задавать огромным --window-size, а секции с `min-height: 100vh`
 * при этом растягиваются на всю его высоту — вёрстка на снимке не совпадает с реальной.
 * Здесь viewport остаётся нормальным (1440x1200), а захват идёт за его пределы
 * (captureBeyondViewport), так что снимок совпадает с тем, что видит человек.
 *
 * Перед захватом страница прокручивается шагами: секции с IntersectionObserver
 * (анимация появления) иначе остаются с opacity: 0 и попадают в кадр пустыми.
 *
 *   node shot.mjs <url> <out.png> [опции]
 *
 *   --wait <мс>      пауза после навигации, по умолчанию 8000 (клиентский рендер)
 *   --viewport <имя> mobile (390x844) | tablet (820x1180) | desktop (1440x1200)
 *   --width <px>     своя ширина вместо пресета
 *   --height <px>    своя высота вместо пресета
 *   --js '<код>'     выполнить перед захватом: раскрыть аккордеон, открыть меню, кликнуть таб
 *   --no-scroll      не прокручивать (быстрее, но анимированные секции будут пустыми)
 *   --port <порт>    CDP-порт, по умолчанию 9222
 *   --keep           не гасить Chrome после съёмки (быстрее для серии снимков)
 *
 * Примеры:
 *   node shot.mjs https://example.com home.png
 *   node shot.mjs https://example.com faq.png \
 *     --js '[...document.querySelectorAll("button")].find(b=>/вернуть деньги/.test(b.innerText))?.click()'
 *
 * Обрезать нужный фрагмент (координаты берутся из живой страницы через
 * getBoundingClientRect + scrollY — вёрстка та же, что на снимке):
 *   python3 -c "from PIL import Image; Image.open('home.png').crop((60,600,1380,980)).save('crop.png')"
 */

import { spawn, spawnSync } from 'node:child_process';
import { writeFileSync, statSync, existsSync } from 'node:fs';

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
if (argv.length < 2 || argv.includes('--help') || argv.includes('-h')) {
  console.error('usage: node shot.mjs <url> <out.png> [--wait мс] [--viewport mobile|tablet|desktop]');
  console.error('                     [--width px] [--height px] [--js "код"] [--no-scroll]');
  console.error('                     [--port 9222] [--keep]');
  process.exit(1);
}

const [url, out] = argv;
const opt = (name, def) => {
  const i = argv.indexOf(name);
  return i === -1 ? def : argv[i + 1];
};
const VIEWPORTS = {
  mobile: [390, 844],
  tablet: [820, 1180],
  desktop: [1440, 1200],
};
const preset = VIEWPORTS[opt('--viewport', 'desktop')] ?? VIEWPORTS.desktop;
const waitMs = Number(opt('--wait', 8000));
const width = Number(opt('--width', preset[0]));
const height = Number(opt('--height', preset[1]));
const js = opt('--js', null);
const port = Number(opt('--port', 9222));
const doScroll = !argv.includes('--no-scroll');
const keepBrowser = argv.includes('--keep');

const CHROME = [
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
].find((p) => existsSync(p));

const cdpAlive = async () => {
  try {
    const r = await fetch(`http://127.0.0.1:${port}/json/version`, { signal: AbortSignal.timeout(700) });
    return r.ok;
  } catch {
    return false;
  }
};

// Chrome поднимаем сами, только если на порту ещё никого нет.
let started = false;
if (!(await cdpAlive())) {
  if (!CHROME) {
    console.error('Не найден Google Chrome и Chromium — поставь Chrome или укажи уже запущенный --port');
    process.exit(1);
  }
  spawn(
    CHROME,
    [
      '--headless=new',
      '--disable-gpu',
      '--hide-scrollbars',
      `--remote-debugging-port=${port}`,
      `--user-data-dir=/tmp/shot-mjs-profile-${port}`,
      'about:blank',
    ],
    { detached: true, stdio: 'ignore' },
  ).unref();
  started = true;

  const deadline = Date.now() + 15000;
  while (!(await cdpAlive())) {
    if (Date.now() > deadline) {
      console.error(`Chrome не поднял CDP на порту ${port} за 15 с`);
      process.exit(1);
    }
    await new Promise((r) => setTimeout(r, 250));
  }
}

const tab = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })).json();
const ws = new WebSocket(tab.webSocketDebuggerUrl);
await new Promise((res, rej) => {
  ws.onopen = res;
  ws.onerror = () => rej(new Error('не удалось подключиться к CDP'));
});

let seq = 0;
const pending = new Map();
ws.onmessage = (m) => {
  const msg = JSON.parse(m.data);
  if (msg.id && pending.has(msg.id)) {
    pending.get(msg.id)(msg.result);
    pending.delete(msg.id);
  }
};
const send = (method, params = {}) =>
  new Promise((res) => {
    const id = ++seq;
    pending.set(id, res);
    ws.send(JSON.stringify({ id, method, params }));
  });

await send('Page.enable');
await send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: false });
await send('Page.navigate', { url });
await new Promise((r) => setTimeout(r, waitMs));

if (doScroll) {
  await send('Runtime.evaluate', {
    awaitPromise: true,
    expression: `(async()=>{const h=document.documentElement.scrollHeight;
      for(let y=0;y<h;y+=600){window.scrollTo(0,y);await new Promise(r=>setTimeout(r,120));}
      window.scrollTo(0,0);await new Promise(r=>setTimeout(r,400));})()`,
  });
}

if (js) {
  await send('Runtime.evaluate', { awaitPromise: true, expression: js });
  await new Promise((r) => setTimeout(r, 900));
}

const { data } = await send('Page.captureScreenshot', {
  format: 'png',
  captureBeyondViewport: true,
  fromSurface: true,
});
writeFileSync(out, Buffer.from(data, 'base64'));

const { result } = await send('Runtime.evaluate', {
  expression: 'document.documentElement.scrollHeight',
  returnByValue: true,
});
// Чей это Chrome — часть результата, а не деталь реализации: снимок из своего headless
// сделан анонимно, снимок из чужого — под той сессией, что в нём открыта. Молчание об
// этом превращает «поля нет» в «я не залогинен».
const chromeSrc = started ? `свой headless :${port}` : `чужой Chrome :${port}`;
console.log(`${out}  ${statSync(out).size} байт  ${width}x${result?.value ?? '?'}  chrome: ${chromeSrc}`);

await send('Page.close');
if (started && !keepBrowser) {
  // Ответ на Browser.close не приходит — браузер рвёт сокет раньше. Без гонки с
  // таймаутом верхнеуровневый await остаётся неразрешённым и Node уходит с кодом 13,
  // хотя снимок сделан. Обёртка с `set -e` считает такой прогон упавшим.
  await Promise.race([send('Browser.close'), new Promise((r) => setTimeout(r, 500))]);
}
ws.close();
process.exit(0);
