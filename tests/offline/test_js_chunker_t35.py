"""T3.5 JavaScript/TypeScript/TSX chunker tests (tests-first)."""

from codecompass.offline.chunking import treesitter
from codecompass.offline.models import ChunkMode

JS = '''import x from "y";

export function run() {
  return 2;
}

const add = (a, b) => a + b;

export class Box {
  render() {
    return 1;
  }
}

export const Comp = () => {
  return null;
};
'''

TS = '''export interface Shape {
  area(): number;
}

export function id<T>(x: T): T {
  return x;
}

const f: (n: number) => number = (n) => n + 1;
'''

TSX = '''export function Comp({ name }: { name: string }) {
  return <div>hi {name}</div>;
}
'''


def _chunk(path, text):
    chunks, mode = treesitter.chunk(path, text, "sha")
    assert mode == ChunkMode.STRUCTURED
    return chunks


def test_js_units():
    chunks = _chunk("src/a.js", JS)
    by_symbol = {c.symbol: c for c in chunks}
    assert by_symbol["run"].text.startswith("export function run")
    assert by_symbol["add"].text.startswith("const add")
    assert "render" in by_symbol["Box"].text  # small class stays whole
    assert by_symbol["Comp"].text.startswith("export const Comp")
    assert by_symbol[None].text.startswith("import x")


def test_ts_and_tsx_units():
    ts = {c.symbol for c in _chunk("src/a.ts", TS)}
    assert "id" in ts and "f" in ts
    tsx = _chunk("src/c.tsx", TSX)
    assert [c.symbol for c in tsx] == ["Comp"]
    assert "<div>" in tsx[0].text


def test_ranges_match_lines():
    for path, text in [("src/a.js", JS), ("src/a.ts", TS), ("src/c.tsx", TSX)]:
        lines = text.split("\n")
        for c in _chunk(path, text):
            assert c.text == "\n".join(lines[c.start_line - 1:c.end_line])
            assert c.language in ("javascript", "typescript", "tsx")
