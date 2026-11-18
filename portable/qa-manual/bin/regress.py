#!/usr/bin/env python3
"""regress.py — эталонные снимки страниц и сравнение с ними после релиза.

Зачем отдельный скрипт, если есть vdiff.py: сравнить два файла руками нетрудно, а вот
держать набор эталонов по десятку страниц в трёх ширинах экрана, помнить их имена и
обновлять после осознанных правок дизайна — работа, которую нельзя делать на память.
Здесь эталоны живут в каталоге, имена выводятся из URL, а прогон отвечает на один
вопрос: что изменилось с прошлого раза и где именно.

    # снять эталоны (делается один раз на стабильной версии)
    python3 regress.py --save --urls urls.txt

    # после релиза — сравнить с эталонами
    python3 regress.py --urls urls.txt

    # обновить эталон одной страницы, если изменение оказалось намеренным
    python3 regress.py --save https://example.com/pricing

Опции:
  --urls <файл>       по одному URL в строке (пустые строки и # игнорируются)
  --dir <путь>        каталог эталонов, по умолчанию .ui-baseline
  --viewport <имя>    mobile | tablet | desktop (по умолчанию desktop); эталоны для
                      разных ширин лежат в разных подкаталогах и не смешиваются
  --threshold <0-255> чувствительность пикселя, по умолчанию 12
  --tolerance <доля>  какую долю изменившихся пикселей считать шумом, по умолчанию 0.001
  --wait <мс>         пауза после навигации перед съёмкой
  --keep-current      не удалять свежие снимки после сравнения (для разбора глазами)

Печатает JSON: по странице — вердикт, доля изменений, координаты области, путь к
карте различий. Отдельно перечисляет страницы без эталона и эталоны без страницы.

Нужны Node 20+, Chrome и Pillow (python3 -m pip install pillow).
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

try:
    from PIL import Image, ImageChops
except ImportError:
    print(json.dumps({"error": "нужен Pillow: python3 -m pip install pillow"}, ensure_ascii=False))
    sys.exit(1)

SHOT = Path(__file__).with_name("shot.mjs")


def slug(url: str) -> str:
    """Имя файла из URL: узнаваемое глазами и устойчивое между прогонами."""
    p = urlparse(url)
    path = (p.path or "/").strip("/")
    base = f"{p.netloc}_{path}" if path else p.netloc
    if p.query:
        base += "_" + p.query
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip("-")
    return (base[:110] or "index") + ".png"


def capture(url: str, out: Path, viewport: str, wait: int) -> bool:
    cmd = ["node", str(SHOT), url, str(out), "--viewport", viewport, "--wait", str(wait)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not out.exists():
        return False
    return True


def compare(before: Path, after: Path, diff_out: Path, threshold: int, tolerance: float) -> dict:
    a = Image.open(before).convert("RGB")
    b = Image.open(after).convert("RGB")

    if a.size != b.size:
        return {
            "verdict": "изменилась высота страницы",
            "before": list(a.size),
            "after": list(b.size),
            "note": "контента стало больше или меньше — это уже изменение",
        }

    diff = ImageChops.difference(a, b).convert("L")
    mask = diff.point(lambda p: 255 if p > threshold else 0)
    changed = sum(mask.histogram()[255:])
    total = a.size[0] * a.size[1]
    ratio = changed / total if total else 0.0
    box = mask.getbbox()

    if ratio <= tolerance:
        return {"verdict": "без изменений", "changedRatio": round(ratio, 5)}

    red = Image.new("RGB", a.size, (255, 0, 0))
    vis = b.copy()
    vis.paste(red, mask=mask)
    diff_out.parent.mkdir(parents=True, exist_ok=True)
    vis.save(diff_out)

    return {
        "verdict": "изменилось" if ratio < 0.02 else "изменилось существенно",
        "changedRatio": round(ratio, 5),
        "changedBox": list(box) if box else None,
        "diffImage": str(diff_out),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="*", help="URL-ы прямо в аргументах")
    ap.add_argument("--urls", dest="urls_file", default=None, help="файл со списком URL")
    ap.add_argument("--dir", default=".ui-baseline")
    ap.add_argument("--viewport", default="desktop", choices=["mobile", "tablet", "desktop"])
    ap.add_argument("--threshold", type=int, default=12)
    ap.add_argument("--tolerance", type=float, default=0.001)
    ap.add_argument("--wait", type=int, default=8000)
    ap.add_argument("--save", action="store_true", help="снять эталоны вместо сравнения")
    ap.add_argument("--keep-current", action="store_true")
    args = ap.parse_args()

    urls = list(args.urls)
    if args.urls_file:
        for line in Path(args.urls_file).read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
    if not urls:
        print(json.dumps({"error": "не задано ни одного URL"}, ensure_ascii=False))
        return 1

    base_dir = Path(args.dir) / args.viewport
    base_dir.mkdir(parents=True, exist_ok=True)

    if args.save:
        saved, failed = [], []
        for u in urls:
            target = base_dir / slug(u)
            (saved if capture(u, target, args.viewport, args.wait) else failed).append(u)
        print(json.dumps({
            "mode": "эталоны сняты",
            "viewport": args.viewport,
            "dir": str(base_dir),
            "saved": len(saved),
            "failed": failed,
            "note": "обновляй эталон каждый раз, когда изменение оказалось намеренным — "
                    "иначе следующий прогон будет показывать одно и то же расхождение",
        }, ensure_ascii=False, indent=1))
        return 0

    current_dir = base_dir / "_current"
    current_dir.mkdir(parents=True, exist_ok=True)
    results, missing = [], []

    for u in urls:
        name = slug(u)
        baseline = base_dir / name
        if not baseline.exists():
            missing.append(u)
            continue
        cur = current_dir / name
        if not capture(u, cur, args.viewport, args.wait):
            results.append({"url": u, "verdict": "страница не открылась"})
            continue
        r = compare(baseline, cur, base_dir / "_diff" / name, args.threshold, args.tolerance)
        results.append({"url": u, **r})

    known = {slug(u) for u in urls}
    orphans = [p.name for p in base_dir.glob("*.png") if p.name not in known]

    changed = [r for r in results if r.get("verdict", "").startswith("изменил")]
    report = {
        "mode": "сравнение с эталонами",
        "viewport": args.viewport,
        "checked": len(results),
        "changed": len(changed),
        "results": results,
    }
    if missing:
        report["noBaseline"] = {"urls": missing, "note": "сначала прогони с --save"}
    if orphans:
        report["staleBaselines"] = {"files": orphans, "note": "эталоны страниц, которых нет в списке"}

    print(json.dumps(report, ensure_ascii=False, indent=1))

    if not args.keep_current:
        shutil.rmtree(current_dir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
