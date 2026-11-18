#!/usr/bin/env python3
"""Дамп интерактивных элементов страницы — «глаза» скилла frontend-tests.

Два режима:

1. Один снимок (дефолт): открывает страницу headless-браузером
   (frontend/driver_factory.get_driver) и выводит JSON — для каждого
   интерактивного элемента tag, видимый текст и кандидат-локатор по
   лестнице приоритетов ВЫБРАННОЙ ветки (--locators, см. docs/frontend.md):

    css  (дефолт, selenium-ветка): id → data-testid → name → css → xpath
          → link_text; нет стабильного уникального — fragile: true;
    role (playwright-ветка): get_by_role(+name) → get_by_label →
          get_by_placeholder → get_by_test_id → css-резерв (fragile).

2. ПРОХОД СЦЕНАРИЯ (--walkthrough) — для страниц ЗА ЛОГИНОМ и состояний
   БЕЗ своего URL (модалки, тосты, шаги визарда, ошибки валидации):
   ОДНА живая НЕ-headless сессия браузера (HEADLESS форсируется в false —
   окном управляет человек), человек логинится и ведёт сценарий руками,
   после каждого шага жмёт Enter в терминале — скрипт снимает дамп DOM
   (та же лестница локаторов) + скриншот шага в папку и пишет steps.json
   с последовательностью шагов (шаги → почти готовые методы page object).

Примеры:
    python3 ${CLAUDE_PLUGIN_ROOT}/bin/dump_dom.py --url https://admin.example.com/users
    python3 ${CLAUDE_PLUGIN_ROOT}/bin/dump_dom.py --url admin-page/index.html   # путь к файлу
    python3 ${CLAUDE_PLUGIN_ROOT}/bin/dump_dom.py --url page.html --locators role
    python3 ${CLAUDE_PLUGIN_ROOT}/bin/dump_dom.py --url page.html --scope "#main" --out dump.json
    python3 ${CLAUDE_PLUGIN_ROOT}/bin/dump_dom.py --walkthrough dumps/create_user \
        --url https://admin.example.com/login   # стартовая страница прохода

Путь к html-файлу (без схемы) резолвится от cwd в абсолютный file:// —
поэтому относительные пути из паспорта проекта работают из корня репо.
Роль и accessible name в role-режиме вычисляются приближённо (таблица
тег→роль + label/aria-label/текст) — этого достаточно для кандидатов,
спорные случаи сверяй с Playwright MCP или codegen.
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

# Корень проекта в sys.path: frontend/ — не пакет, а скрипт лежит в плагине.
# Запускается из корня проекта.
sys.path.insert(0, str(Path.cwd()))

from selenium.webdriver.common.by import By  # noqa: E402

from frontend.driver_factory import get_driver  # noqa: E402

# Что считаем интерактивным элементом; [role=alert]/[role=status] — не
# интерактивны, но это элементы обратной связи (тосты, индикаторы), чьи
# селекторы нужны тестам для проверки ожидаемого результата.
INTERACTIVE_CSS = (
    "a, button, input, select, textarea, [role=button], [onclick], "
    "[data-testid], [role=alert], [role=status]"
)
TEXT_LIMIT = 40


def resolve_url(url: str) -> str:
    """http/https/file — как есть; иначе путь к html-файлу → file:// от cwd."""
    if url.startswith(("http://", "https://", "file://", "data:")):
        return url
    path = Path(url).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.resolve()
    if not path.exists():
        raise FileNotFoundError(f"Файл не найден: {path}")
    return path.as_uri()


def _visible_text(element) -> str:
    """Видимый текст (или value/placeholder для инпутов), обрезанный до лимита."""
    text = (element.text or "").strip()
    if not text:
        text = (
            element.get_attribute("value")
            or element.get_attribute("placeholder")
            or ""
        ).strip()
    return text[:TEXT_LIMIT]


def _is_unique(driver, by, value) -> bool:
    """Селектор указывает ровно на один элемент страницы."""
    try:
        return len(driver.find_elements(by, value)) == 1
    except Exception:
        return False


def _css_escape(value: str) -> str:
    """Минимальное экранирование значения атрибута для css-селектора."""
    return value.replace('"', '\\"')


def _stable_css(driver, element, tag: str):
    """Уникальный css по классам элемента: .cls / tag.cls / tag.cls1.cls2."""
    classes = (element.get_attribute("class") or "").split()
    for cls in classes:
        for sel in (f".{cls}", f"{tag}.{cls}"):
            if _is_unique(driver, By.CSS_SELECTOR, sel):
                return sel
    if len(classes) > 1:
        sel = tag + "".join(f".{c}" for c in classes)
        if _is_unique(driver, By.CSS_SELECTOR, sel):
            return sel
    return None


