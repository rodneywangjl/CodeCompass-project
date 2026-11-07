"""T22.1 docs as context fallback tests (tests-first).

Contract under test (Spec 002 S22; Article I.1, I.2, IV.2, V.4, VI.4):
  - RetrievalConfig adds docs_fallback (default False), doc_languages (default ("md", "rst")),
    and docs_margin (default 0.2), validated at startup
  - With docs_fallback=False, retrieval, prompt and audit log are unchanged
  - With docs_fallback=True, code is gated on best_code; docs join when the question asks
    about docs, when best_doc >= best_code + docs_margin, or when code fails the gate and
    best_doc passes
  - When doc chunks are sent, DOCS_NOTE precedes the code context and is counted in the
    D4 token prefix
  - Audit log records log["docs_fallback"] only when docs_fallback is True
"""

from __future__ import annotations

import dataclasses
import subprocess
from pathlib import Path

import pytest

import codecompass.online as online
from codecompass.online.agent import harness
from codecompass.online.config import OnlineConfig, RetrievalConfig, load_online_config
from tests.online.ask_support import CitingGenerator, config, stubs
from tests.support.fixture_repo import MAIN_V1

THRESHOLD = 0.02
QUESTION = "How does hello work?"
README_QUESTION = "What does the README say about hello?"
README_TEXT = "# Project Guide\nreadme_marker explains how hello works.\n"


class ChunkScoreReranker:
    """Scores doc chunks (containing readme_marker) and code chunks with chosen scores."""

    def __init__(self, *, code: float, doc: float) -> None:
        self.code, self.doc = code, doc

    def rerank(self, query, texts):
        return [self.doc if "readme_marker" in t else self.code for t in texts]


class CountingGenerator(CitingGenerator):
    """CitingGenerator that records every text it is asked to count."""

    def __init__(self) -> None:
        super().__init__()
        self.counted: list[str] = []

    def count_tokens(self, text: str) -> int:
        self.counted.append(text)
        return super().count_tokens(text)


