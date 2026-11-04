"""Question-set check: format and references at the pinned commit (Spec 003 T1.1).

Usage: python -m codecompass.eval.questions FILE [FILE ...] --repo PATH

Every row must have the agreed fields, allowed values and non-empty text, and every
ground-truth range and citation must exist at the row's ``repo_commit`` (Plan 003 §1).
Files are read from git at that commit, never from the working tree.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

FIELDS = ["id", "set", "category", "complexity", "question", "reference_answer",
          "reference_citations", "ground_truth_files", "source", "ai_assisted",
          "repo_commit", "original_id"]
SETS = {"core", "swe-qa", "fastapi-heldout"}
SOURCES = {"hand-written", "swe-qa"}
CATEGORIES = {"architectural", "runtime-behaviour", "design-rationale", "localisation",
              "unanswerable"}
COMPLEXITIES = {"simple", "code-tracing"}
_FULL_SHA = re.compile(r"[0-9a-f]{40}")
_LINE_RANGE = re.compile(r"(\d+)-(\d+)")


def load_question_set(path) -> list[dict]:
    """Read a JSONL question file; blank lines are skipped."""
    rows = []
    with open(path, encoding="utf-8") as fh:
        for number, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}: line {number} is not valid JSON ({e.msg})") from None
    return rows


class _Repo:
    """Read-only git queries, cached, never touching the working tree."""

    def __init__(self, path):
        self.path = str(path)
        self._counts: dict[tuple[str, str], int | None] = {}

    def _git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", self.path, *args], capture_output=True)

    def is_repository(self) -> bool:
        try:
            return self._git("rev-parse", "--git-dir").returncode == 0
        except OSError:
            return False

    def has_commit(self, sha: str) -> bool:
        return self._git("cat-file", "-e", f"{sha}^{{commit}}").returncode == 0

    def line_count(self, commit: str, path: str) -> int | None:
        key = (commit, path)
        if key not in self._counts:
            r = self._git("show", f"{commit}:{path}")
            text = r.stdout.decode("utf-8", errors="replace") if r.returncode == 0 else None
            self._counts[key] = None if text is None else len(text.splitlines())
        return self._counts[key]

    def is_ancestor(self, older: str, newer: str) -> bool:
        return (self.has_commit(older)
                and self._git("merge-base", "--is-ancestor", older, newer).returncode == 0)


def _range_problem(repo: _Repo, commit: str, path: str, start, end, what: str) -> str | None:
    if not (isinstance(start, int) and isinstance(end, int)
            and not isinstance(start, bool) and not isinstance(end, bool)):
        return f"{what} {path}: line numbers must be integers"
    count = repo.line_count(commit, path)
    if count is None:
        return f"{what} {path} does not exist at {commit[:7]}"
    if not 1 <= start <= end <= count:
        return f"{what} {path} lines {start}-{end} are outside the file ({count} lines at {commit[:7]})"
    return None


def _check_row(row, repo: _Repo, seen_ids: set) -> list[str]:
    if not isinstance(row, dict) or list(row) != FIELDS:
        got = list(row) if isinstance(row, dict) else type(row).__name__
        return [f"fields must be exactly {FIELDS} in that order, got {got}"]
    out = []
    if row["id"] in seen_ids:
        out.append("duplicate id")
    seen_ids.add(row["id"])
    for field, allowed in (("set", SETS), ("source", SOURCES), ("category", CATEGORIES),
                           ("complexity", COMPLEXITIES)):
        if row[field] not in allowed:
            out.append(f"{field} {row[field]!r} is not one of {sorted(allowed)}")
    for field in ("question", "reference_answer"):
        if not isinstance(row[field], str) or not row[field].strip():
            out.append(f"{field} is empty")
    if not isinstance(row["ai_assisted"], bool):
        out.append("ai_assisted must be true or false")
    original = row["original_id"]
    if row["source"] == "hand-written" and original is not None:
        out.append("original_id must be null for a hand-written question")
    if row["source"] == "swe-qa" and not (isinstance(original, int) and not isinstance(original, bool)
                                          and original > 0):
        out.append("original_id must be a positive integer for a SWE-QA question")

    commit = row["repo_commit"]
    if not (isinstance(commit, str) and _FULL_SHA.fullmatch(commit)):
        out.append(f"repo_commit {commit!r} must be the full 40-character commit SHA")
        return out
    if not repo.has_commit(commit):
        out.append(f"repo_commit {commit} is not in this git repository ({repo.path}); "
                   "is --repo the right repository?")
        return out

    truth = row["ground_truth_files"]
    if not isinstance(truth, list):
        out.append("ground_truth_files must be a list")
        truth = []
    if row["category"] == "unanswerable" and truth:
        out.append("an unanswerable question must have no ground truth")
    if row["category"] != "unanswerable" and not truth:
        out.append("an answerable question needs ground truth")
    for entry in truth:
        if not isinstance(entry, dict) or set(entry) != {"path", "start_line", "end_line"}:
            out.append(f"ground truth entry {entry!r} must have path, start_line and end_line")
            continue
        if not str(entry["path"]).endswith(".py"):
            out.append(f"ground truth {entry['path']} is not a .py file (only code is indexed)")
            continue
        problem = _range_problem(repo, commit, entry["path"], entry["start_line"],
                                 entry["end_line"], "ground truth")
        if problem:
            out.append(problem)

    citations = row["reference_citations"]
    if not isinstance(citations, list):
        out.append("reference_citations must be a list")
        citations = []
    for cite in citations:
        if isinstance(cite, dict) and set(cite) == {"commit"}:
            if not (isinstance(cite["commit"], str) and repo.is_ancestor(cite["commit"], commit)):
                out.append(f"cited commit {cite['commit']!r} is not in the history of {commit[:7]}")
        elif isinstance(cite, dict) and set(cite) == {"path", "lines"}:
            m = _LINE_RANGE.fullmatch(str(cite["lines"]))
            if not m:
                out.append(f"citation {cite['path']} lines {cite['lines']!r} must look like '12-34'")
                continue
            problem = _range_problem(repo, commit, cite["path"], int(m.group(1)),
                                     int(m.group(2)), "citation")
            if problem:
                out.append(problem)
        else:
            out.append(f"citation {cite!r} must be {{path, lines}} or {{commit}}")
    return out


def check_question_set(rows, repo_path) -> list[str]:
    """Return one problem per broken rule, each starting with the question id.

    Raises ValueError if *repo_path* is not a git repository at all.
    """
    repo = _Repo(repo_path)
    if not repo.is_repository():
        raise ValueError(f"{repo_path} is not a git repository")
    seen: set = set()
    problems = []
    for number, row in enumerate(rows, 1):
        qid = row.get("id") if isinstance(row, dict) else None
        label = qid if isinstance(qid, str) and qid else f"row {number}"
        problems += [f"{label}: {p}" for p in _check_row(row, repo, seen)]
    return problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m codecompass.eval.questions",
                                     description="Check evaluation question files (Spec 003 T1.1).")
    parser.add_argument("files", nargs="+", type=Path, help="JSONL question files, checked as one set")
    parser.add_argument("--repo", required=True, type=Path, help="git checkout of the repository under test")
    args = parser.parse_args(argv)
    try:
        rows = [row for path in args.files for row in load_question_set(path)]
    except (OSError, ValueError) as e:
        print(f"error: {e}")
        return 1
    try:
        problems = check_question_set(rows, args.repo)
    except ValueError as e:
        print(f"error: --repo {e}")
        return 1
    for p in problems:
        print(p)
    print(f"{len(rows)} questions checked, {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
