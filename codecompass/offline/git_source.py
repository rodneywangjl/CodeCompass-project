"""Git repository adapter: HEAD, diffs, and blob reads from the object database."""

from __future__ import annotations

import subprocess
from pathlib import Path

from git import InvalidGitRepositoryError, Repo


from codecompass.offline.models import ChangeSet

EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


class GitSourceError(Exception):
    """Clear, user-facing git-source failure (AC-1.4, AC-1.5)."""


class GitSource:
    def __init__(self, path: str | Path) -> None:
        try:
            self._repo = Repo(path, search_parent_directories=False)
        except (InvalidGitRepositoryError, Exception) as e:
            if isinstance(e, GitSourceError):
                raise
            raise GitSourceError(f"not a git repository: {path}") from e
        try:
            self._repo.head.commit
        except Exception as e:
            raise GitSourceError(f"repository has no commits: {path}") from e
        self.path = Path(path)

    def head_sha(self) -> str:
        """Committed HEAD sha; never affected by working-tree edits."""
        return self._repo.head.commit.hexsha

    def diff(self, old: str | None, new: str) -> ChangeSet:
        """Paths added/modified/deleted between commits (renames off: delete+add)."""
        base = old if old is not None else EMPTY_TREE
        out = self._repo.git.diff("--name-status", "--no-renames", f"{base}", f"{new}", "--")
        added, modified, deleted = [], [], []
        for line in out.splitlines():
            if not line.strip():
                continue
            status, path = line.split("\t", 1)
            if status == "A":
                added.append(path)
            elif status == "M":
                modified.append(path)
            elif status == "D":
                deleted.append(path)
        return ChangeSet(added=sorted(added), modified=sorted(modified), deleted=sorted(deleted))

    def is_ancestor(self, old: str, new: str) -> bool:
        """True if *old* is reachable from *new*; False on any unresolvable sha."""
        try:
            r = subprocess.run(
                ["git", "merge-base", "--is-ancestor", old, new],
                cwd=self.path, capture_output=True,
            )
            return r.returncode == 0
        except Exception:
            return False

    def entry_kind(self, sha: str, path: str) -> str:
        """One of blob|symlink|submodule|missing, from the commit's tree."""
        out = self._repo.git.ls_tree(sha, "--", path).strip()
        if not out:
            return "missing"
        mode = out.split()[0]
        if mode == "120000":
            return "symlink"
        if mode == "160000":
            return "submodule"
        return "blob"

    def read_blob(self, sha: str, path: str) -> bytes:
        """Committed bytes for *path*; never the working tree, never follows links."""
        kind = self.entry_kind(sha, path)
        if kind != "blob":
            raise GitSourceError(f"not a readable file ({kind}): {path}")
        r = subprocess.run(
            ["git", "cat-file", "-p", f"{sha}:{path}"],
            cwd=self.path, capture_output=True, check=True,
        )
        return r.stdout

    def blob_size(self, sha: str, path: str) -> int:
        """Size from the object database without reading content."""
        if self.entry_kind(sha, path) != "blob":
            raise GitSourceError(f"not a readable file: {path}")
        return int(self._repo.git.cat_file("-s", f"{sha}:{path}"))
