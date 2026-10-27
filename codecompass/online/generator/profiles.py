"""Model profile selection (Article VIII.4, Plan D13)."""

from __future__ import annotations

import os

from codecompass.online.config import ModelProfile, OnlineConfig, get_generator_profile


def resolve_profile(config: OnlineConfig, name: str | None = None) -> tuple[str, ModelProfile]:
    """(name, profile): explicit name, else GENERATOR_PROFILE, else the default.

    An unknown name raises (AC-5.9); there is no silent fallback.
    """
    name = name or os.environ.get("GENERATOR_PROFILE") or config.generator.default_profile
    return name, get_generator_profile(config, name)
