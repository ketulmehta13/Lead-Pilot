"""Execute every notebook top to bottom and save it with outputs.

    python ml/notebooks/run_notebooks.py            # all
    python ml/notebooks/run_notebooks.py churn      # just churn.ipynb

Exits non-zero if any cell fails, which is the "each notebook runs top to bottom" check.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import nbformat
from nbclient import NotebookClient

HERE = Path(__file__).resolve().parent


def run(path: Path) -> None:
    nb = nbformat.read(path, as_version=4)
    start = time.time()
    NotebookClient(
        nb,
        timeout=1800,
        startup_timeout=180,  # a cold kernel start on a busy Windows machine can take > 60 s
        kernel_name="python3",
        resources={"metadata": {"path": str(HERE)}},
    ).execute()
    nbformat.write(nb, path)
    print(f"ok  {path.name}  ({time.time() - start:.0f}s)")


def main() -> int:
    wanted = set(sys.argv[1:])
    paths = sorted(p for p in HERE.glob("*.ipynb") if not wanted or p.stem in wanted)
    failed = []
    for path in paths:
        try:
            run(path)
        except Exception as exc:  # noqa: BLE001 - report every failing notebook
            print(f"FAIL {path.name}: {type(exc).__name__}: {str(exc)[:500]}")
            failed.append(path.name)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
