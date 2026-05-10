# inccsv/_reader.py
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Any

from ._parser import split_inc, parse_metadata, MetadataDict

# Keyword aliases for single-character [structure] values (Julia idiom).
_CHAR_ALIASES: dict[str, str] = {"tab": "\t", "space": " "}

# [structure] keys Python can map to csv.DictReader kwargs.
_STRUCTURE_HONOURED_KEYS = frozenset({"delimiter", "delim", "quotechar", "escapechar", "comment"})

# Julia [structure] keys that have no csv.DictReader equivalent; recognised
# so they don't raise, but not applied to the reader.
_STRUCTURE_JULIA_ONLY_KEYS = frozenset({
    "decimal", "groupmark", "missingstring", "dateformat",
    "ignoreemptyrows", "ignorerepeated", "normalizenames",
    "header", "skipto", "footerskip", "limit",
})

_STRUCTURE_KNOWN_KEYS = _STRUCTURE_HONOURED_KEYS | _STRUCTURE_JULIA_ONLY_KEYS


def _coerce_char(value: int | str) -> str:
    """Translate a [structure] char value: keyword alias or int code point → str."""
    if isinstance(value, int):
        return chr(value)
    return _CHAR_ALIASES.get(str(value).lower(), str(value))


@dataclass
class IncFile:
    metadata: MetadataDict
    rows: list[dict[str, str]]
    path: str | None = None

    def to_dataframe(self):
        """Return rows as a pandas DataFrame. Requires pandas (pip install inccsv[pandas])."""
        try:
            import pandas as pd
        except ImportError as exc:
            raise ImportError(
                "pandas is required for to_dataframe(). Install with: pip install inccsv[pandas]"
            ) from exc
        return pd.DataFrame(self.rows)


def _csv_kwargs_from_metadata(metadata: MetadataDict) -> tuple[dict[str, Any], str | None]:
    """Extract csv.DictReader kwargs and comment char from [structure] metadata section."""
    structure = metadata.get("structure", {})
    kwargs: dict[str, Any] = {}
    comment_char: str | None = None
    if isinstance(structure, dict):
        for key in structure:
            if key not in _STRUCTURE_KNOWN_KEYS:
                raise ValueError(
                    f"[structure] contains unknown key {key!r}. "
                    f"Known keys: {sorted(_STRUCTURE_KNOWN_KEYS)}"
                )
        delim_value = structure.get("delimiter") if "delimiter" in structure else structure.get("delim")
        if delim_value is not None:
            kwargs["delimiter"] = _coerce_char(delim_value)
        if "quotechar" in structure:
            kwargs["quotechar"] = _coerce_char(structure["quotechar"])
        if "escapechar" in structure:
            kwargs["escapechar"] = _coerce_char(structure["escapechar"])
        if "comment" in structure:
            comment_char = str(structure["comment"])
        # _STRUCTURE_JULIA_ONLY_KEYS are recognised but not honoured by
        # Python's csv.DictReader; accepted silently for cross-language compatibility.
    return kwargs, comment_char


def read_inc(path: str, **csv_kwargs: Any) -> IncFile:
    """
    Read an INC or plain CSV file.

    Args:
        path: Path to the .inc or .csv file.
        **csv_kwargs: Override csv.DictReader kwargs (e.g., delimiter=';').
                      A 'comment' key is used for line filtering, not passed to csv.

    Returns:
        IncFile with metadata dict and rows as list of dicts (all values are str).
    """
    meta_lines, csv_start = split_inc(path)
    metadata: MetadataDict = parse_metadata(meta_lines) if meta_lines else {}

    base_kwargs, comment_char = _csv_kwargs_from_metadata(metadata)

    if "comment" in csv_kwargs:
        comment_char = str(csv_kwargs.pop("comment"))

    base_kwargs.update(csv_kwargs)

    with open(path, encoding="utf-8") as f:
        all_lines = f.readlines()

    csv_lines = all_lines[csv_start - 1:]

    if comment_char:
        csv_lines = [ln for ln in csv_lines if not ln.lstrip().startswith(comment_char)]

    reader = csv.DictReader(io.StringIO("".join(csv_lines)), **base_kwargs)
    rows = [dict(row) for row in reader]

    return IncFile(metadata=metadata, rows=rows, path=path)
