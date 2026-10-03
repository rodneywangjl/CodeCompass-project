"""Command-line entry point: index, status, check (AC-7.x, AC-4.3)."""

from __future__ import annotations

import argparse
import shutil
import sys


def _load_config(path):
    from .config import load_config
    return load_config(path)


def _resolve_embedder(name, config):
    if name == "stub":
        # Deterministic test embedder: keeps the required suite model-free
        # (Article IX.7). Production uses "code".
        from tests.support.stub_embedder import StubEmbedder
        return StubEmbedder()
    if name == "code":
        from .embedding import CodeEmbedder
        return CodeEmbedder(config.embedder)
    raise ValueError(f"unknown embedder: {name}")


def _base(args, config):
    return args.index_dir if args.index_dir is not None else config.index.dir


def _cmd_index(args, config) -> int:
    from . import orchestrator
    from .report import to_text
    try:
        if args.dry_run:
            report = orchestrator.dry_run(
                args.repo, config=config, index_dir=_base(args, config))
            print(to_text(report), end="")
            return 0
        if args.full:
            idx = orchestrator.index_path_for(args.repo, _base(args, config))
            shutil.rmtree(idx, ignore_errors=True)
        report = orchestrator.run(
            args.repo, config=config, index_dir=_base(args, config),
            embedder=_resolve_embedder(args.embedder, config))
    except Exception as e:  # noqa: BLE001 (CLI reports, exit code signals)
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(to_text(report), end="")
    return 0


def _cmd_status(args, config) -> int:
    from . import status
    try:
        st = status(args.repo, config=config, index_dir=_base(args, config))
    except Exception as e:  # noqa: BLE001
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"state: {st.state}")
    print(f"head: {st.head_commit}")
    print(f"indexed: {st.indexed_commit}")
    if st.embedder_model:
        print(f"embedder: {st.embedder_model}@{st.embedder_revision} "
              f"dim {st.embedder_dimension} (schema {st.schema_version})")
    return 0


def _cmd_check(args, config) -> int:
    from . import check_consistency, open_index
    if getattr(args, "embedder", "code") == "stub":
        import dataclasses
        from tests.support.stub_embedder import StubEmbedder
        ident = StubEmbedder().identity
        config = dataclasses.replace(
            config, embedder=dataclasses.replace(
                config.embedder, model=ident.model, revision=ident.revision,
                dimension=ident.dimension))
    try:
        handles = open_index(args.repo, config=config,
                             index_dir=_base(args, config))
    except Exception as e:  # noqa: BLE001
        print(f"error: {e}", file=sys.stderr)
        return 1
    try:
        result = check_consistency(handles.vector, handles.keyword)
        n_chunks = len(handles.vector.ids())
    finally:
        handles.close()
    if result.ok:
        print(f"consistent: True ({n_chunks} chunks agree)")
        return 0
    print("INCONSISTENT:")
    for cid, path in sorted(result.only_in_vector.items()):
        print(f"  vector-only: {cid} ({path})")
    for cid, path in sorted(result.only_in_keyword.items()):
        print(f"  keyword-only: {cid} ({path})")
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="codecompass", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("index", "status", "check"):
        p = sub.add_parser(name)
        p.add_argument("repo")
        p.add_argument("--index-dir", default=None)
        p.add_argument("--config", default=None)
    index_p = sub.choices["index"]
    index_p.add_argument("--full", action="store_true",
                         help="rebuild from scratch")
    index_p.add_argument("--dry-run", action="store_true",
                         help="show what would change without writing")
    index_p.add_argument("--embedder", default="code", choices=("code", "stub"),
                         help="code: pinned code embedder (identity from config); stub: deterministic "
                         "test embedder (model-free)")
    check_p = sub.choices["check"]
    check_p.add_argument("--embedder", default="code", choices=("code", "stub"))
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = _load_config(args.config)
    if args.command == "index":
        return _cmd_index(args, config)
    if args.command == "status":
        return _cmd_status(args, config)
    if args.command == "check":
        return _cmd_check(args, config)
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