def _stable_xpath(driver, element, tag: str):
    """Уникальный атрибутный xpath (type/placeholder/aria-label/href/value)."""
    for attr in ("type", "placeholder", "aria-label", "href", "value", "role"):
        value = element.get_attribute(attr)
        if value:
            xpath = f'//{tag}[@{attr}="{value}"]'
            if _is_unique(driver, By.XPATH, xpath):
                return xpath
    return None


def _positional_xpath(driver, element) -> str:
    """Позиционный xpath от корня — последний резерв (хрупкий по определению)."""
    return driver.execute_script(
        """
        function xpathOf(el) {
            if (el === document.body) return '/html/body';
            var ix = 1, sibs = el.parentNode ? el.parentNode.children : [];
            for (var i = 0; i < sibs.length; i++) {
                if (sibs[i] === el) break;
                if (sibs[i].tagName === el.tagName) ix++;
            }
            return xpathOf(el.parentNode) + '/' + el.tagName.toLowerCase()
                + '[' + ix + ']';
        }
        return xpathOf(arguments[0]);
        """,
        element,
    )


# --- role-режим (playwright-ветка) ---------------------------------------

# Приближённая карта тег/тип → ARIA-роль (для кандидатов достаточно)
def _aria_role(element, tag: str):
    explicit = element.get_attribute("role")
    if explicit:
        return explicit
    if tag == "a":
        return "link" if element.get_attribute("href") else None
    if tag == "button":
        return "button"
    if tag == "select":
        return "combobox"
    if tag == "textarea":
        return "textbox"
    if tag == "input":
        input_type = (element.get_attribute("type") or "text").lower()
        return {
            "text": "textbox", "email": "textbox", "tel": "textbox",
            "url": "textbox", "password": "textbox", "search": "searchbox",
            "checkbox": "checkbox", "radio": "radio", "number": "spinbutton",
            "submit": "button", "button": "button", "range": "slider",
        }.get(input_type)
    return None


def _label_text(driver, element):
    """Текст <label for=...> или обёртывающего label (accessible name инпута)."""
    element_id = element.get_attribute("id")
    if element_id:
        labels = driver.find_elements(
            By.CSS_SELECTOR, f'label[for="{_css_escape(element_id)}"]')
        if labels and labels[0].text.strip():
            return labels[0].text.strip()
    return driver.execute_script(
        "var l = arguments[0].closest('label');"
        "return l ? l.textContent.trim() : null;", element)


def _accessible_name(driver, element, tag: str):
    aria = element.get_attribute("aria-label")
    if aria:
        return aria.strip()
    if tag in ("input", "select", "textarea"):
        return _label_text(driver, element)
    text = (element.text or "").strip()
    return text or (element.get_attribute("value") or "").strip() or None


def _role_name_unique(driver, role, name) -> bool:
    """Ровно один элемент страницы даёт эту пару роль+имя (приближённо).

    name=None — проверка уникальности самой роли (для get_by_role без name:
    например единственный [role=alert] на странице).
    """
    count = 0
    for other in driver.find_elements(By.CSS_SELECTOR, INTERACTIVE_CSS):
        other_tag = other.tag_name.lower()
        if _aria_role(other, other_tag) != role:
            continue
        if name is None or _accessible_name(driver, other, other_tag) == name:
            count += 1
    return count == 1


def candidate_locator_role(driver, element, tag: str):
    """Кандидат-локатор по лестнице playwright-ветки.

    :return: (kind, value, fragile) — kind в терминах Page.get_by_*.
    """
    role = _aria_role(element, tag)
    name = _accessible_name(driver, element, tag)
    if role and name and _role_name_unique(driver, role, name):
        return "get_by_role", {"role": role, "name": name}, False

    if tag in ("input", "select", "textarea"):
        label = _label_text(driver, element)
        if label:
            return "get_by_label", label, False
        placeholder = element.get_attribute("placeholder")
        if placeholder:
            return "get_by_placeholder", placeholder, False

    testid = element.get_attribute("data-testid")
    if testid:
        return "get_by_test_id", testid, False

    # роль без имени — если она одна на страницу (единственный alert/combobox)
    if role and _role_name_unique(driver, role, None):
        return "get_by_role", {"role": role}, False

    # css-резерв: механика selenium-режима, но для pw-ветки это уже техдолг;
    # значение конвертируется в валидный аргумент page.locator()
    by, value, _ = candidate_selector(driver, element, tag)
    locator_value = {
        "id": f"#{value}",
        "name": f'[name="{value}"]',
        "link_text": f"text={value}",
    }.get(by, value)  # css_selector и xpath (//...) locator() понимает как есть
    return "locator", locator_value, True


