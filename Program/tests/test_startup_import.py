"""The app starts: `python -m adventure` imports adventure.main first, in a fresh interpreter, so an import cycle that
the test run's own import order hides still fails here (a cycle through adventure/gm.py once kept main from starting)."""
import subprocess
import sys
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]


def test_the_app_imports_in_a_fresh_interpreter():
    ran = subprocess.run([sys.executable, '-c', 'import adventure.main'], cwd=PROGRAM, capture_output=True, text=True,
                         timeout=120)
    assert ran.returncode == 0, ran.stderr[-2000:]
