"""T15.1 evidence gate tests (tests-first).

Contract under test (Spec AC-1.5, 1.6, 1.7, 7.4, FR-20; Plan D19; Article I.2, I.3, V.4, X.2):
  - a best re-ranker score below retrieval.min_top_score: the generator is not called,
    no tool runs, the answer is online.NO_EVIDENCE plus the closest matches
  - a best score equal to the threshold, or one good chunk among poor ones, proceeds
  - the closest matches are the first retrieval.closest_files distinct files, best first,
    each with its best chunk's lines, in plain text that the citation checker never reads
  - the gate is recorded in the audit log: the threshold, the best score, passed or not
  - the `rag` mode is gated too; `no_retrieval` and an empty index are not
  - retrieval.min_top_score (0 to 1, default 0.02) and retrieval.closest_files (0 or more,
    default 3) are validated at startup

Seen in use (7B, spm_proj): "What is the capital of France?" re-ranked at best 0.006 and
the model answered "Paris" from its own knowledge, with no evidence at all.
"""

import dataclasses
import re
import subprocess

import pytest

import codecompass.online as online
from codecompass.online.config import OnlineConfig, RetrievalConfig, load_online_config
from tests.online.ask_support import CitingGenerator, config, docs_only_repo, stubs
from tests.support.fixture_repo import build_history_repo
from tests.support.stub_generator import StubGenerator

QUESTION = "Why does authenticate retry?"
THRESHOLD = 0.02
CLOSEST_HEADER = ("Closest matches found (these are not evidence for an answer; "
                  "check them yourself):")

# alpha.py has two chunks (lines 1-2 and 5-6); the others have one (lines 1-2).
FILES = {
    "src/alpha.py": "def alpha_one():\n    return 1\n\n\ndef alpha_two():\n    return 2\n",
    "src/beta.py": "def beta_one():\n    return 1\n",
    "src/gamma.py": "def gamma_one():\n    return 1\n",
    "src/delta.py": "def delta_one():\n    return 1\n",
}
# Best first: alpha_two, alpha_one, beta, gamma, delta. All below the threshold.
BY_FUNCTION = {"alpha_two": 0.004, "alpha_one": 0.003, "beta_one": 0.002,
               "gamma_one": 0.001, "delta_one": 0.0005}


class ScoreReranker:
    """Gives the first text *first* and every other text *rest*; records its calls."""

    def __init__(self, first: float, rest: float | None = None) -> None:
        self.first, self.rest = first, first if rest is None else rest
        self.calls = []

    def rerank(self, query, texts):
        self.calls.append((query, list(texts)))
        return [self.first] + [self.rest] * (len(texts) - 1)


class FunctionScoreReranker:
    """Scores a text by the function name it contains, so the order is known."""

    def __init__(self, scores: dict[str, float]) -> None:
        self.scores = scores

    def rerank(self, query, texts):
        return [next((v for k, v in self.scores.items() if k in t), 0.0) for t in texts]


def _cfg(tmp_path, *, min_top_score=THRESHOLD, mode="rag_tools", **retrieval):
    cfg = config(tmp_path, mode=mode)
    return dataclasses.replace(cfg, retrieval=dataclasses.replace(
        cfg.retrieval, min_top_score=min_top_score, **retrieval))


def _ask(tmp_path, reranker, *, generator=None, **cfg_kw):
    repo = build_history_repo(tmp_path / "repo")
    gen = generator or CitingGenerator()
    kw = stubs(gen)
    kw["reranker"] = reranker
    result = online.ask(repo.path, QUESTION, config=_cfg(tmp_path, **cfg_kw),
                        index_dir=tmp_path / "idx", **kw)
    return result, gen


def _four_file_repo(path):
    path.mkdir(parents=True)
    for rel, text in FILES.items():
        (path / rel).parent.mkdir(parents=True, exist_ok=True)
        (path / rel).write_text(text)
    for args in (["init", "-q"], ["add", "-A"],
                 ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "files"]):
        subprocess.run(["git", *args], cwd=path, check=True)
    return path


