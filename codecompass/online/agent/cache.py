"""Per-query tool-result cache (Article V.3, Plan D8)."""

from __future__ import annotations

import json


class ToolCache:
    """Runs each distinct (tool, args) once per ask call.

    Repo and commit are fixed for one ask call, so (tool, args) is the full
    key that Article V.3 asks for.
    """

    def __init__(self, run) -> None:
        self._run = run
        self._results: dict[str, object] = {}

    def get(self, call) -> tuple[object, bool]:
        key = json.dumps([call.tool, call.args], sort_keys=True, default=str)
        if key in self._results:
            return self._results[key], True
        result = self._results[key] = self._run(call)
        return result, False
