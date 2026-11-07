"""T22.2 Label documentation sources tests (tests-first).

Contract under test (Spec 002 S22; Article I.1, I.2, IV.2, V.4, VI.3, VI.4):
  - In formatter.py:
    - DOCS_LABEL = " (documentation)"
    - DOCS_BANNER = ("ℹ Note: Part of this answer is based on documentation, which may be out of "
                     "date. Code is the source of truth.")
    - mark_documentation(rendered, result, doc_paths) labels Sources lines for code entries
      matching doc_paths and prepends DOCS_BANNER at the very top.
    - Commit entries and normal code paths are never labelled.
    - Body lines starting with markers (above Sources) are never labelled.
    - If no doc sources are labelled, returns rendered unchanged and [].
  - In ask() (__init__.py):
    - When docs_fallback=True, doc_paths are identified from retrieved chunks with doc_languages.
    - If any documentation source is cited, log["citation"]["documentation_sources"] records the
      sorted list of labelled markers.
    - When docs_fallback=False, no labelling or banners occur, and log is unchanged.
"""

from __future__ import annotations

import dataclasses
import subprocess
from pathlib import Path

from codecompass.online import ask
from codecompass.online.citation import formatter
from codecompass.online.config import OnlineConfig
from codecompass.online.models import CitationResult, SourceEntry
from tests.online.ask_support import CitingGenerator, config, stubs
from tests.support.stub_generator import StubGenerator
from tests.support.fixture_repo import MAIN_V1

THRESHOLD = 0.02
QUESTION = "How does hello work?"
README_TEXT = (
    "# Project Guide\n"
    "readme_marker explains how hello works.\n"
    "Third line of guide.\n"
    "Fourth line of guide.\n"
    "Fifth line of guide.\n"
)


class ChunkScoreReranker:
    """Scores doc chunks (containing readme_marker) and code chunks with chosen scores."""

    def __init__(self, *, code: float, doc: float) -> None:
        self.code, self.doc = code, doc

    def rerank(self, query, texts):
        return [self.doc if "readme_marker" in t else self.code for t in texts]


