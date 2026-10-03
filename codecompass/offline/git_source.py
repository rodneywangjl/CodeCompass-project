"""Git repository adapter: HEAD, diffs, and blob reads from the object database."""

from __future__ import annotations

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
