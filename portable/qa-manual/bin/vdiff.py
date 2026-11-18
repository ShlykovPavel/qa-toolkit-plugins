#!/usr/bin/env python3
"""vdiff.py — сравнить два скриншота и сказать, изменилось ли что-то заметное.

Нужен в двух местах прогона:

  * перепроверка находки — сняли до и после фикса, хотим знать, поменялось ли вообще;
  * регресс — эталон прошлого прогона против сегодняшнего кадра той же страницы.

Глазами сравнивать два тёмных скриншота бесполезно: сдвиг на пару пикселей не виден,
а подмена шрифта — видна, но не описывается словами. Скрипт считает долю изменившихся
пикселей и показывает, где именно, чтобы решение принималось по числу и координатам.

    python3 vdiff.py before.png after.png [--out diff.png] [--threshold 12]

  --threshold  насколько сильно должен отличаться пиксель (0-255), чтобы считаться
               изменившимся; 12 отсекает шум сглаживания шрифтов и градиентов
  --out        куда сохранить карту различий (изменения подсвечены красным)

Печатает JSON: доля изменившихся пикселей, прямоугольник изменений, вердикт.
Разные размеры картинок — это само по себе ответ: высота страницы поехала.

Нужен Pillow: python3 -m pip install pillow
"""

import argparse
import json
import sys

try:
    from PIL import Image, ImageChops
except ImportError:
    print(json.dumps({"error": "нужен Pillow: python3 -m pip install pillow"}, ensure_ascii=False))
    sys.exit(1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--out", default=None)
    ap.add_argument("--threshold", type=int, default=12)
    args = ap.parse_args()

    a = Image.open(args.before).convert("RGB")
    b = Image.open(args.after).convert("RGB")

    if a.size != b.size:
        print(json.dumps({
            "verdict": "размеры не совпадают",
            "before": list(a.size),
            "after": list(b.size),
            "note": "разная высота страницы — контента стало больше или меньше, "
                    "это уже изменение; для попиксельного сравнения пересними одним viewport",
        }, ensure_ascii=False, indent=1))
        return 0

    # Карта различий по яркости: устойчивее к субпиксельному сглаживанию, чем поканальная.
    diff = ImageChops.difference(a, b).convert("L")
    mask = diff.point(lambda p: 255 if p > args.threshold else 0)
    changed = sum(mask.histogram()[255:])
    total = a.size[0] * a.size[1]
    ratio = changed / total if total else 0.0
    box = mask.getbbox()

    if ratio == 0:
        verdict = "идентичны"
    elif ratio < 0.001:
        verdict = "почти идентичны — вероятно, шум рендеринга"
    elif ratio < 0.02:
        verdict = "локальное изменение"
    else:
        verdict = "существенное изменение"

    if args.out and box:
        red = Image.new("RGB", a.size, (255, 0, 0))
        vis = b.copy()
        vis.paste(red, mask=mask)
        vis.save(args.out)

    print(json.dumps({
        "verdict": verdict,
        "changedRatio": round(ratio, 5),
        "changedPixels": changed,
        "changedBox": list(box) if box else None,
        "size": list(a.size),
        "diffImage": args.out,
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
