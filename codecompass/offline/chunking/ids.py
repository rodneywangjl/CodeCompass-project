"""Deterministic chunk identity (plan D3, AC-3.7)."""

from __future__ import annotations

import hashlib


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def chunk_id(path: str, symbol: str | None, occurrence: int, text: str) -> str:
    """sha256(path | symbol | occurrence | text_hash), truncated.

    Line numbers are deliberately excluded so an unchanged chunk keeps its id
    when neighbouring edits shift its lines.
    """
    material = f"{path}\x00{symbol or ''}\x00{occurrence}\x00{text_hash(text)}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
