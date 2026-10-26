"""T5.5 tool-result caching tests (tests-first).

Contract under test (Spec AC-3.5; Plan D8):
  - codecompass.online.agent.cache.cache_mod.ToolCache(run) where run(call) -> output
  - cache.get(call) -> (output, cache_hit: bool); runs on a miss, reuses on a hit
  - the key is (tool, args); equal args in a different order are the same key
  - unhashable argument values (lists) still work
  - each ToolCache is independent (one per ask call)
"""

from codecompass.online.agent import cache as cache_mod
from codecompass.online.models import ToolCall


class Counter:
    def __init__(self):
        self.calls = []

    def __call__(self, call):
        self.calls.append(call)
        return f"out{len(self.calls)}"


def test_second_identical_call_is_a_cache_hit():
    run = Counter()
    cache = cache_mod.ToolCache(run)
    call = ToolCall(tool="git_log", args={"path": "a.py", "n": 5})
    assert cache.get(call) == ("out1", False)
    assert cache.get(call) == ("out1", True)
    assert len(run.calls) == 1


def test_argument_order_does_not_matter():
    run = Counter()
    cache = cache_mod.ToolCache(run)
    cache.get(ToolCall(tool="git_blame", args={"path": "a.py", "lines": "1-2"}))
    _, hit = cache.get(ToolCall(tool="git_blame", args={"lines": "1-2", "path": "a.py"}))
    assert hit


def test_different_args_or_tool_miss():
    run = Counter()
    cache = cache_mod.ToolCache(run)
    cache.get(ToolCall(tool="git_log", args={"path": "a.py"}))
    assert cache.get(ToolCall(tool="git_log", args={"path": "b.py"}))[1] is False
    assert cache.get(ToolCall(tool="git_blame", args={"path": "a.py"}))[1] is False
    assert len(run.calls) == 3


def test_unhashable_argument_values():
    cache = cache_mod.ToolCache(Counter())
    call = ToolCall(tool="git_log", args={"path": ["a.py"]})
    cache.get(call)
    assert cache.get(call)[1] is True


def test_caches_are_independent():
    run = Counter()
    call = ToolCall(tool="git_log", args={"path": "a.py"})
    cache_mod.ToolCache(run).get(call)
    assert cache_mod.ToolCache(run).get(call)[1] is False