def candidate_selector(driver, element, tag: str):
    """Кандидат-селектор по полной лестнице приоритетов docs/frontend.md.

    :return: (by, value, fragile) — by в терминах методов ButtonFinder.
    """
    element_id = element.get_attribute("id")
    if element_id and _is_unique(driver, By.ID, element_id):
        return "id", element_id, False

    testid = element.get_attribute("data-testid")
    if testid:
        sel = f'[data-testid="{_css_escape(testid)}"]'
        if _is_unique(driver, By.CSS_SELECTOR, sel):
            return "css_selector", sel, False

    name = element.get_attribute("name")
    if name and _is_unique(driver, By.NAME, name):
        return "name", name, False

    css = _stable_css(driver, element, tag)
    if css:
        return "css_selector", css, False

    xpath = _stable_xpath(driver, element, tag)
    if xpath:
        return "xpath", xpath, False

    if tag == "a":
        link_text = (element.text or "").strip()
        if link_text and _is_unique(driver, By.LINK_TEXT, link_text):
            return "link_text", link_text, True  # ломается при смене локализации

    return "xpath", _positional_xpath(driver, element), True


def _summary(elements) -> dict:
    """Сводка по списку элементов (та же в одиночном дампе и в шаге прохода)."""
    return {
        "total": len(elements),
        "with_testid": sum(1 for e in elements if "data_testid" in e),
        "fragile": sum(1 for e in elements if e.get("fragile")),
    }


def dump_page(driver, scope_css=None, locators_mode="css"):
    """Собирает интерактивные элементы страницы (или контейнера --scope)."""
    root = driver.find_element(By.CSS_SELECTOR, scope_css) if scope_css else driver
    elements, seen = [], set()
    for element in root.find_elements(By.CSS_SELECTOR, INTERACTIVE_CSS):
        if element.id in seen:
            continue
        seen.add(element.id)
        tag = element.tag_name.lower()
        if locators_mode == "role":
            by, value, fragile = candidate_locator_role(driver, element, tag)
        else:
            by, value, fragile = candidate_selector(driver, element, tag)
        entry = {
            "tag": tag,
            "text": _visible_text(element),
            "selector": {"by": by, "value": value},
            "visible": element.is_displayed(),
        }
        testid = element.get_attribute("data-testid")
        if testid:
            entry["data_testid"] = testid
        if fragile:
            entry["fragile"] = True
        elements.append(entry)
    return elements


def _sanitize_step_name(name: str) -> str:
    """Имя шага → безопасный кусок имени файла (кириллица сохраняется)."""
    return re.sub(r'[^\w-]+', '_', name.strip()).strip('_')[:40]


def run_walkthrough(driver, out_dir: str, locators_mode: str = "css",
                    scope_css: str = None, input_fn=input) -> list:
    """Проход сценария: на каждый шаг человека — дамп DOM + скриншот в out_dir.

    Одна живая сессия на весь проход — логин и состояния без своего URL
    (модалки, шаги визарда) не теряются между шагами. Человек делает шаг
    в браузере, возвращается в терминал, вводит имя шага (или пустую
    строку) и Enter — снимается дамп и скриншот текущего состояния.
    `q` — закончить. steps.json перезаписывается после каждого шага —
    обрыв посреди прохода не теряет уже снятые шаги.

    :param driver: живой Selenium-драйвер (или совместимый объект в смоуке)
    :param out_dir: папка результатов (step_NN_*.json/.png + steps.json)
    :param locators_mode: лестница кандидатов ветки ("css" | "role")
    :param scope_css: css-селектор контейнера (как --scope одиночного дампа)
    :param input_fn: источник ввода (подменяется в смоуке без браузера)
    :return: список шагов (то же, что уходит в steps.json)
    """
    os.makedirs(out_dir, exist_ok=True)
    print(
        "Проход сценария начат — браузерное окно открыто, сессия одна на "
        "весь проход.\n"
        "Доведи страницу руками до НАЧАЛА сценария (логин — тоже руками), "
        "затем по циклу:\n"
        "  1) сделай очередной шаг в браузере;\n"
        "  2) вернись сюда, введи короткое имя шага (например: "
        "otkryl_formu) и нажми Enter — сниму дамп DOM и скриншот.\n"
        "     Пустой Enter — тоже снимет (имя будет step_NN).\n"
        "Когда сценарий пройден — введи q и Enter.",
        file=sys.stderr,
    )
    steps = []
    while True:
        try:
            line = input_fn()
        except EOFError:
            break
        if line.strip().lower() in ('q', 'quit', 'exit'):
            break

        number = len(steps) + 1
        suffix = _sanitize_step_name(line)
        base = f"step_{number:02d}" + (f"_{suffix}" if suffix else "")

        try:
            elements = dump_page(driver, scope_css, locators_mode)
            step_dump = {
                "url": driver.current_url,
                "title": driver.title,
                "elements": elements,
                "summary": _summary(elements),
            }
        except Exception as e:
            print(f"Дамп шага не снялся: {e} — дождись загрузки страницы "
                  f"и нажми Enter ещё раз.", file=sys.stderr)
            continue
        with open(os.path.join(out_dir, base + '.json'), 'w',
                  encoding='utf-8') as f:
            json.dump(step_dump, f, ensure_ascii=False, indent=2)

        screenshot = None
        try:
            png = driver.get_screenshot_as_png()
            screenshot = base + '.png'
            with open(os.path.join(out_dir, screenshot), 'wb') as f:
                f.write(png)
        except Exception as e:
            print(f"Скриншот шага {number} не снялся (не страшно): {e}",
                  file=sys.stderr)

        steps.append({
            "step": number,
            "name": line.strip() or base,
            "dump": base + '.json',
            "screenshot": screenshot,
            "url": step_dump["url"],
            "title": step_dump["title"],
            "count": step_dump["summary"]["total"],
            "fragile": step_dump["summary"]["fragile"],
        })
        with open(os.path.join(out_dir, 'steps.json'), 'w',
                  encoding='utf-8') as f:
            json.dump(steps, f, ensure_ascii=False, indent=2)
        print(f"Шаг {number} снят: {base}.json "
              f"({step_dump['summary']['total']} элементов, "
              f"{step_dump['summary']['fragile']} хрупких). "
              f"Следующий шаг или q.", file=sys.stderr)

    with open(os.path.join(out_dir, 'steps.json'), 'w', encoding='utf-8') as f:
        json.dump(steps, f, ensure_ascii=False, indent=2)
    print(f"Готово: {len(steps)} шагов в {out_dir} (+ steps.json). "
          f"Отдай агенту папку целиком.", file=sys.stderr)
    return steps


