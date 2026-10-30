"""T14.1 open_file tests (tests-first).

Contract under test (Constitution V.2, VI.4 as of 1.4.0; Plan D6, D7, D18):
  - tools.open_file(repo, commit, path, lines=None, *, max_tokens, count_tokens,
    symbols=None) -> ToolOutput
  - with `lines`: reads the file at the given (indexed) commit, never HEAD, and
    returns the D3 chunk format; ToolOutput.chunks holds one RetrievedChunk for
    exactly the lines shown, so the citation checker can verify it (VI.4)
  - if the range does not fit max_tokens: whole lines from the start of the range,
    then "[showing lines X-Y; ask for lines Y+1-Z to continue]"; the chunk covers
    only the lines shown
  - without `lines`: an outline of the file's indexed symbols with line ranges,
    from the `symbols(path)` callable; not code, so no citable chunk
  - path and line validation reuse D6 (ToolArgumentError)
  - cap_output keeps the chunks of a result that already fits
"""

import pytest

from codecompass.online.agent import tools
from codecompass.online.context import format_chunk
from tests.support.fixture_repo import build_history_repo
from tests.support.stub_generator import StubGenerator

COUNT = StubGenerator(["x"]).count_tokens        # whitespace tokens, deterministic
BIG = 10_000                                     # a cap that never truncates


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    return build_history_repo(tmp_path_factory.mktemp("hist") / "repo")


def read(repo, commit_key, path, lines=None, **kw):
    kw.setdefault("max_tokens", BIG)
    return tools.open_file(repo.path, repo.commits[commit_key], path, lines,
                           count_tokens=COUNT, **kw)


# --- reading a line range -------------------------------------------------------

def test_returns_the_requested_lines_as_a_citable_chunk(repo):
    out = read(repo, "wip", "src/auth.py", "6-12")
    assert not out.error
    [chunk] = out.chunks
    assert (chunk.path, chunk.start_line, chunk.end_line) == ("src/auth.py", 6, 12)
    assert chunk.commit_sha == repo.commits["wip"]
    assert chunk.language == "python"
    assert chunk.text.splitlines()[0] == "def authenticate(client, user, password):"
    assert out.text == format_chunk(chunk)       # same header as retrieved chunks (D3)


def test_reads_the_given_commit_not_head(repo):
    out = read(repo, "retry", "src/auth.py", "3")
    assert out.chunks[0].text == "MAX_RETRIES = 3"   # HEAD has MAX_RETRIES = 5


def test_single_line_range(repo):
    out = read(repo, "wip", "src/auth.py", "3")
    assert (out.chunks[0].start_line, out.chunks[0].end_line) == (3, 3)


# --- fitting the token cap --------------------------------------------------------

def test_long_range_is_cut_to_whole_lines_with_a_continue_marker(repo):
    cap = 30
    out = read(repo, "wip", "src/auth.py", "1-12", max_tokens=cap)
    [chunk] = out.chunks
    assert chunk.start_line == 1 and chunk.end_line < 12
    end = chunk.end_line
    assert out.text == (format_chunk(chunk) + "\n"
                        f"[showing lines 1-{end}; ask for lines {end + 1}-12 to continue]")
    assert COUNT(out.text) <= cap
    assert len(chunk.text.splitlines()) == end   # only the lines actually shown


def test_range_that_fits_has_no_marker(repo):
    out = read(repo, "wip", "src/auth.py", "1-12")
    assert "[showing lines" not in out.text
    assert out.chunks[0].end_line == 12


# --- outline mode -----------------------------------------------------------------

def test_without_lines_returns_an_outline_and_no_citable_chunk(repo):
    symbols = lambda path: [("authenticate", 6, 12)] if path == "src/auth.py" else []
    out = read(repo, "wip", "src/auth.py", symbols=symbols)
    assert not out.error
    assert out.chunks == ()
    assert "authenticate" in out.text and "6-12" in out.text
    assert 'lines="' in out.text                 # tells the model how to read code next


def test_outline_with_no_symbols_says_so(repo):
    out = read(repo, "wip", "src/util.py", symbols=lambda path: [])
    assert out.chunks == () and not out.error
    assert "no outline" in out.text.lower()


# --- validation (D6) --------------------------------------------------------------

@pytest.mark.parametrize("path, lines", [
    ("../secret.py", "1-2"),
    ("/etc/passwd", "1-2"),
    ("src/missing.py", "1-2"),
    ("src/auth.py", "0-3"),
    ("src/auth.py", "5-99"),
    ("src/auth.py", "abc"),
])
def test_bad_arguments_are_rejected(repo, path, lines):
    with pytest.raises(tools.ToolArgumentError):
        read(repo, "wip", path, lines)


# --- cap_output keeps the evidence ------------------------------------------------

def test_cap_output_keeps_chunks_of_a_result_that_fits(repo):
    out = read(repo, "wip", "src/auth.py", "6-12")
    assert tools.cap_output(out, BIG, COUNT).chunks == out.chunks
