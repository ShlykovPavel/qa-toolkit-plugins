# Мобильный стенд с нуля: от чистой машины до первого дампа

[../mobile.md](../mobile.md) учит писать тесты, когда стенд уже дышит.
Эта статья — про путь ДО того: что поставить на машину, что заполнить в
`.env` и как убедиться, что связка «эмулятор → Appium → приложение»
живая. Ориентир — Android (основной путь), iOS — отдельной секцией.

> **Про версии.** Экосистема Appium/SDK меняется быстро; конкретные
> команды здесь соответствуют состоянию на июль 2026 — при расхождении
> верь официальным докам Appium и Android Studio, а сюда принеси правку.

---

## Слои стенда (что вообще должно работать)

```
Android SDK (эмулятор, adb)  ← железо/симуляция
    ↑
Appium-сервер + драйвер UiAutomator2/XCUITest  ← мост
    ↑
этот фреймворк (фикстуры Tests/Mobile_tests/conftest.py)  ← автозапуск
```

Важно понимать, что фреймворк поднимает САМ, а что должен обеспечить ты.
Автоматически (autouse) — только Appium-сервер: фикстура
`launch_appium_server` поднимет его, если он не отвечает на
`:4723/status`. Фикстуры `launch_android_emulator` (запуск эмулятора) и
`install_apk` (установка APK) НЕ autouse — форк подключает их к тестам
явно. Команды `appium`, `emulator` и `adb` должны существовать на машине
и находиться в PATH того процесса, из которого запускается pytest. Твоя
работа — установить их, прописать PATH и заполнить `.env`.

## Android: установка

**1. Android SDK.** Проще всего — Android Studio (тянет SDK, эмулятор и
platform-tools). Запомни путь к SDK (обычно `~/Library/Android/sdk` на
macOS, `~/Android/Sdk` на Linux) — он пойдёт в env. Для ручных запусков
удобно добавить в профиль шелла:

```bash
export ANDROID_HOME="$HOME/Library/Android/sdk"
export PATH="$ANDROID_HOME/emulator:$ANDROID_HOME/platform-tools:$PATH"
```

Экспорт в профиле обязателен и для прогонов: фреймворк запускает
`emulator`/`adb` обычным subprocess'ом и полагается на унаследованный
PATH (функция `set_android_env`, читающая `ANDROID_HOME_FOR_SIM_LAUNCH`,
в текущем коде не вызывается — её вызов закомментирован в
`Appium/Simulator/Android_emulator.py`). Переменную в `.env` всё равно
заполни — но на неё одну не рассчитывай.

**2. Эмулятор (AVD).** Android Studio → Device Manager → создать
устройство (или `avdmanager` из cmdline-tools). Имя AVD — то, что пойдёт
в `ANDROID_DEVICE_NAME`. Убедись, что включено аппаратное ускорение —
эмулятор без него неюзабельно медленный.

**3. Appium.** Нужен Node.js, затем:

```bash
npm install -g appium
appium driver install uiautomator2
appium --version && appium driver list --installed   # самопроверка
```

`appium` должен быть в PATH того шелла, из которого запускается pytest —
иначе фикстура запуска сервера упадёт с «Appium не найден».

**4. Тестовый билд.** APK от разработчиков (debug или release с
проставленными идентификаторами — см.
[../locator-conventions.md](../locator-conventions.md)). Путь к файлу —
в `APK_PATH`; установку на эмулятор делает фикстура `install_apk`.

**5. Мобильная секция `.env`** (полный список — [../mobile.md](../mobile.md), «Env-переменные»):

| Переменная | Что это |
|---|---|
| `PLATFORM` | `android` (или `iOS`) — ветка фабрики драйвера |
| `ANDROID_DEVICE_NAME` | имя AVD из шага 2 |
| `ANDROID_APP_PACKAGE` / `ANDROID_APP_ACTIVITY` | package и стартовая activity билда (спроси разработчиков или `aapt dump badging <apk>`) |
| `APK_PATH` | путь к тестовому APK |
| `ANDROID_HOME_FOR_SIM_LAUNCH` | путь к Android SDK (шаг 1) |
| `REMOTE_PATH_IN_EMULATOR` | путь в эмуляторе для записи экрана |
| `MOBILE_ELEMENT_TIMEOUT` | таймаут поиска элемента, дефолт 5 с |
| `LOCALIZATION_FILE_PATH` | JSON локализации (`Appium/localization/`) |

