"""T3.6 Java chunker tests (tests-first)."""

from codecompass.offline.chunking import treesitter
from codecompass.offline.models import ChunkMode

JAVA = '''package com.x;

import java.util.List;

public class Outer {
    private int x;

    public Outer() {
        x = 1;
    }

    @Override
    public String toString() {
        return "o";
    }

    class Inner {
        void go() {}
    }
}

interface Shape {
    int area();
}

enum Color {
    RED, GREEN
}
'''


def test_java_units():
    chunks, mode = treesitter.chunk("src/Outer.java", JAVA, "sha")
    assert mode == ChunkMode.STRUCTURED
    by_symbol = {c.symbol: c for c in chunks}
    # Small classes stay whole (D4); annotations nest inside.
    assert set(by_symbol) == {None, "Outer", "Shape", "Color"}
    assert by_symbol["Outer"].text.startswith("public class Outer")
    assert "@Override" in by_symbol["Outer"].text
    assert "class Inner" in by_symbol["Outer"].text
    assert by_symbol[None].text.startswith("package com.x")


def test_big_java_class_splits_to_methods():
    from codecompass.offline.chunking.sizing import SizePolicy
    policy = SizePolicy(target_tokens=20, hard_max_tokens=200)
    src = "public class Big {\n" + "".join(
        f"    public int m{i}() {{\n        return {i};\n    }}\n" for i in range(6)) + "}\n"
    chunks, _ = treesitter.chunk("src/Big.java", src, "sha",
                                 policy=policy, tokenizer=lambda s: s.split())
    symbols = [c.symbol for c in chunks]
    assert symbols[0] == "Big"
    assert symbols[1:] == [f"Big.m{i}" for i in range(6)]


def test_java_ranges_match_lines():
    chunks, _ = treesitter.chunk("src/Outer.java", JAVA, "sha")
    lines = JAVA.split("\n")
    for c in chunks:
        assert c.text == "\n".join(lines[c.start_line - 1:c.end_line])
        assert c.language == "java"
