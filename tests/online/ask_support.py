"""Shared fixtures for ask() tests (T9.6, T10.x, T11.x, T12.x)."""

from __future__ import annotations

import dataclasses
import re
import subprocess
from pathlib import Path

from codecompass.offline.config import EmbedderConfig, load_config
from codecompass.online import config as online_config
from tests.support.stub_embedder import StubEmbedder
from tests.support.stub_generator import StubGenerator
from tests.support.stub_reranker import StubReranker

_HEADER = re.compile(r"^--- (.+?) \| \w+ ---$", re.M)


def config(tmp_path, mode="rag_tools", **tools):
    base = online_config.OnlineConfig()
    offline = dataclasses.replace(
        load_config(None), embedder=EmbedderConfig(model="stub", revision="stub-1", dimension=8))
    return dataclasses.replace(
        base, offline=offline, pipeline=online_config.PipelineConfig(mode=mode),
        logging=online_config.LoggingConfig(query_log_dir=str(tmp_path / "queries")),
        tools=dataclasses.replace(base.tools, **tools))


class CitingGenerator(StubGenerator):
    """Answers by citing the first chunk header it was shown (outcome F)."""

    def __init__(self, before: list[str] | None = None) -> None:
        super().__init__(["unused"])
        self.before = list(before or [])

    def generate(self, messages):
        super().generate(messages)
        if len(self.calls) <= len(self.before):
            return self.before[len(self.calls) - 1]
        label = _HEADER.search(messages[1]["content"]).group(1)
        return f"Login retries on timeout [1].\n\nSources\n[1] {label}"


def stubs(generator=None):
    return {"generator": generator or CitingGenerator(), "reranker": StubReranker(),
            "embedder": StubEmbedder()}


def docs_only_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "README.md").write_text("# only docs\n")
    for args in (["init", "-q"], ["add", "-A"],
                 ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "docs"]):
        subprocess.run(["git", *args], cwd=path, check=True)
    return path