## Android: проверка, что стенд дышит

По шагам, каждый изолирует свой слой:

```bash
# 1. SDK и эмулятор: устройство видно?
adb devices          # ожидаем emulator-5554  device

# 2. Appium-сервер отвечает? (если запускал руками: appium &)
curl -s http://localhost:4723/status   # ожидаем {"value":{"ready":true,...}}

# 3. Приложение установлено и открывается руками на эмуляторе?

# 4. Финальный тест всей связки — первый дамп:
dump_ui_tree.py --wait-manual 30 --raw-out screen.xml
```

Если шаг 4 вернул XML со списком идентификаторов — стенд готов, дальше
по [../mobile.md](../mobile.md). Если идентификаторов в дампе нет — стенд
готов, а приложение нет: это блокер разработчикам
([../locator-conventions.md](../locator-conventions.md)), не проблема
окружения.

## iOS: отличия

1. Нужен macOS + Xcode (+ принятая лицензия и скачанный симулятор нужной
   версии iOS). Драйвер: `appium driver install xcuitest`.
2. WebDriverAgent (WDA) — агент на устройстве, через который работает
   XCUITest: для симулятора Appium собирает его сам при первой сессии
   (долго — это нормально). Альтернатива, снимающая большинство болей, —
   `prepare_ios_simulator` из appium-mcp
   ([appium-mcp.md](appium-mcp.md)): бут симулятора + prebuilt WDA.
3. `.env`: `PLATFORM=iOS`, `IOS_DEVICE_NAME`, `IOS_PLATFORM_VERSION`,
   `IOS_UDID` (симулятор: `xcrun simctl list devices`), `IOS_BUNDLE_ID`;
   для РЕАЛЬНОГО устройства дополнительно подпись WDA — `xcodeOrgId` /
   `xcodeSigningId` (Team ID из Apple Developer аккаунта).
4. Проверка WDA при поднятой сессии:
   `curl http://127.0.0.1:8100/source?format=xml` — вернулся XML → мост
   работает.

Реальные iOS-девайсы — отдельная территория (провижининг-профили,
доверие к разработчику на устройстве) — сверяйся с доками
appium-xcuitest-driver.

## Частые грабли

| Сигнатура | Причина и лечение |
|---|---|
| Фикстура сервера падает «Appium не найден» | `appium` не в PATH процесса pytest — ставь глобально (`npm install -g`) или добавь в PATH; параметр `appium_command` у `ensure_appium_running` есть, но conftest вызывает её без аргументов — переопределение пути потребует правки вызова |
| Эмулятор «поднялся», тесты падают на таймауте загрузки | холодный старт AVD дольше ожидания готовности (120 с) — прогрей эмулятор заранее или включи snapshot-загрузку |
| `adb devices` пусто при живом эмуляторе | конфликт adb-серверов (например, от Android Studio) — `adb kill-server && adb devices` |
| В дампе ноль идентификаторов на Compose-экране | `testTagsAsResourceId` не включён — блокер разработчикам, детали в [../locator-conventions.md](../locator-conventions.md) |
| `uiautomator dump` молчит/ошибается при живой сессии | accessibility-канал занят UiAutomator2 — из живой сессии только page_source ([../mobile.md](../mobile.md)) |
| Flutter release-билд «пустой» глазами дампа | Semantics-дерево строится при подключённом accessibility-клиенте — проверяй дампом через Appium, не глазами |
| Первая iOS-сессия висит минуты | сборка WDA — норма для первого раза; следующие сессии быстрые |

Найденную новую граблю — сюда (правкой этой таблицы) или в «Копилку
ловушек проекта» в [../mobile.md](../mobile.md), если она специфична
твоему проекту.