def _build_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "src").mkdir(exist_ok=True)
    (path / "src" / "app.py").write_text(MAIN_V1)
    (path / "README.md").write_text(README_TEXT)
    for args in (["init", "-q"], ["add", "-A"],
                 ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init"]):
        subprocess.run(["git", *args], cwd=path, check=True)
    return path


def _cfg(tmp_path: Path, *, min_top_score: float = THRESHOLD, **retrieval) -> OnlineConfig:
    base = config(tmp_path)
    files = dataclasses.replace(
        base.offline.files,
        source_extensions=(*base.offline.files.source_extensions, ".md"),
    )
    return dataclasses.replace(
        base,
        offline=dataclasses.replace(base.offline, files=files),
        retrieval=dataclasses.replace(
            base.retrieval, min_top_score=min_top_score, **retrieval),
    )


def _ask(tmp_path: Path, reranker, *, question: str = QUESTION, generator=None, **retrieval):
    repo = _build_repo(tmp_path / "repo")
    gen = generator or CitingGenerator()
    kw = stubs(gen)
    kw["reranker"] = reranker
    cfg = _cfg(tmp_path, **retrieval)
    result = ask(repo, question, config=cfg, index_dir=tmp_path / "idx", **kw)
    return result, gen


# 1. a verified doc source (README.md) gets DOCS_LABEL on its Sources line; DOCS_BANNER is at top
def test_verified_doc_source_gets_docs_label_and_banner_on_top():
    text = (
        "Project description [1].\n\n"
        "Sources\n"
        "[1] README.md, lines 1-5 (indexed at a1b2c3d)"
    )
    result = CitationResult(
        outcome="F",
        sources=[
            SourceEntry(kind="code", marker=1, path="README.md", start_line=1, end_line=5,
                        commit="a1b2c3d", verified=True),
        ],
        unverified=[],
        answer_text=text,
    )
    rendered = formatter.render(result)
    new_text, markers = formatter.mark_documentation(rendered, result, {"README.md"})
    assert new_text.startswith(formatter.DOCS_BANNER + "\n\n")
    assert f"[1] README.md, lines 1-5 (indexed at a1b2c3d){formatter.DOCS_LABEL}" in new_text
    assert markers == [1]


# 2. a code source in the same answer is not labelled
def test_code_source_in_same_answer_not_labelled():
    text = (
        "Overview [1] and implementation [2].\n\n"
        "Sources\n"
        "[1] README.md, lines 1-5 (indexed at a1b2c3d)\n"
        "[2] src/app.py, lines 10-20 (indexed at a1b2c3d)"
    )
    result = CitationResult(
        outcome="F",
        sources=[
            SourceEntry(kind="code", marker=1, path="README.md", start_line=1, end_line=5,
                        commit="a1b2c3d", verified=True),
            SourceEntry(kind="code", marker=2, path="src/app.py", start_line=10, end_line=20,
                        commit="a1b2c3d", verified=True),
        ],
        unverified=[],
        answer_text=text,
    )
    rendered = formatter.render(result)
    new_text, markers = formatter.mark_documentation(rendered, result, {"README.md"})
    assert f"[1] README.md, lines 1-5 (indexed at a1b2c3d){formatter.DOCS_LABEL}" in new_text
    assert f"[2] src/app.py, lines 10-20 (indexed at a1b2c3d){formatter.DOCS_LABEL}" not in new_text
    assert "[2] src/app.py, lines 10-20 (indexed at a1b2c3d)" in new_text
    assert markers == [1]


# 3. two doc sources: both labelled, DOCS_BANNER appears once; returned markers are both, sorted
def test_two_doc_sources_both_labelled_banner_once_sorted_markers():
    text = (
        "Overview [2] and guide [1].\n\n"
        "Sources\n"
        "[2] docs/guide.rst, lines 1-10 (indexed at a1b2c3d)\n"
        "[1] README.md, lines 1-5 (indexed at a1b2c3d)"
    )
    result = CitationResult(
        outcome="F",
        sources=[
            SourceEntry(kind="code", marker=2, path="docs/guide.rst", start_line=1, end_line=10,
                        commit="a1b2c3d", verified=True),
            SourceEntry(kind="code", marker=1, path="README.md", start_line=1, end_line=5,
                        commit="a1b2c3d", verified=True),
        ],
        unverified=[],
        answer_text=text,
    )
    rendered = formatter.render(result)
    new_text, markers = formatter.mark_documentation(
        rendered, result, {"README.md", "docs/guide.rst"}
    )
    assert new_text.count(formatter.DOCS_BANNER) == 1
    assert new_text.startswith(formatter.DOCS_BANNER + "\n\n")
    assert f"[2] docs/guide.rst, lines 1-10 (indexed at a1b2c3d){formatter.DOCS_LABEL}" in new_text
    assert f"[1] README.md, lines 1-5 (indexed at a1b2c3d){formatter.DOCS_LABEL}" in new_text
    assert markers == [1, 2]


# 4. no doc sources: text returned unchanged (identical string) and []
def test_no_doc_sources_returns_identical_string_and_empty_list():
    text = (
        "Code details [1].\n\n"
        "Sources\n"
        "[1] src/app.py, lines 1-10 (indexed at a1b2c3d)"
    )
    result = CitationResult(
        outcome="F",
        sources=[
            SourceEntry(kind="code", marker=1, path="src/app.py", start_line=1, end_line=10,
                        commit="a1b2c3d", verified=True),
        ],
        unverified=[],
        answer_text=text,
    )
    rendered = formatter.render(result)
    new_text, markers = formatter.mark_documentation(rendered, result, {"README.md"})
    assert new_text == rendered
    assert markers == []


# 5. an unverified doc source in a G answer: its line keeps the [UNVERIFIED] prefix AND gets
#    DOCS_LABEL; the existing WARNING banner is still present, below DOCS_BANNER
def test_unverified_doc_source_in_g_answer_keeps_unverified_and_gets_docs_label():
    text = (
        "Unverified doc claim [1].\n\n"
        "Sources\n"
        "[1] README.md, lines 1-5 (indexed at a1b2c3d)"
    )
    result = CitationResult(
        outcome="G",
        sources=[
            SourceEntry(kind="code", marker=1, path="README.md", start_line=1, end_line=5,
                        commit="a1b2c3d", verified=False),
        ],
        unverified=[1],
        answer_text=text,
    )
    rendered = formatter.render(result)
    assert formatter.BANNER in rendered
    assert "[UNVERIFIED] [1] README.md, lines 1-5 (indexed at a1b2c3d)" in rendered

    new_text, markers = formatter.mark_documentation(rendered, result, {"README.md"})
    assert new_text.startswith(formatter.DOCS_BANNER + "\n\n" + formatter.BANNER)
    expected_line = (
        f"[UNVERIFIED] [1] README.md, lines 1-5 (indexed at a1b2c3d){formatter.DOCS_LABEL}"
    )
    assert expected_line in new_text
    assert markers == [1]


# 6. commit entries are never labelled even if doc_paths is non-empty
def test_commit_entries_never_labelled_even_if_doc_paths_non_empty():
    text = (
        "According to commit [1].\n\n"
        "Sources\n"
        '[1] Commit a1b2c3d, "Update docs", Kelsey, 2026-11-08'
    )
    result = CitationResult(
        outcome="F",
        sources=[
            SourceEntry(kind="commit", marker=1, commit="a1b2c3d", subject="Update docs",
                        author="Kelsey", date="2026-11-08", verified=True),
        ],
        unverified=[],
        answer_text=text,
    )
    rendered = formatter.render(result)
    new_text, markers = formatter.mark_documentation(
        rendered, result, {"README.md", "a1b2c3d"}
    )
    assert new_text == rendered
    assert formatter.DOCS_BANNER not in new_text
    assert formatter.DOCS_LABEL not in new_text
    assert markers == []


# 7. flag on, answer cites the README chunk: result.answer starts with DOCS_BANNER,
#    the README Sources line ends with DOCS_LABEL,
#    log["citation"]["documentation_sources"] == [marker]
def test_ask_flag_on_cites_readme_gets_banner_label_and_audit_log(tmp_path):
    result, _ = _ask(
        tmp_path, ChunkScoreReranker(code=0.005, doc=0.4), docs_fallback=True,
    )
    assert result.citation_outcome == "F"
    assert len(result.sources) == 1
    assert result.sources[0].path == "README.md"
    assert result.answer.startswith(formatter.DOCS_BANNER)
    readme_marker = result.sources[0].marker
    source_lines = [
        line for line in result.answer.splitlines()
        if line.startswith(f"[{readme_marker}]")
    ]
    assert len(source_lines) == 1
    assert "README.md, lines" in source_lines[0]
    assert source_lines[0].endswith(formatter.DOCS_LABEL)
    assert result.audit_log["citation"]["documentation_sources"] == [readme_marker]


# 8. flag on, answer cites only code: answer has no DOCS_BANNER/DOCS_LABEL and log["citation"]
#    has no "documentation_sources" key
def test_ask_flag_on_cites_only_code_no_banner_no_label_no_log_key(tmp_path):
    result, _ = _ask(
        tmp_path, ChunkScoreReranker(code=0.5, doc=0.1), docs_fallback=True,
    )
    assert result.citation_outcome == "F"
    assert len(result.sources) == 1
    assert result.sources[0].path == "src/app.py"
    assert formatter.DOCS_BANNER not in result.answer
    assert formatter.DOCS_LABEL not in result.answer
    assert "documentation_sources" not in result.audit_log["citation"]


# 9. flag off with .md indexed and the answer citing README.md: answer and log are exactly as
#    without T22.2 (no label, no banner, no new log key)
def test_ask_flag_off_cites_readme_unchanged_no_banner_no_label_no_log_key(tmp_path):
    result, _ = _ask(
        tmp_path, ChunkScoreReranker(code=0.1, doc=0.5), docs_fallback=False,
    )
    assert result.citation_outcome == "F"
    assert len(result.sources) == 1
    assert result.sources[0].path == "README.md"
    assert formatter.DOCS_BANNER not in result.answer
    assert formatter.DOCS_LABEL not in result.answer
    assert "documentation_sources" not in result.audit_log["citation"]


# 10. a body line starting with marker is not labelled; only the Sources line gets DOCS_LABEL
def test_body_line_starting_with_marker_not_labelled_only_sources_line_gets_label():
    text = (
        "[1] README.md says how hello works.\n\n"
        "Sources\n"
        "[1] README.md, lines 1-5 (indexed at a1b2c3d)"
    )
    result = CitationResult(
        outcome="F",
        sources=[
            SourceEntry(kind="code", marker=1, path="README.md", start_line=1, end_line=5,
                        commit="a1b2c3d", verified=True),
        ],
        unverified=[],
        answer_text=text,
    )
    rendered = formatter.render(result)
    new_text, markers = formatter.mark_documentation(rendered, result, {"README.md"})
    assert new_text.startswith(formatter.DOCS_BANNER + "\n\n")
    assert "[1] README.md says how hello works." in new_text
    assert f"[1] README.md says how hello works.{formatter.DOCS_LABEL}" not in new_text
    assert f"[1] README.md, lines 1-5 (indexed at a1b2c3d){formatter.DOCS_LABEL}" in new_text
    assert markers == [1]

# 11. flag on, documentation opened via open_file must also be labelled
def test_ask_flag_on_labels_a_doc_opened_with_open_file(tmp_path):
    repo = _build_repo(tmp_path / "repo")
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo, text=True
    ).strip()[:7]
    base = config(tmp_path)
    cfg = dataclasses.replace(
        base,
        retrieval=dataclasses.replace(
            base.retrieval, docs_fallback=True, min_top_score=THRESHOLD
        ),
    )
    answer = f"README details [1].\n\nSources\n[1] README.md, lines 1-5 (indexed at {head})"
    gen = StubGenerator(['<tool>open_file(path="README.md", lines="1-5")</tool>', answer])
    kw = stubs(gen)
    kw["reranker"] = ChunkScoreReranker(code=0.5, doc=0.0)
    result = ask(repo, "How does hello work?", config=cfg, index_dir=tmp_path / "idx", **kw)

    assert result.citation_outcome == "F"
    assert len(result.sources) == 1
    assert result.sources[0].path == "README.md"
    assert result.answer.startswith(formatter.DOCS_BANNER)
    readme_marker = result.sources[0].marker
    source_lines = [
        line for line in result.answer.splitlines()
        if line.startswith(f"[{readme_marker}]")
    ]
    assert len(source_lines) == 1
    assert "README.md, lines" in source_lines[0]
    assert source_lines[0].endswith(formatter.DOCS_LABEL)
    assert result.audit_log["citation"]["documentation_sources"] == [readme_marker]
