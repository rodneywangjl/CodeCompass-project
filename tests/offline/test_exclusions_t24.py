"""T2.4 cheap-first decision pipeline tests (tests-first)."""

from codecompass.offline.config import FilesConfig
from codecompass.offline.exclusions import classify_all, decide_for_source
from codecompass.offline.git_source import GitSource
from tests.support.fixture_repo import build_fixture_repo


class SpySource:
    def __init__(self, real):
        self.real = real
        self.sizes = 0
        self.reads = 0

    def blob_size(self, sha, path):
        self.sizes += 1
        return self.real.blob_size(sha, path)

    def read_blob(self, sha, path):
        self.reads += 1
        return self.real.read_blob(sha, path)


def test_excluded_path_reads_nothing(tmp_path):
    fx = build_fixture_repo(tmp_path / "repo")
    src = GitSource(fx.path)
    spy = SpySource(src)
    d = decide_for_source(".env", FilesConfig(), spy, src.head_sha())
    assert not d.included
    assert (spy.sizes, spy.reads) == (0, 0)


def test_oversize_path_reads_no_content(tmp_path):
    fx = build_fixture_repo(tmp_path / "repo")
    src = GitSource(fx.path)
    spy = SpySource(src)
    cfg = FilesConfig(max_file_bytes=10)
    d = decide_for_source("src/main.py", cfg, spy, src.head_sha())
    assert d.reason == "too-large"
    assert spy.reads == 0 and spy.sizes >= 1


def test_counts_by_rule(tmp_path):
    fx = build_fixture_repo(tmp_path / "repo")
    src = GitSource(fx.path)
    paths = ["src/main.py", ".env", "README.md", "image.bin"]
    _, counts = classify_all(paths, FilesConfig(), src, src.head_sha())
    assert counts["include"] == 1
    assert counts["non-code"] == 1
    assert counts["binary"] == 1
    assert sum(counts.values()) == 4
