"""Hit rate@k for retrieval ablations (Spec 003 AC-4.1, AC-4.4, AC-4.5; Plan 003 §2.1).

A ranked list is chunks in rank order, each {"path", "start_line", "end_line", "score"}.
k counts chunks, not files; k = "all" means the whole list (the "sent" figure).
"""

from __future__ import annotations

GROUPS = ("set", "category", "complexity")


def _top(ranked: list[dict], k) -> list[dict]:
    return list(ranked) if k == "all" else list(ranked)[:k]


def file_hit(ranked: list[dict], truth: list[dict], k) -> bool:
    """A ground-truth file is among the first k chunks (AC-4.4 headline)."""
    paths = {t["path"] for t in truth}
    return any(c["path"] in paths for c in _top(ranked, k))


def line_hit(ranked: list[dict], truth: list[dict], k) -> bool:
    """A chunk in the first k has a ground-truth path and overlapping lines (AC-4.4)."""
    return any(c["path"] == t["path"]
               and c["start_line"] <= t["end_line"] and t["start_line"] <= c["end_line"]
               for c in _top(ranked, k) for t in truth)


def _stats(scored: list[tuple[bool, bool, bool]]) -> dict:
    """scored: (file hit, line hit, counts for lines) per counted question."""
    n = len(scored)
    file_hits = sum(f for f, _, _ in scored)
    line_n = sum(counts for _, _, counts in scored)
    line_hits = sum(line for _, line, counts in scored if counts)
    return {"n": n, "file_hits": file_hits, "file_rate": file_hits / n if n else None,
            "line_n": line_n, "line_hits": line_hits,
            "line_rate": line_hits / line_n if line_n else None}


def hit_rates(rows: list[dict], ks: dict) -> dict:
    """Rates per setup and k, overall and by set, category and complexity (AC-4.5).

    Questions without ground truth are left out of n and listed in "excluded"
    (AC-4.1). A whole_file question counts for the file figures only, since any
    chunk of that file would overlap it. A group with n = 0 has rates None.
    """
    counted = [r for r in rows if r["ground_truth_files"]]
    excluded = [r["id"] for r in rows if not r["ground_truth_files"]]
    setups: dict = {}
    for setup, k_values in ks.items():
        setups[setup] = {}
        for k in k_values:
            scored = {}
            for r in counted:
                ranked = r["ranked"].get(setup, [])
                truth = r["ground_truth_files"]
                scored[r["id"]] = (file_hit(ranked, truth, k), line_hit(ranked, truth, k),
                                   not r.get("whole_file", False))
            groups = {"overall": _stats(list(scored.values()))}
            for field in GROUPS:
                values = sorted({r[field] for r in rows})
                groups[field] = {v: _stats([scored[r["id"]] for r in counted if r[field] == v])
                                 for v in values}
            setups[setup][k] = groups
    return {"excluded": excluded, "setups": setups}
