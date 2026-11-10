"""Clone-to-running helper: venv + install + personal config + index + status + check + tests.

Run from the project root:
    python quickstart.py /path/to/repo                       # real code embedder (~300 MB download once)
    python quickstart.py /path/to/repo --profile dev-lowmem  # pick the generator profile for this machine
    python quickstart.py /path/to/repo --embedder stub       # smoke test only; codecompass cannot query it

The personal config (~/.config/codecompass/codecompass.toml, %APPDATA% on Windows) is
created only if it does not exist. It holds the pinned generator profiles from this
project's codecompass.toml, so codecompass works in repos that have no config of their own.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Pinned wheels (torch in particular) exist for these versions; CI runs 3.11.
SUPPORTED = ((3, 11), (3, 14))
SUPPORTED_TEXT = "Python 3.11 to 3.14"

if not SUPPORTED[0] <= sys.version_info[:2] <= SUPPORTED[1]:
    raise SystemExit(f"quickstart: {SUPPORTED_TEXT} is required, this is {sys.version.split()[0]}. "
                     "Run it with a supported one, e.g. `python3.14 quickstart.py ...`")

import tomllib  # noqa: E402 (stdlib from 3.11, checked above)

ROOT = Path(__file__).resolve().parent
PROJECT_CONFIG = ROOT / "codecompass.toml"

# Run inside the venv so the path and the parsing are exactly what codecompass uses.
USER_CONFIG_PATH_PY = ("from codecompass.online.tui import CONFIG_NAME, _user_config_dir; "
                       "print(_user_config_dir() / 'codecompass' / CONFIG_NAME)")
VALIDATE_CONFIG_PY = """\
import sys
from pathlib import Path
from codecompass.online.config import load_online_config_layers
config = load_online_config_layers([Path(sys.argv[1])])
name = config.generator.default_profile
if name not in config.generator.profiles:
    raise SystemExit(f"default_profile {name!r} is not defined in {sys.argv[1]}")
profile = config.generator.profiles[name]
print(f"profile {name}: {profile.model_id}, {profile.gguf_file or 'no GGUF pinned'}, "
      f"context {profile.context_window}")
