#!/usr/bin/env python3
"""Start llama-server for a CodeCompass generator profile.

    python run.py 7b                 # profile dev-7b
    python run.py 14b                # profile dev (32768 context)
    python run.py 14b-lowmem         # profile dev-lowmem (8192 context)
    python run.py dev-7b             # any profile name from codecompass.toml
    python run.py 7b -ngl 99         # extra args go straight to llama-server

The GGUF file, context window and port come from codecompass.toml, so the
server always matches the profile. Binds to 127.0.0.1 only (Article VIII.2).
Models are looked up in ~/.cache/codecompass/models (override: MODELS_DIR).
"""

from __future__ import annotations

import os
import shutil
import sys
import tomllib
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
ALIASES = {"7b": "dev-7b", "14b": "dev", "14b-lowmem": "dev-lowmem", "32b": "prod"}
MODELS_DIR = Path(os.environ.get("MODELS_DIR", "~/.cache/codecompass/models")).expanduser()


def main(argv: list[str]) -> int:
    with open(ROOT / "codecompass.toml", "rb") as f:
        gen = tomllib.load(f)["generator"]
    profiles = gen["profiles"]

    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        print("Profiles:", ", ".join(profiles), "| aliases:", ", ".join(ALIASES))
        return 0 if argv else 2

    name = ALIASES.get(argv[0], argv[0])
    if name not in profiles:
        print(f"error: unknown profile {argv[0]!r}. Known: {', '.join(profiles)}", file=sys.stderr)
        return 2
    profile = profiles[name]

    gguf_file = profile.get("gguf_file")
    if not gguf_file:
        print(f"error: profile {name!r} has no gguf_file in codecompass.toml", file=sys.stderr)
        return 2
    model = MODELS_DIR / gguf_file
    if not model.is_file():
        print(f"error: model not found: {model}\n"
              f"Download it first (see MODEL-SETUP.md §1).", file=sys.stderr)
        return 1

    binary = shutil.which("llama-server")
    if not binary:
        print("error: llama-server not found on PATH (see MODEL-SETUP.md §2)", file=sys.stderr)
        return 1

    port = urlsplit(gen.get("server_url", "http://127.0.0.1:8080")).port or 8080
    cmd = [binary, "-m", str(model), "--host", "127.0.0.1", "--port", str(port),
           "-c", str(profile["context_window"]), "--jinja", *argv[1:]]

    print(f"profile: {name}  ({profile['model_id']}, context {profile['context_window']})")
    print("running:", " ".join(cmd))
    print(f"then, in another terminal:  codecompass --profile {name}\n")
    os.execv(binary, cmd)  # replace this process so Ctrl-C stops the server directly


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