def _refuse_with_four_files(tmp_path, **retrieval):
    repo = _four_file_repo(tmp_path / "four")
    gen = CitingGenerator()
    kw = stubs(gen)
    kw["reranker"] = FunctionScoreReranker(BY_FUNCTION)
    result = online.ask(repo, QUESTION, config=_cfg(tmp_path, **retrieval),
                        index_dir=tmp_path / "idx", **kw)
    return result, gen


def _listed(answer):
    return re.findall(r"^- (\S+), lines (\d+)-(\d+)$", answer, re.M)


# AC-1.5, FR-20: below the threshold nothing is generated.
def test_best_score_below_threshold_refuses_without_generating(tmp_path):
    result, gen = _ask(tmp_path, ScoreReranker(0.005))
    assert online.NO_EVIDENCE in result.answer
    assert gen.calls == []
    assert result.audit_log["generator_calls"] == 0
    assert result.audit_log["tool_calls"] == []


# AC-1.5: the boundary is explicit: equal to the threshold proceeds.
def test_best_score_equal_to_threshold_proceeds(tmp_path):
    result, gen = _ask(tmp_path, ScoreReranker(THRESHOLD))
    assert len(gen.calls) >= 1
    assert online.NO_EVIDENCE not in result.answer


# AC-1.5: it is the best score that counts, not the average.
def test_one_good_chunk_among_poor_ones_proceeds(tmp_path):
    result, gen = _ask(tmp_path, ScoreReranker(0.9, rest=0.0))
    assert len(gen.calls) >= 1
    assert online.NO_EVIDENCE not in result.answer


# AC-1.5: the gate also applies to the `rag` mode (no tools, same retrieval).
def test_rag_mode_is_gated_too(tmp_path):
    result, gen = _ask(tmp_path, ScoreReranker(0.005), mode="rag")
    assert online.NO_EVIDENCE in result.answer
    assert gen.calls == []


# AC-1.6: 0 switches the gate off, even for a best score of 0.
def test_threshold_zero_turns_the_gate_off(tmp_path):
    result, gen = _ask(tmp_path, ScoreReranker(0.0), min_top_score=0)
    assert len(gen.calls) >= 1


# AC-1.7, Article X.2: the refusal says where to look: the closest distinct files, best first.
def test_refusal_names_the_three_closest_files_best_first(tmp_path):
    result, gen = _refuse_with_four_files(tmp_path)
    assert gen.calls == []
    assert online.NO_EVIDENCE in result.answer
    assert CLOSEST_HEADER in result.answer
    assert _listed(result.answer) == [("src/alpha.py", "5", "6"),   # its best chunk, not 1-2
                                      ("src/beta.py", "1", "2"),
                                      ("src/gamma.py", "1", "2")]
    assert "delta" not in result.answer


def test_a_file_with_several_chunks_is_listed_once(tmp_path):
    result, _ = _refuse_with_four_files(tmp_path)
    assert CLOSEST_HEADER in result.answer
    assert result.answer.count("src/alpha.py") == 1


def test_closest_files_setting_changes_the_count(tmp_path):
    two, _ = _refuse_with_four_files(tmp_path / "two", closest_files=2)
    assert [p for p, _, _ in _listed(two.answer)] == ["src/alpha.py", "src/beta.py"]
    ten, _ = _refuse_with_four_files(tmp_path / "ten", closest_files=10)
    assert [p for p, _, _ in _listed(ten.answer)] == [
        "src/alpha.py", "src/beta.py", "src/gamma.py", "src/delta.py"]  # only four exist


def test_zero_closest_files_lists_nothing(tmp_path):
    result, gen = _refuse_with_four_files(tmp_path, closest_files=0)
    assert gen.calls == []
    assert online.NO_EVIDENCE in result.answer
    assert CLOSEST_HEADER not in result.answer
    assert _listed(result.answer) == []


# AC-1.7, AC-4.8: the list is plain text. The checker sees an answer with no citations.
def test_the_list_is_not_read_as_citations(tmp_path):
    result, _ = _refuse_with_four_files(tmp_path)
    assert result.sources == []
    assert result.citation_outcome == "G"
    assert result.audit_log["citation"]["unverified"] == []


