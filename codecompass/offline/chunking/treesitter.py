"""Structure-aware chunker over tree-sitter parse trees (plan D4)."""

from __future__ import annotations

from .ids import chunk_id
from .registry import language_for_path, spec_for_language
from .sizing import SizePolicy, classify_size, count_tokens
from codecompass.offline.models import Chunk, ChunkMode

_parsers: dict[str, object] = {}


def _parser(language: str):
    if language not in _parsers:
        from tree_sitter_language_pack import get_parser
        _parsers[language] = get_parser(language)
    return _parsers[language]


def _word_split(text: str) -> list[str]:
    return text.split()


class _Emitter:
    def __init__(self, path, lines, language, commit_sha, policy, tokenizer):
        self.path = path
        self.lines = lines
        self.language = language
        self.commit_sha = commit_sha
        self.policy = policy
        self.tokenizer = tokenizer
        self.occurrence: dict[str, int] = {}
        self.chunks: list[Chunk] = []

    def take(self, start: int, end: int, symbol: str | None) -> None:
        """Take 1-based inclusive [start, end] as one chunk."""
        text = "\n".join(self.lines[start - 1:end])
        key = symbol or ""
        index = self.occurrence.get(key, 0)
        self.occurrence[key] = index + 1
        self.chunks.append(Chunk(
            id=chunk_id(self.path, symbol, index, text),
            text=text, path=self.path,
            start_line=start, end_line=end,
            language=self.language, symbol=symbol,
            commit_sha=self.commit_sha,
        ))

    def tokens(self, start: int, end: int) -> int:
        return count_tokens("\n".join(self.lines[start - 1:end]), self.tokenizer)


def _node_text(node, content: bytes) -> str:
    return content[node.start_byte:node.end_byte].decode("utf-8", "replace")


def _unwrap(node, spec):
    """Return (range_node, named_node, intermediates) peeling wrappers.

    Intermediates (e.g. variable_declarator) are kept so the symbol can be
    resolved when the inner function node itself is anonymous.
    """
    current = node
    while True:
        named = None
        for child in current.children:
            if child.type in spec["function"] or child.type in spec["class"]:
                named = child
                break
        if named is None or current.type not in spec["wrapper"]:
            break
        current = named
    if current.type in spec["function"] or current.type in spec["class"]:
        return node, current, []
    # Nearest function/class descendant (e.g. export > lexical > declarator
    # > arrow); intermediates resolve anonymous names like `const f = ...`.
    from collections import deque
    queue = deque((child, [child]) for child in current.children)
    while queue:
        descendant, trail = queue.popleft()
        if descendant.type in spec["function"] or descendant.type in spec["class"]:
            return node, descendant, trail[:-1]
        if len(trail) < 3:
            queue.extend((c, [*trail, c]) for c in descendant.children)
    return node, None, []


def _symbol(named, intermediates, content: bytes, parent: str | None) -> str | None:
    for candidate in [named, *intermediates] if named is not None else intermediates:
        name_node = candidate.child_by_field_name("name")
        if name_node is None:
            for child in candidate.children:
                if child.type == "identifier":
                    name_node = child
                    break
        if name_node is not None:
            name = _node_text(name_node, content).strip()
            return f"{parent}.{name}" if parent else name
    return parent


def _methods_of(class_node, spec):
    """Direct method-like children of a class node."""
    methods = []

    def visit(node, depth):
        for child in node.children:
            if child.type in spec["method"]:
                methods.append(child)
            elif depth < 2 and child.is_named and child.type not in spec["function"]:
                visit(child, depth + 1)

    visit(class_node, 0)
    return methods


def _split_children(node, spec, emitter: _Emitter, symbol: str | None):
    """Split an oversize unit at its top-level blocks (greedy groups)."""
    container = node
    for child in node.children:
        if child.type in ("block", "statement_block") or child.type.endswith("_body"):
            container = child
            break
    stmts = [c for c in container.children
             if c.is_named and c.type not in ("comment",)]
    if not stmts:
        _windows(emitter, node.start_point[0] + 1, node.end_point[0] + 1, symbol)
        return
    group_start = node.start_point[0] + 1
    acc_end: int | None = None
    for stmt in stmts:
        stmt_end = stmt.end_point[0] + 1
        if acc_end is None:
            acc_end = stmt_end
            if classify_size(emitter.tokens(group_start, acc_end), emitter.policy) == "fits":
                continue
            _emit_group(emitter, group_start, acc_end, symbol)
            group_start, acc_end = acc_end + 1, None
            continue
        if classify_size(emitter.tokens(group_start, stmt_end), emitter.policy) == "fits":
            acc_end = stmt_end
        else:
            _emit_group(emitter, group_start, acc_end, symbol)
            group_start, acc_end = acc_end + 1, stmt_end
            if classify_size(emitter.tokens(group_start, acc_end), emitter.policy) != "fits":
                _emit_group(emitter, group_start, acc_end, symbol)
                group_start, acc_end = acc_end + 1, None
    if acc_end is not None:
        _emit_group(emitter, group_start, acc_end, symbol)
    elif group_start <= node.end_point[0] + 1:
        _emit_group(emitter, group_start, node.end_point[0] + 1, symbol)


