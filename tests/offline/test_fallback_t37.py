"""T3.7 fallback chunker tests (tests-first)."""

from codecompass.offline.chunking import fallback
from codecompass.offline.chunking.sizing import SizePolicy
from codecompass.offline.models import ChunkMode

POLICY = SizePolicy(target_tokens=10, hard_max_tokens=40)
TOK = lambda s: s.split()  # noqa: E731


def test_windows_near_target_prefer_blank_breaks():
    src = "\n".join(
        ["line one here", "", "line two here", ""] + [f"code line {i} now" for i in range(20)]
    ) + "\n"
    chunks, mode = fallback.chunk("src/tool.go", src, "sha", policy=POLICY, tokenizer=TOK)
    assert mode == ChunkMode.FALLBACK
    assert len(chunks) > 2
    for c in chunks:
        assert len(TOK(c.text)) <= POLICY.target_tokens
        assert c.language == "go"


def test_crlf_and_unicode_ranges_accurate():
    src = "x = 1\r\n\r\nünïcode — line\r\n" + "".join(f"y{i} = {i}\r\n" for i in range(20))
    chunks, _ = fallback.chunk("src/a.rb", src, "sha", policy=POLICY, tokenizer=TOK)
    raw_lines = src.split("\n")  # keep trailing \r so CRLF preservation is checked
    if raw_lines and raw_lines[-1] == "":
        raw_lines.pop()  # same trailing-newline convention as the chunker
    assert len(chunks) > 1
    assert "\r\n" in chunks[0].text
    for c in chunks:
        assert c.text == "\n".join(raw_lines[c.start_line - 1:c.end_line])


def test_empty_file_and_hard_max():
    assert fallback.chunk("src/e.go", "", "sha")[0] == []
    src = "".join(f"word{i} " for i in range(500)).strip()
    chunks, _ = fallback.chunk("src/big.go", src + "\n", "sha",
                               policy=POLICY, tokenizer=TOK)
    for c in chunks:
        assert len(TOK(c.text)) <= POLICY.hard_max_tokens
