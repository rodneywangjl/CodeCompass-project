"""Clone-to-running helper: venv + install + index + status + check + tests.

Run from the project root:
    python quickstart.py /path/to/repo [--embedder stub] [--skip-tests]
    python quickstart.py /path/to/repo --embedder code   # real model (~600MB download once)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def venv_python() -> Path:
    if sys.platform == "win32":
        return ROOT / ".venv" / "Scripts" / "python.exe"
    return ROOT / ".venv" / "bin" / "python"


def run(cmd: list[str]) -> None:
    print(f"+ {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("repo", help="path to the git repository to index")
    p.add_argument("--embedder", default="stub", choices=("stub", "code"),
                   help="stub: model-free (default); code: pinned real model")
    p.add_argument("--skip-install", action="store_true")
    p.add_argument("--skip-tests", action="store_true")
    args = p.parse_args(argv)

    vpy = venv_python()
    if not vpy.exists():
        run([sys.executable, "-m", "venv", ".venv"])
        vpy = venv_python()

    if not args.skip_install:
        run([str(vpy), "-m", "pip", "install", "-r", "requirements.txt"])

    index_cmd = [str(vpy), "-m", "codecompass.offline.cli", "index", args.repo,
                 "--embedder", args.embedder]
    run(index_cmd)
    run([str(vpy), "-m", "codecompass.offline.cli", "status", args.repo])
    check_cmd = [str(vpy), "-m", "codecompass.offline.cli", "check", args.repo]
    if args.embedder == "stub":
        check_cmd += ["--embedder", "stub"]
    run(check_cmd)

    if not args.skip_tests:
        run([str(vpy), "-m", "pytest", "-m", "not model"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
