"""T5.2 embedder compatibility gate tests (tests-first)."""

import dataclasses

import pytest

from codecompass.offline.meta import (
    EmbedderMismatchError,
    check_compatible,
    default_meta,
)
from codecompass.offline.models import EmbedderIdentity

BUILT = EmbedderIdentity(model="m", revision="r", dimension=8)


def test_matching_identity_passes():
    check_compatible(default_meta(BUILT), BUILT)


@pytest.mark.parametrize("field,other_value", [
    ("model", "other-model"),
    ("revision", "other-rev"),
    ("dimension", 16),
])
def test_mismatch_names_expected_and_found(field, other_value):
    other = dataclasses.replace(BUILT, **{field: other_value})
    with pytest.raises(EmbedderMismatchError) as e:
        check_compatible(default_meta(BUILT), other)
    assert str(getattr(BUILT, field)) in str(e.value)
    assert str(other_value) in str(e.value)
