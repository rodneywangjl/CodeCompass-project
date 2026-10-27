"""Command-line entry point: python -m codecompass.online.cli ask REPO QUESTION."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from codecompass.online import ask
from codecompass.online.config import load_online_config
from codecompass.online.generator.profiles import resolve_profile


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m codecompass.online.cli",
                                     description="Ask CodeCompass about a git repository.")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("ask", help="answer a question with checked citations")
    p.add_argument("repo", help="path to the git repository")
    p.add_argument("question", help="the question, in quotes")
    p.add_argument("--profile", help="generator profile (default: GENERATOR_PROFILE or dev)")
    p.add_argument("--config", help="codecompass.toml (default: ./codecompass.toml if present)")
    p.add_argument("--index-dir", help="override the index directory")
    p.add_argument("--verbose", action="store_true",
                   help="print retrieved chunks and tool calls to stderr")
    return parser


def _details(log: dict) -> str:
    lines = ["retrieved:"]
    for c in log["retrieved"]:
        mark = "sent" if c["sent"] else "dropped"
        lines.append(f"  {c['path']} lines {c['lines']}  rrf={c['rrf_score']:.4f}  "
                     f"rerank={c['rerank_score']:.3f}  {mark}")
    lines.append(f"tool calls: {sum('tool' in r for r in log['tool_calls'])}")
    for r in log["tool_calls"]:
        if "tool" in r:
            hit = "cache hit" if r["cache_hit"] else "run"
            lines.append(f"  round {r['round']}: {r['tool']}({r['args']})  {hit}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config_path = args.config or ("codecompass.toml" if Path("codecompass.toml").exists()
                                  else None)
    try:
        config = load_online_config(config_path)
        name, profile = resolve_profile(config, args.profile)
        print(f"codecompass: profile {name} ({profile.model_id})", file=sys.stderr)
        result = ask(args.repo, args.question, config=config, profile=name,
                     index_dir=args.index_dir)
    except Exception as exc:  # noqa: BLE001 (a CLI reports, it does not trace back)
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(result.answer)
    if args.verbose:
        print(_details(result.audit_log), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
