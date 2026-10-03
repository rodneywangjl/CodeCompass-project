"""T2.2 size limit and binary detection tests (tests-first)."""

from codecompass.offline.config import FilesConfig
from codecompass.offline.exclusions import decide


def test_over_limit_skipped_with_reason():
    cfg = FilesConfig(max_file_bytes=10)
    d = decide("src/a.py", cfg, get_size=lambda: 11)
    assert not d.included and d.reason == "too-large"


def test_nul_byte_is_binary_despite_source_extension():
    cfg = FilesConfig()
    d = decide("src/a.py", cfg, get_size=lambda: 5,
               get_head=lambda: b"\x89PNG\x00binary")
    assert not d.included and d.reason == "binary"


def test_unicode_text_is_not_binary():
    cfg = FilesConfig()
    d = decide("src/a.py", cfg, get_size=lambda: 50,
               get_head=lambda: "ünïcode — text\n".encode("utf-8"))
    assert d.included
