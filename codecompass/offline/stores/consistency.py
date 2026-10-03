"""Two-index consistency check (AC-4.3, AC-4.5)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ConsistencyResult:
    ok: bool
    only_in_vector: dict = field(default_factory=dict)  # id -> path
    only_in_keyword: dict = field(default_factory=dict)  # id -> path
    path_disagreements: dict = field(default_factory=dict)  # path -> (vec ids, kw ids)


def check_consistency(vector, keyword) -> ConsistencyResult:
    """Compare chunk id sets and per-path agreement between the two stores."""
    vec_ids = vector.ids()
    kw_ids = keyword.ids()
    only_v = {cid: p for cid, p in vector.paths_for_ids(vec_ids - kw_ids).items()}
    only_k = {cid: p for cid, p in keyword.paths_for_ids(kw_ids - vec_ids).items()}
    disagreements: dict = {}
    if only_v or only_k:
        vec_paths = vector.paths_for_ids(vec_ids)
        kw_paths: dict[str, set] = {}
        for cid, path in keyword.paths_for_ids(kw_ids).items():
            kw_paths.setdefault(path, set()).add(cid)
        vec_by_path: dict[str, set] = {}
        for cid, path in vec_paths.items():
            vec_by_path.setdefault(path, set()).add(cid)
        for path in set(vec_by_path) | set(kw_paths):
            if vec_by_path.get(path, set()) != kw_paths.get(path, set()):
                disagreements[path] = (
                    sorted(vec_by_path.get(path, set())),
                    sorted(kw_paths.get(path, set())),
                )
    return ConsistencyResult(
        ok=not only_v and not only_k,
        only_in_vector=only_v,
        only_in_keyword=only_k,
        path_disagreements=disagreements,
    )