"""


def venv_python() -> Path:
    if sys.platform == "win32":
        return ROOT / ".venv" / "Scripts" / "python.exe"
    return ROOT / ".venv" / "bin" / "python"


def run(cmd: list[str]) -> None:
    print(f"+ {' '.join(cmd)}", flush=True)
    if subprocess.run(cmd, cwd=ROOT).returncode != 0:
        raise SystemExit(f"quickstart: step failed: {' '.join(cmd)}")


def capture(cmd: list[str], what: str) -> str:
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        detail = (result.stderr.strip().splitlines() or ["(no output)"])[-1]
        raise SystemExit(f"quickstart: {what} failed: {detail}")
    return result.stdout.strip()


def project_profiles() -> dict:
    with PROJECT_CONFIG.open("rb") as f:
        return tomllib.load(f).get("generator", {}).get("profiles", {})


def toml_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)  # a JSON string is a valid TOML basic string
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(v) for v in value) + "]"
    raise TypeError(f"unsupported value in {PROJECT_CONFIG.name}: {value!r}")


def user_config_text(profile: str, profiles: dict) -> str:
    lines = ["# Personal CodeCompass settings, written by quickstart.py.",
             f"# Profiles copied from {PROJECT_CONFIG}. A repo's own codecompass.toml is",
             "# layered on top and wins. Edit freely: quickstart never overwrites this file.",
             "# GPU settings ([reranker], [embedder] device/dtype) are manual: see README §7.",
             "",
             "[generator]",
             f"default_profile = {toml_value(profile)}"]
    for name, values in profiles.items():
        lines += ["", f"[generator.profiles.{toml_value(name)}]"]
        lines += [f"{key} = {toml_value(value)}" for key, value in values.items()]
    return "\n".join(lines) + "\n"


def ensure_user_config(vpy: Path, profile: str | None, profiles: dict) -> Path:
    path = Path(capture([str(vpy), "-c", USER_CONFIG_PATH_PY], "locating the personal config"))
    validate = [str(vpy), "-c", VALIDATE_CONFIG_PY]
    if path.exists():
        print(f"Personal config exists, left unchanged: {path}", flush=True)
        print(capture(validate + [str(path)], f"checking {path}"), flush=True)
        if profile is not None:
            print(f"--profile {profile} ignored: edit default_profile there, or run "
                  f"`codecompass --profile {profile}`", flush=True)
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(user_config_text(profile or "dev", profiles), encoding="utf-8")
    try:
        summary = capture(validate + [str(tmp)], "checking the new personal config")  # before it goes live
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
    print(f"Wrote personal config: {path}\n{summary}", flush=True)
    return path


def next_steps(repo: Path, embedder: str, user_config: Path) -> str:
    if embedder == "stub":
        return ("\nIndexed with the stub embedder: a smoke test only. codecompass refuses to "
                "query this index (embedder mismatch, Article II.4).\n"
                f"Re-run without --embedder stub to build a queryable index:\n"
                f"  python quickstart.py {repo}\n")
    command = ".venv\\Scripts\\codecompass" if sys.platform == "win32" else ".venv/bin/codecompass"
    return ("\nIndex ready. To ask questions:\n"
            f"  1. Download the GGUF named by your profile ({user_config}) and start\n"
            "     llama-server (MODEL-SETUP.md). codecompass prints the exact start\n"
            "     command if the server is not running.\n"
            f"  2. {ROOT / command} {repo}\n"
            "     (or activate .venv, cd into the repo and run `codecompass`)\n")


def main(argv=None) -> int:
    profiles = project_profiles()
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("repo", help="path to the git repository to index")
    p.add_argument("--embedder", default="code", choices=("code", "stub"),
                   help="code: pinned real model, queryable by codecompass (default); "
                        "stub: model-free smoke test, not queryable")
    p.add_argument("--profile", default=None, choices=sorted(profiles),
                   help="default generator profile for a new personal config (default: dev; "
                        "dev-lowmem for 16 GB machines). Ignored if the file already exists.")
    p.add_argument("--skip-install", action="store_true")
    p.add_argument("--skip-tests", action="store_true")
    args = p.parse_args(argv)
    # Commands run from the project root, so a path relative to the caller's cwd must be resolved first.
    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        raise SystemExit(f"quickstart: not a directory: {repo}")

    vpy = venv_python()
    if not vpy.exists():
        run([sys.executable, "-m", "venv", ".venv"])
        vpy = venv_python()
    venv_version = tuple(json.loads(capture(
        [str(vpy), "-c", "import json, sys; print(json.dumps(sys.version_info[:2]))"],
        "checking .venv")))
    if not SUPPORTED[0] <= venv_version <= SUPPORTED[1]:
        raise SystemExit(f"quickstart: .venv uses Python {venv_version[0]}.{venv_version[1]}; "
                         f"{SUPPORTED_TEXT} is required. Delete {ROOT / '.venv'} and run again.")

    if not args.skip_install:
        run([str(vpy), "-m", "pip", "install", "-r", "requirements.txt"])
        run([str(vpy), "-m", "pip", "install", "-e", "."])  # installs the `codecompass` command

    user_config = ensure_user_config(vpy, args.profile, profiles)

    run([str(vpy), "-m", "codecompass.offline.cli", "index", str(repo),
         "--embedder", args.embedder])
    run([str(vpy), "-m", "codecompass.offline.cli", "status", str(repo)])
    run([str(vpy), "-m", "codecompass.offline.cli", "check", str(repo),
         "--embedder", args.embedder])

    if not args.skip_tests:
        run([str(vpy), "-m", "pytest", "-m", "not model"])
    print(next_steps(repo, args.embedder, user_config), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