# AC-7.4: a refusal is auditable: the value in force, the score seen, and what was retrieved.
def test_refusal_is_recorded_in_the_log(tmp_path):
    result, _ = _ask(tmp_path, ScoreReranker(0.005))
    log = result.audit_log
    assert log["evidence_gate"] == {"min_top_score": THRESHOLD, "top_score": 0.005,
                                    "passed": False}
    assert log["retrieved"], "the retrieved chunks are still logged"
    assert not any(entry["sent"] for entry in log["retrieved"])


def test_pass_is_recorded_in_the_log(tmp_path):
    result, _ = _ask(tmp_path, ScoreReranker(0.5))
    assert result.audit_log["evidence_gate"] == {"min_top_score": THRESHOLD,
                                                 "top_score": 0.5, "passed": True}


# AC-7.4 / AC-10.2: nothing was re-ranked, so there is no gate entry and no list.
def test_no_retrieval_mode_is_unaffected(tmp_path):
    reranker = ScoreReranker(0.0)
    gen = StubGenerator(["An answer without evidence."])
    result, _ = _ask(tmp_path, reranker, generator=gen, mode="no_retrieval")
    assert len(gen.calls) == 1
    assert reranker.calls == []
    assert "evidence_gate" not in result.audit_log
    assert CLOSEST_HEADER not in result.answer


def test_empty_index_has_no_gate_entry_and_no_list(tmp_path):
    repo = docs_only_repo(tmp_path / "docs")
    gen = CitingGenerator()
    kw = stubs(gen)
    kw["reranker"] = ScoreReranker(0.0)
    result = online.ask(repo, QUESTION, config=_cfg(tmp_path),
                        index_dir=tmp_path / "idx", **kw)
    assert online.NO_EVIDENCE in result.answer
    assert gen.calls == []
    assert "evidence_gate" not in result.audit_log
    assert CLOSEST_HEADER not in result.answer


# AC-1.6, AC-1.7: named config values with defaults, not magic numbers.
def test_defaults():
    assert OnlineConfig().retrieval.min_top_score == 0.02
    assert RetrievalConfig().min_top_score == 0.02
    assert OnlineConfig().retrieval.closest_files == 3
    assert RetrievalConfig().closest_files == 3


def test_both_settings_are_read_from_the_config_file(tmp_path):
    path = tmp_path / "codecompass.toml"
    path.write_text("[retrieval]\nmin_top_score = 0.2\nclosest_files = 5\n")
    retrieval = load_online_config(path).retrieval
    assert (retrieval.min_top_score, retrieval.closest_files) == (0.2, 5)


@pytest.mark.parametrize("value", [0, 1, 0.0, 0.5, 1.0])
def test_min_top_score_from_0_to_1_is_accepted(value):
    assert RetrievalConfig(min_top_score=value).min_top_score == value


@pytest.mark.parametrize("value", [0, 1, 3, 100])
def test_closest_files_whole_numbers_are_accepted(value):
    assert RetrievalConfig(closest_files=value).closest_files == value


# AC-1.6: a bad value fails loudly at startup and names the setting.
@pytest.mark.parametrize("name, toml_value", [
    ("min_top_score", "-0.1"), ("min_top_score", "1.5"),
    ("min_top_score", '"0.1"'), ("min_top_score", "true"),
    ("closest_files", "-1"), ("closest_files", "2.5"),
    ("closest_files", '"3"'), ("closest_files", "true"),
])
def test_bad_values_fail_loudly_from_the_config_file(tmp_path, name, toml_value):
    path = tmp_path / "codecompass.toml"
    path.write_text(f"[retrieval]\n{name} = {toml_value}\n")
    with pytest.raises(ValueError, match=rf"retrieval\.{name}"):
        load_online_config(path)


@pytest.mark.parametrize("name, value", [
    ("min_top_score", -0.1), ("min_top_score", 1.5), ("min_top_score", "0.1"),
    ("min_top_score", True), ("min_top_score", None),
    ("closest_files", -1), ("closest_files", 2.5), ("closest_files", "3"),
    ("closest_files", True), ("closest_files", None),
])
def test_bad_values_fail_loudly_when_constructed(name, value):
    with pytest.raises(ValueError, match=rf"retrieval\.{name}"):
        RetrievalConfig(**{name: value})
