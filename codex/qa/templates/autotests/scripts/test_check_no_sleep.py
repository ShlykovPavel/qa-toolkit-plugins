"""Тесты гейта scripts/check_no_sleep.py.

Гоняются ВРУЧНУЮ (в make verify не попадают — pytest testpaths=Tests):
    .venv/bin/python -m pytest scripts/test_check_no_sleep.py -q
"""
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "check_no_sleep.py"
sys.path.insert(0, str(SCRIPT.parent))

from check_no_sleep import find_blind_waits  # noqa: E402


def lines(src):
    return [line for line, _ in find_blind_waits(src)]


def test_time_sleep_found():
    assert lines("import time\n\ndef f():\n    time.sleep(2)\n") == [4]


def test_aliased_module_found():
    assert lines("import time as t\nt.sleep(1)\n") == [2]


def test_from_import_found():
    assert lines("from time import sleep\nsleep(0.3)\n") == [2]


def test_from_import_alias_found():
    assert lines("from time import sleep as pause\npause(1)\n") == [2]


def test_asyncio_sleep_found():
    assert lines("import asyncio\n\nasync def f():\n    await asyncio.sleep(1)\n") == [4]


def test_playwright_wait_for_timeout_found():
    assert lines("def test_x(page):\n    page.wait_for_timeout(500)\n") == [2]


def test_mentions_in_docstring_and_comment_pass():
    src = '"""Ждём через wait_until, `time.sleep` не используем."""\n# time.sleep(1) — нельзя\n'
    assert lines(src) == []


def test_foreign_sleep_attribute_passes():
    # .sleep у объекта, не импортированного из time/asyncio, — не наш случай
    assert lines("device.sleep(1)\n") == []


def test_wait_until_passes():
    src = "from src.wait_utils import wait_until\nwait_until(lambda: True, interval=1)\n"
    assert lines(src) == []


def test_cli_reports_file_and_line(tmp_path):
    bad = tmp_path / "Tests" / "test_bad.py"
    bad.parent.mkdir()
    bad.write_text("import time\ntime.sleep(3)\n", encoding="utf-8")
    good = tmp_path / "Tests" / "test_good.py"
    good.write_text("x = 1\n", encoding="utf-8")
    res = subprocess.run([sys.executable, str(SCRIPT), "--root", str(tmp_path)],
                         capture_output=True, text=True)
    assert res.returncode == 1
    assert "Tests/test_bad.py:2" in res.stdout
    assert "test_good" not in res.stdout


def test_cli_excluded_infra_passes(tmp_path):
    infra = tmp_path / "src" / "wait_utils.py"
    infra.parent.mkdir()
    infra.write_text("import time\ntime.sleep(1)\n", encoding="utf-8")
    res = subprocess.run([sys.executable, str(SCRIPT), "--root", str(tmp_path)],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stdout


def test_repo_is_clean():
    res = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
    assert res.returncode == 0, res.stdout
