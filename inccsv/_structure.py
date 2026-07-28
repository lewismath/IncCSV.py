# inccsv/_structure.py
from __future__ import annotations

from typing import Any

from ._parser import MetadataDict

# Keyword aliases for single-character [structure] values.
_CHAR_ALIASES: dict[str, str] = {"tab": "\t", "\\t": "\t", "space": " "}

# Canonical [structure] key allowlist — spec structure.md.
STRUCTURE_ALLOWED_KEYS = frozenset({
    "delim", "delimiter", "quotechar", "escapechar", "comment", "header", "footerskip"
})

# Writer-relevant [structure] keys: they describe the bytes a writer must emit,
# per INCspec's writer conformance rule.
_STRUCTURE_WRITE_KEYS = ("delimiter", "quotechar", "escapechar")


def coerce_char(value: int | str) -> str:
    """Translate a [structure] char value: keyword alias or int code point → str."""
    if isinstance(value, int):
        return chr(value)
    s = _CHAR_ALIASES.get(str(value).lower(), str(value))
    if len(s) != 1:
        raise ValueError(
            f"[structure] character value must resolve to a single character, got {value!r}"
        )
    return s


def validate_structure_keys(structure: dict) -> None:
    for key in structure:
        if key not in STRUCTURE_ALLOWED_KEYS:
            raise ValueError(
                f"[structure] contains unknown key {key!r}. "
                f"Allowed keys: {sorted(STRUCTURE_ALLOWED_KEYS)}"
            )


def structure_csv_kwargs(metadata: MetadataDict) -> dict[str, Any]:
    """Extract csv delimiter/quotechar/escapechar kwargs from [structure].

    Shared by the reader (all csv.DictReader kwargs) and the writer
    (writer-relevant kwargs only, checked against explicit csv_kwargs).
    """
    structure = metadata.get("structure", {})
    kwargs: dict[str, Any] = {}
    if not isinstance(structure, dict):
        return kwargs
    validate_structure_keys(structure)
    delim_value = structure.get("delimiter") if "delimiter" in structure else structure.get("delim")
    if delim_value is not None:
        kwargs["delimiter"] = coerce_char(delim_value)
    if "quotechar" in structure:
        kwargs["quotechar"] = coerce_char(structure["quotechar"])
    if "escapechar" in structure:
        kwargs["escapechar"] = coerce_char(structure["escapechar"])
    return kwargs


def structure_write_kwargs(metadata: MetadataDict, csv_kwargs: dict[str, Any]) -> dict[str, Any]:
    """Merge writer-relevant [structure] metadata with explicit csv_kwargs.

    Explicit csv_kwargs win when they agree with [structure]. If an explicit
    delimiter/quotechar/escapechar contradicts [structure] metadata, raise
    rather than writing a file whose metadata misdescribes its CSV component.
    """
    structure_kwargs = structure_csv_kwargs(metadata)
    merged = dict(csv_kwargs)
    for key in _STRUCTURE_WRITE_KEYS:
        if key not in structure_kwargs:
            continue
        structure_value = structure_kwargs[key]
        if key in csv_kwargs:
            if csv_kwargs[key] != structure_value:
                raise ValueError(
                    f"CSV writer argument {key}={csv_kwargs[key]!r} contradicts "
                    f"[structure].{key}={structure_value!r}"
                )
        else:
            merged[key] = structure_value
    return merged
