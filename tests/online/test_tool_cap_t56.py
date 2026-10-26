"""T5.6 tool output cap tests (tests-first).

Contract under test (Spec §6 edge case; Plan D4):
  - tools.cap_output(output, max_tokens, count_tokens) -> ToolOutput
  - output within the cap is returned unchanged
  - otherwise whole lines are kept while the text plus the marker
    "[output truncated: N more lines]" fits in max_tokens; a line is never split
  - commit records whose line was dropped are dropped too, so only commits
    the model actually saw remain citable (Article VI.1)
"""

from codecompass.online.agent import tools

A = tools.CommitRecord("a" * 40, "Ann", "2024-01-01", "first change")
B = tools.CommitRecord("b" * 40, "Bo", "2024-01-02", "second change")
C = tools.CommitRecord("c" * 40, "Cy", "2024-01-03", "third change")


def words(text):
    return len(text.split())


def output():
    text = "\n".join(f'{r.sha[:7]} {r.date} {r.author} "{r.subject}"' for r in (A, B, C))
    return tools.ToolOutput(text=text, commits=(A, B, C))


def test_within_cap_unchanged():
    out = output()
    assert tools.cap_output(out, max_tokens=100, count_tokens=words) == out


def test_truncates_whole_lines_and_marks_it():
    capped = tools.cap_output(output(), max_tokens=13, count_tokens=words)
    lines = capped.text.splitlines()
    assert lines[:-1] == output().text.splitlines()[:1]
    assert lines[-1] == "[output truncated: 2 more lines]"
    assert words(capped.text) <= 13


def test_dropped_lines_drop_their_commits():
    capped = tools.cap_output(output(), max_tokens=13, count_tokens=words)
    assert capped.commits == (A,)


def test_cap_too_small_for_any_line_keeps_only_marker():
    capped = tools.cap_output(output(), max_tokens=4, count_tokens=words)
    assert capped.text == "[output truncated: 3 more lines]"
    assert capped.commits == ()


def test_error_flag_preserved():
    err = tools.ToolOutput(text="error: " + "x " * 50, error=True)
    assert tools.cap_output(err, max_tokens=10, count_tokens=words).error
