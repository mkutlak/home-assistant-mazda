"""Every translation must carry the same keys and placeholders as en.json."""

import json
import re
from pathlib import Path

import pytest

TRANSLATIONS = Path(__file__).parent.parent / "custom_components/mazda_cs/translations"


def _flat(tree: dict, prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in tree.items():
        if isinstance(value, dict):
            out |= _flat(value, f"{prefix}{key}.")
        else:
            out[f"{prefix}{key}"] = value
    return out


def _load(name: str) -> dict[str, str]:
    return _flat(json.loads((TRANSLATIONS / name).read_text(encoding="utf-8")))


@pytest.mark.parametrize(
    "name", sorted(p.name for p in TRANSLATIONS.glob("*.json") if p.name != "en.json")
)
def test_translation_matches_english(name: str) -> None:
    en, other = _load("en.json"), _load(name)
    assert sorted(set(en) - set(other)) == [], "missing keys"
    assert sorted(set(other) - set(en)) == [], "extra keys"
    placeholders = re.compile(r"\{\w+\}")
    for key, text in en.items():
        assert set(placeholders.findall(other[key])) == set(placeholders.findall(text)), key