def _build_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "src").mkdir(exist_ok=True)
    (path / "src" / "app.py").write_text(MAIN_V1)
    (path / "README.md").write_text(README_TEXT)
    for args in (["init", "-q"], ["add", "-A"],
                 ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init"]):
        subprocess.run(["git", *args], cwd=path, check=True)
    return path


def _build_code_only_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "src").mkdir(exist_ok=True)
    (path / "src" / "app.py").write_text(MAIN_V1)
    for args in (["init", "-q"], ["add", "-A"],
                 ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init"]):
        subprocess.run(["git", *args], cwd=path, check=True)
    return path


def _build_docs_only_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
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
    result = online.ask(repo, question, config=cfg, index_dir=tmp_path / "idx", **kw)
    return result, gen


def _sent_paths(result) -> set[str]:
    return {entry["path"] for entry in result.audit_log["retrieved"] if entry["sent"]}


# 1. flag off (default): chunks sent and the audit log are the same as today; no "docs_fallback" key
def test_flag_off_keeps_existing_chunks_and_audit_log(tmp_path):
    assert RetrievalConfig().docs_fallback is False
    result, gen = _ask(tmp_path, ChunkScoreReranker(code=0.5, doc=0.1))
    assert _sent_paths(result) == {"src/app.py", "README.md"}
    assert "docs_fallback" not in result.audit_log
    assert len(gen.calls) == 1


# 2. flag on, code passes, question not about docs, best_doc below best_code + margin
def test_flag_on_code_passes_below_margin_sends_only_code(tmp_path):
    result, _ = _ask(
        tmp_path, ChunkScoreReranker(code=0.5, doc=0.6), docs_fallback=True,
    )
    assert _sent_paths(result) == {"src/app.py"}
    assert result.audit_log["docs_fallback"] == {
        "used": False, "reason": None, "best_code": 0.5, "best_doc": 0.6,
    }


# 3. flag on, code passes, question mentions "README": doc chunks sent with code; DOCS_NOTE present
def test_flag_on_question_mentions_readme_sends_docs_with_note(tmp_path):
    result, gen = _ask(
        tmp_path, ChunkScoreReranker(code=0.5, doc=0.1),
        question=README_QUESTION, docs_fallback=True,
    )
    assert _sent_paths(result) == {"src/app.py", "README.md"}
    user_msg = gen.calls[0][1]["content"]
    assert harness.DOCS_NOTE in user_msg
    assert user_msg.index(harness.DOCS_NOTE) < user_msg.index("Code context:")
    assert result.audit_log["docs_fallback"] == {
        "used": True, "reason": "asked", "best_code": 0.5, "best_doc": 0.1,
    }


# 3b. flag on, question mentions README, but best_doc below min_top_score: only code sent
def test_flag_on_question_mentions_readme_but_doc_below_gate_sends_only_code(tmp_path):
    result, gen = _ask(
        tmp_path, ChunkScoreReranker(code=0.5, doc=0.005),
        question=README_QUESTION, docs_fallback=True,
    )
    assert _sent_paths(result) == {"src/app.py"}
    assert harness.DOCS_NOTE not in gen.calls[0][1]["content"]
    assert result.audit_log["docs_fallback"] == {
        "used": False, "reason": None, "best_code": 0.5, "best_doc": 0.005,
    }


# 4. flag on, code passes, best_doc >= best_code + docs_margin (question not about docs)
def test_flag_on_doc_score_beats_code_by_margin_sends_docs(tmp_path):
    result, _ = _ask(
        tmp_path, ChunkScoreReranker(code=0.4, doc=0.75), docs_fallback=True,
    )
    assert _sent_paths(result) == {"src/app.py", "README.md"}
    assert result.audit_log["docs_fallback"] == {
        "used": True, "reason": "better", "best_code": 0.4, "best_doc": 0.75,
    }


# 5. flag on, best_doc exactly best_code + docs_margin counts as better; just below does not
def test_flag_on_exact_margin_boundary(tmp_path):
    exact, _ = _ask(
        tmp_path / "exact", ChunkScoreReranker(code=0.5, doc=0.7),
        docs_fallback=True, docs_margin=0.2,
    )
    assert _sent_paths(exact) == {"src/app.py", "README.md"}
    assert exact.audit_log["docs_fallback"]["reason"] == "better"
    assert exact.audit_log["docs_fallback"]["used"] is True

    below, _ = _ask(
        tmp_path / "below", ChunkScoreReranker(code=0.5, doc=0.699),
        docs_fallback=True, docs_margin=0.2,
    )
    assert _sent_paths(below) == {"src/app.py"}
    assert below.audit_log["docs_fallback"]["reason"] is None
    assert below.audit_log["docs_fallback"]["used"] is False


# 6. flag on, code fails the gate, docs pass: only doc chunks sent; reason "code_failed"
def test_flag_on_code_fails_gate_but_docs_pass_sends_only_docs(tmp_path):
    result, gen = _ask(
        tmp_path, ChunkScoreReranker(code=0.005, doc=0.3), docs_fallback=True,
    )
    assert len(gen.calls) == 1
    assert _sent_paths(result) == {"README.md"}
    assert result.audit_log["evidence_gate"] == {
        "min_top_score": THRESHOLD, "top_score": 0.005, "passed": False,
    }
    assert result.audit_log["docs_fallback"] == {
        "used": True, "reason": "code_failed", "best_code": 0.005, "best_doc": 0.3,
    }


# 7. flag on, neither passes: the existing refusal text, zero generator calls
def test_flag_on_neither_passes_refuses_without_generating(tmp_path):
    result, gen = _ask(
        tmp_path, ChunkScoreReranker(code=0.005, doc=0.01), docs_fallback=True,
    )
    assert online.NO_EVIDENCE in result.answer
    assert online.CLOSEST_HEADER in result.answer
    assert gen.calls == []
    assert result.audit_log["generator_calls"] == 0
    assert _sent_paths(result) == set()
    assert result.audit_log["docs_fallback"] == {
        "used": False, "reason": None, "best_code": 0.005, "best_doc": 0.01,
    }


# 8. a cited doc chunk that was sent is verified by the citation checker (outcome F)
def test_cited_doc_chunk_is_verified_outcome_f(tmp_path):
    result, _ = _ask(
        tmp_path, ChunkScoreReranker(code=0.005, doc=0.4), docs_fallback=True,
    )
    assert result.citation_outcome == "F"
    assert len(result.sources) == 1
    assert result.sources[0].path == "README.md"
    assert result.sources[0].verified is True


# 9. DOCS_NOTE is absent whenever no doc chunk is sent (including flag on, case 2)
def test_docs_note_absent_when_no_doc_chunk_sent(tmp_path):
    result, gen = _ask(
        tmp_path, ChunkScoreReranker(code=0.5, doc=0.6), docs_fallback=True,
    )
    assert _sent_paths(result) == {"src/app.py"}
    assert harness.DOCS_NOTE not in gen.calls[0][1]["content"]
    plain = harness.user_message(QUESTION, [], tools_enabled=True, docs=False)
    assert plain == harness.user_message(QUESTION, [], tools_enabled=True)
    assert harness.DOCS_NOTE not in plain


# 10. the token prefix counts DOCS_NOTE when docs are sent
def test_token_prefix_counts_docs_note_when_docs_are_sent(tmp_path):
    gen = CountingGenerator()
    _ask(
        tmp_path, ChunkScoreReranker(code=0.5, doc=0.8),
        generator=gen, docs_fallback=True,
    )
    expected = harness.user_message(QUESTION, [], tools_enabled=True, docs=True)
    assert harness.DOCS_NOTE in expected
    assert expected in gen.counted


# 11. asks_about_docs whole-word and extension check
@pytest.mark.parametrize("question, expected", [
    ("What does the README say?", True),
    ("where is the docs folder", True),
    ("see setup.rst", True),
    ("check CONTRIBUTING.md for details", True),
    ("How does url_for work?", False),
    ("the docstring of make_response", False),
])
def test_asks_about_docs(question, expected):
    assert online.asks_about_docs(question) is expected


# 12. config defaults, TOML list -> tuple conversion, and validation of bad values
def test_config_defaults_toml_and_validation(tmp_path):
    cfg = RetrievalConfig()
    assert cfg.docs_fallback is False
    assert cfg.doc_languages == ("md", "rst")
    assert cfg.docs_margin == 0.2
    assert OnlineConfig().retrieval == cfg

    toml_path = tmp_path / "codecompass.toml"
    toml_path.write_text(
        '[retrieval]\ndocs_fallback = true\ndoc_languages = ["md", "rst"]\ndocs_margin = 0.25\n'
    )
    loaded = load_online_config(toml_path).retrieval
    assert loaded.docs_fallback is True
    assert loaded.doc_languages == ("md", "rst")
    assert isinstance(loaded.doc_languages, tuple)
    assert loaded.docs_margin == 0.25

    bad_toml = tmp_path / "bad.toml"
    bad_toml.write_text('[retrieval]\ndoc_languages = "md"\n')
    with pytest.raises(ValueError, match=r"retrieval\.doc_languages"):
        load_online_config(bad_toml)

    bad_values = [
        ("docs_fallback", 1),
        ("docs_fallback", "yes"),
        ("docs_fallback", None),
        ("doc_languages", []),
        ("doc_languages", [""]),
        ("doc_languages", "md"),
        ("docs_margin", -0.1),
        ("docs_margin", 1.5),
        ("docs_margin", "0.2"),
        ("docs_margin", True),
    ]
    for name, val in bad_values:
        with pytest.raises(ValueError, match=rf"retrieval\.{name}"):
            RetrievalConfig(**{name: val})


# 13. flag on, repo with NO doc files: only code is sent, best_doc is None, reason is None
def test_flag_on_no_doc_files_sends_only_code(tmp_path):
    repo = _build_code_only_repo(tmp_path / "repo")
    gen = CitingGenerator()
    kw = stubs(gen)
    kw["reranker"] = ChunkScoreReranker(code=0.5, doc=0.0)
    cfg = _cfg(tmp_path, docs_fallback=True)
    result = online.ask(repo, README_QUESTION, config=cfg, index_dir=tmp_path / "idx", **kw)
    assert _sent_paths(result) == {"src/app.py"}
    assert result.audit_log["docs_fallback"] == {
        "used": False, "reason": None, "best_code": 0.5, "best_doc": None,
    }


# 14. flag on, repo with ONLY README.md: doc chunks sent, reason "code_failed", best_code is None
def test_flag_on_docs_only_repo_sends_docs(tmp_path):
    repo = _build_docs_only_repo(tmp_path / "repo")
    gen = CitingGenerator()
    kw = stubs(gen)
    kw["reranker"] = ChunkScoreReranker(code=0.0, doc=0.6)
    cfg = _cfg(tmp_path, docs_fallback=True)
    result = online.ask(repo, QUESTION, config=cfg, index_dir=tmp_path / "idx", **kw)
    assert _sent_paths(result) == {"README.md"}
    assert result.audit_log["docs_fallback"]["reason"] == "code_failed"
    assert result.audit_log["docs_fallback"]["best_code"] is None
    assert result.audit_log["docs_fallback"]["used"] is True
    assert result.audit_log["evidence_gate"] == {
        "min_top_score": THRESHOLD, "top_score": None, "passed": False,
    }

