"""Extension -> language -> structural node types (spec C1, plan D4)."""

from __future__ import annotations

LANGUAGES: dict[str, dict] = {
    "python": {
        "extensions": (".py",),
        "unit": ("decorated_definition", "function_definition", "class_definition"),
        "function": ("function_definition",),
        "class": ("class_definition",),
        "method": ("function_definition",),
        "wrapper": ("decorated_definition",),
    },
    "javascript": {
        "extensions": (".js", ".jsx"),
        "unit": (
            "export_statement", "function_declaration", "class_declaration",
            "lexical_declaration", "variable_declaration",
        ),
        "function": ("function_declaration", "function_expression", "arrow_function"),
        "class": ("class_declaration",),
        "method": ("method_definition",),
        "wrapper": ("export_statement",),
    },
    "typescript": {
        "extensions": (".ts",),
        "unit": (
            "export_statement", "function_declaration", "class_declaration",
            "lexical_declaration", "variable_declaration",
            "interface_declaration", "type_alias_declaration",
        ),
        "function": ("function_declaration", "function_expression", "arrow_function"),
        "class": ("class_declaration",),
        "method": ("method_definition",),
        "wrapper": ("export_statement",),
    },
    "java": {
        "extensions": (".java",),
        "unit": (
            "class_declaration", "interface_declaration",
            "enum_declaration", "annotation_type_declaration",
        ),
        "function": ("method_declaration", "constructor_declaration"),
        "class": (
            "class_declaration", "interface_declaration",
            "enum_declaration", "annotation_type_declaration",
        ),
        "method": ("method_declaration", "constructor_declaration"),
        "wrapper": (),
    },
}

# tsx shares the typescript grammar's node types.
LANGUAGES["tsx"] = {
    **LANGUAGES["typescript"],
    "extensions": (".tsx",),
}


def language_for_path(path: str) -> str | None:
    ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path.rsplit("/", 1)[-1] else ""
    for lang, spec in LANGUAGES.items():
        if ext in spec["extensions"]:
            return lang
    return None


def spec_for_language(language: str) -> dict:
    return LANGUAGES[language]
