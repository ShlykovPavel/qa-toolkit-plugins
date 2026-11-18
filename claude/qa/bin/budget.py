#!/usr/bin/env python3
"""Замер холодного старта скилла: сколько контекста агент читает до первого полезного действия.

Список обязательного чтения объявляется проектом в манифесте
<корень>/.qa/labs/<скилл>/cold-start.txt (скилл из плагина: его папку перезаписывает
обновление) или по-старому <скилл>/project/cold-start.txt — по одному пути на строку, относительно корня репозитория,
пустые строки и строки с # игнорируются. Манифеста нет — считаются только корневой CLAUDE.md
и сам SKILL.md, и об этом печатается предупреждение: неполный замер хуже отсутствующего,
если о неполноте не сказано.

Оценка токенов приблизительная и помечена как оценка: она нужна, чтобы видеть динамику,
а не чтобы спорить о втором знаке.
"""
import argparse
import sys
from pathlib import Path

CYR = set("абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ")


def est_tokens(text: str) -> int:
    """Грубая оценка: кириллица токенизируется примерно вдвое хуже латиницы."""
    if not text:
        return 0
    cyr = sum(1 for ch in text if ch in CYR)
    frac = cyr / len(text)
    chars_per_token = 3.6 - 1.4 * frac  # ~3.6 латиница, ~2.2 сплошная кириллица
    return int(len(text) / chars_per_token)


def measure(paths, repo):
    rows, missing = [], []
    for rel in paths:
        p = (repo / rel) if not Path(rel).is_absolute() else Path(rel)
        if not p.is_file():
            missing.append(rel)
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        rows.append((rel, len(text.encode("utf-8")), text.count("\n") + 1, est_tokens(text)))
    return rows, missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill", required=True, help="каталог скилла")
    ap.add_argument("--repo", required=True, help="корень репозитория")
    ap.add_argument("--ceiling", type=float, default=None, help="потолок из файла цели, КБ")
    ap.add_argument("--extra", action="append", default=[], help="добавить путь к замеру")
    args = ap.parse_args()

    skill, repo = Path(args.skill).resolve(), Path(args.repo).resolve()
    if not skill.is_dir():
        sys.exit(f"нет каталога скилла: {skill}")

    manifest = repo / ".qa" / "labs" / skill.name / "cold-start.txt"
    if not manifest.is_file():
        manifest = skill / "project" / "cold-start.txt"  # скилл в .claude/ проекта
    warn = None
    if manifest.is_file():
        paths = [ln.strip() for ln in manifest.read_text(encoding="utf-8").splitlines()
                 if ln.strip() and not ln.lstrip().startswith("#")]
    else:
        paths = [p for p in ("CLAUDE.md",) if (repo / p).is_file()]
        paths.append(str((skill / "SKILL.md").relative_to(repo)) if skill.is_relative_to(repo)
                     else str(skill / "SKILL.md"))
        warn = (f"манифест {manifest} не объявлен — замер неполный: "
                f"посчитаны только {', '.join(paths)}")
    paths += args.extra
    seen, uniq = set(), []
    for rel in paths:  # дубли дают двойной счёт и врут в итоге
        key = str((repo / rel).resolve()) if not Path(rel).is_absolute() else str(Path(rel).resolve())
        if key not in seen:
            seen.add(key)
            uniq.append(rel)
    paths = uniq

    rows, missing = measure(paths, repo)
    rows.sort(key=lambda r: -r[1])
    total_b = sum(r[1] for r in rows)
    total_t = sum(r[3] for r in rows)

    print("ОБЯЗАТЕЛЬНОЕ ЧТЕНИЕ ХОЛОДНОГО СТАРТА\n")
    print(f"{'байт':>9}  {'строк':>6}  {'~токенов':>9}  файл")
    for rel, b, ln, tk in rows:
        print(f"{b:>9}  {ln:>6}  {tk:>9}  {rel}")
    print(f"{'-' * 9}  {'-' * 6}  {'-' * 9}")
    print(f"{total_b:>9}  {'':>6}  {total_t:>9}  ИТОГО  ({total_b / 1024:.1f} КБ, оценка токенов)")

    if rows:
        rel, b, _, _ = rows[0]
        print(f"\nСамый жирный кусок: {rel} — {b / 1024:.1f} КБ, "
              f"{b * 100 // total_b} % всего чтения.")

    refs = sorted((skill / "references").glob("*.md")) if (skill / "references").is_dir() else []
    if refs:
        rb = sum(p.stat().st_size for p in refs)
        print(f"Справочники скилла ({len(refs)} шт., {rb / 1024:.1f} КБ) читаются по надобности "
              f"и в холодный старт не входят.")

    sk = skill / "SKILL.md"
    if sk.is_file():
        n = sk.read_text(encoding="utf-8").count("\n") + 1
        mark = "ок" if n <= 500 else "выше ориентира skill-creator (500)"
        print(f"SKILL.md: {n} строк — {mark}.")

    if args.ceiling is not None:
        d = total_b / 1024 - args.ceiling
        print(f"\nПотолок {args.ceiling:.0f} КБ: "
              + (f"ПРЕВЫШЕН на {d:.1f} КБ" if d > 0 else f"запас {-d:.1f} КБ"))

    if warn:
        print(f"\nВНИМАНИЕ: {warn}")
    if missing:
        print(f"ВНИМАНИЕ: не найдены и не посчитаны: {', '.join(missing)}")


if __name__ == "__main__":
    main()