def _emit_group(emitter: _Emitter, start: int, end: int, symbol: str | None):
    if start > end:
        return
    if classify_size(emitter.tokens(start, end), emitter.policy) == "over_hard_max":
        _windows(emitter, start, end, symbol)
    else:
        emitter.take(start, end, symbol)


def _windows(emitter: _Emitter, start: int, end: int, symbol: str | None):
    """Line windows near the target size, preferring blank-line breaks."""
    cur = start
    while cur <= end:
        nxt = cur
        while nxt <= end:
            trial = emitter.tokens(cur, nxt)
            state = classify_size(trial, emitter.policy)
            if state == "fits":
                nxt += 1
            elif state == "over_target":
                break_at = nxt
                for back in range(nxt - 1, cur - 1, -1):
                    if emitter.lines[back - 1].strip() == "":
                        break_at = back
                        break
                nxt = max(break_at, cur)
                break
            else:  # over_hard_max: force a cut
                break
        if nxt == cur:
            nxt = cur  # single line over hard max: emit alone rather than loop
        emitter.take(cur, nxt, symbol)
        cur = nxt + 1


def _emit_unit(node, spec, content: bytes, emitter: _Emitter, parent: str | None):
    range_node, named, intermediates = _unwrap(node, spec)
    start = range_node.start_point[0] + 1
    end = range_node.end_point[0] + 1
    symbol = _symbol(named, intermediates, content, parent)
    state = classify_size(emitter.tokens(start, end), emitter.policy)
    if state == "fits":
        emitter.take(start, end, symbol)
        return
    target = named if named is not None else node
    if target.type in spec["class"]:
        body = target
        for child in target.children:
            if child.type in ("block", "statement_block") or child.type.endswith("_body"):
                body = child
                break
        methods = [c for c in body.children if c.type in spec["method"]]
        nested = [c for c in body.children if c.type in spec["class"]]
        if methods or nested:
            members = sorted(methods + nested,
                             key=lambda n: n.start_point[0])
            first = members[0].start_point[0] + 1
            if first > start:
                _emit_sized(emitter, start, first - 1, symbol)
            for method in methods:
                _emit_unit(method, spec, content, emitter, symbol)
            for sub in nested:
                _emit_unit(sub, spec, content, emitter, symbol)
            return
    _split_children(target, spec, emitter, symbol)


def _emit_sized(emitter: _Emitter, start: int, end: int, symbol: str | None):
    if start > end:
        return
    if classify_size(emitter.tokens(start, end), emitter.policy) == "fits":
        emitter.take(start, end, symbol)
    else:
        _windows(emitter, start, end, symbol)


def chunk(path: str, content: str, commit_sha: str, *,
          policy: SizePolicy | None = None,
          tokenizer=None) -> tuple[list[Chunk], ChunkMode]:
    """Chunk one file along structural boundaries (AC-3.1, AC-3.6)."""
    language = language_for_path(path)
    if language is None:
        raise ValueError(f"no tree-sitter language for: {path}")
    policy = policy or SizePolicy()
    tokenizer = tokenizer or _word_split
    spec = spec_for_language(language)
    tree = _parser(language).parse(content.encode("utf-8"))
    lines = content.split("\n")
    emitter = _Emitter(path, lines, language, commit_sha, policy, tokenizer)
    residue: list = []
    units = 0
    for child in tree.root_node.children:
        if child.type in spec["unit"]:
            if residue:
                _flush_residue(residue, emitter)
                residue = []
            _emit_unit(child, spec, content.encode("utf-8"), emitter, None)
            units += 1
        elif child.type not in ("comment",) and child.is_named:
            residue.append(child)
    if residue:
        _flush_residue(residue, emitter)
    if tree.root_node.has_error and units == 0 and not emitter.chunks:
        return [], ChunkMode.FALLBACK
    return emitter.chunks, ChunkMode.STRUCTURED


def _flush_residue(nodes, emitter: _Emitter) -> None:
    start = nodes[0].start_point[0] + 1
    end = nodes[-1].end_point[0] + 1
    if classify_size(emitter.tokens(start, end), emitter.policy) == "fits":
        emitter.take(start, end, None)
        return
    cur = start
    for node in nodes:
        node_end = node.end_point[0] + 1
        if (classify_size(emitter.tokens(cur, node_end), emitter.policy) != "fits"
                and cur < node.start_point[0] + 1):
            emitter.take(cur, node.start_point[0], None)
            cur = node.start_point[0] + 1
    if cur <= end:
        if classify_size(emitter.tokens(cur, end), emitter.policy) == "fits":
            emitter.take(cur, end, None)
        else:
            _windows(emitter, cur, end, None)