def main():
    parser = argparse.ArgumentParser(
        description="Дамп интерактивных элементов страницы (JSON в stdout). "
                    "Режимы: один снимок (дефолт) или --walkthrough — проход "
                    "сценария (одна не-headless сессия, дамп+скриншот на "
                    "каждый шаг человека)."
    )
    parser.add_argument(
        "--url",
        help="http(s)://, file:// или путь к html-файлу (резолвится от cwd); "
             "в --walkthrough — необязательная стартовая страница",
    )
    parser.add_argument(
        "--walkthrough", metavar="DIR",
        help="проход сценария: одна живая не-headless сессия, на каждый шаг "
             "человека (Enter в терминале) дамп+скриншот в DIR + steps.json",
    )
    parser.add_argument(
        "--scope", help="css-селектор контейнера: искать только внутри него"
    )
    parser.add_argument(
        "--locators", choices=("css", "role"), default="css",
        help="лестница кандидатов: css — selenium-ветка (дефолт), "
             "role — playwright-ветка (get_by_role/label/testid)",
    )
    parser.add_argument(
        "--wait", type=float, default=2,
        help="секунд подождать после загрузки страницы (дефолт 2)",
    )
    parser.add_argument("--out", help="файл для JSON вместо stdout")
    args = parser.parse_args()

    if not args.walkthrough and not args.url:
        parser.error("--url обязателен в режиме одного снимка")
    if args.walkthrough and args.out:
        parser.error("--out — только для режима одного снимка "
                     "(в --walkthrough файлы шагов пишутся в DIR сами)")

    if args.walkthrough:
        # Проходом управляет человек — окно браузера обязано быть видимым
        os.environ["HEADLESS"] = "false"
        driver = get_driver()
        try:
            if args.url:
                driver.get(resolve_url(args.url))
                time.sleep(args.wait)
            steps = run_walkthrough(driver, args.walkthrough,
                                    args.locators, args.scope)
        finally:
            driver.quit()
        result = {
            "mode": "walkthrough",
            "dir": args.walkthrough,
            "steps": steps,
            "summary": {
                "total": sum(s["count"] for s in steps),
                "fragile": sum(s["fragile"] for s in steps),
            },
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    url = resolve_url(args.url)
    driver = get_driver()
    try:
        driver.get(url)
        time.sleep(args.wait)
        elements = dump_page(driver, args.scope, args.locators)
        title = driver.title
    finally:
        driver.quit()

    result = {
        "url": url,
        "title": title,
        "elements": elements,
        "summary": _summary(elements),
    }
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(output + os.linesep)
        print(f"Дамп сохранён: {args.out} "
              f"(элементов: {result['summary']['total']})")
    else:
        print(output)


if __name__ == "__main__":
    main()
