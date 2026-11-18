---
paths:
  - "Appium/**/*.py"
  - "Tests/Mobile_tests/**/*.py"
---

# Мобильный слой: экраны, модули, локаторы

Правило грузится при чтении файлов `Appium/` и `Tests/Mobile_tests/`.
Полная процедура — [docs/mobile.md](../../docs/mobile.md).

## Раскладка

- `Appium/driver_func.py` — фабрика драйвера, UiAutomator2/XCUITest по env
  `PLATFORM`.
- `Appium/app_keys/` — локаторы экрана по стабильному id, база `ScreenActions`
  с методом `get_element`.
- `Appium/Modules/` — модули взаимодействия с фичей.

Новый экран → копия `Appium/app_keys/example_feature_buttons.py` плюс
`Appium/Modules/example_module.py`. Эталоны остаются нетронутыми.

## Локаторы видит НАТИВНЫЙ Appium

Драйверы здесь нативные (UiAutomator2 / XCUITest), а не `flutter`. Для
Flutter-приложения это значит: `ValueKey` в дампе НЕ виден, нужен
`Semantics(identifier:)`. Ключ, честно проставленный в коде, может
отсутствовать на устройстве — **проверяется дампом UI-дерева**
(`dump_ui_tree.py`), а не чтением исходников приложения.

Идентификаторов нет, а репозиторий приложения доступен (`docs/apps-repos.md`)
→ сначала `/qa-auto:keys-mobile`, выкат на стенд, повторный дамп, и только потом тест.

## Состояние приложения между тестами

Фикстура `driver` данные приложения НЕ чистит: на iOS приложение ставится
поверх, PIN, keychain и сессия переживают прогон. Тест, доводящий
приложение до такого состояния (вход, PIN, согласия), запрашивает фикстуру
`reset_app_after_test` из `Tests/Mobile_tests/conftest.py`: iOS —
`remove_app` + `install_app` той же сессией, Android — `mobile: clearApp`.
Своей копии этого сброса в conftest фичи заводить не надо, общий `driver`
ради этого не трогать.

## Удалённые имена

`Button_actions`, `ButtonActions`, `get_element_by_value_key`,
`driver_functions`, `Flutter_tests` — заменены на `ScreenActions.get_element`,
`DriverFunctions` и `Tests/Mobile_tests`.
