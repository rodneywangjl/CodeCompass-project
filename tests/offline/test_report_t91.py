"""T9.1 run report tests (tests-first)."""

import json

from codecompass.offline.models import RunReport
from codecompass.offline.report import to_dict, to_text, write_json


def _report():
    return RunReport(
        mode="incremental", from_commit="aaa", to_commit="bbb",
        files_added=1, files_modified=2, files_deleted=0,
        files_skipped=1, files_non_code=1, files_fallback=1,
        chunks_added=5, chunks_removed=3,
        embedder_model="m", embedder_revision="r",
        elapsed_seconds=1.5, timings={"chunk": 0.5, "embed": 0.7},
    )


def test_dict_text_and_json_file(tmp_path):
    rep = _report()
    d = to_dict(rep)
    assert d["mode"] == "incremental"
    assert (d["from_commit"], d["to_commit"]) == ("aaa", "bbb")
    assert d["chunks_added"] == 5 and d["chunks_removed"] == 3
    assert d["embedder_model"] == "m" and d["schema_version"] == 1
    assert d["timings"] == {"chunk": 0.5, "embed": 0.7}
    text = to_text(rep)
    for needle in ["incremental", "aaa", "bbb", "5", "chunk"]:
        assert needle in text, needle
    out = write_json(rep, tmp_path / "runs" / "r.json")
    assert json.loads(out.read_text())["to_commit"] == "bbb"
