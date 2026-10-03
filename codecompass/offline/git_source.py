"""Git repository adapter: HEAD, diffs, and blob reads from the object database."""

from __future__ import annotations

from pathlib import Path

from git import InvalidGitRepositoryError, Repo


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
