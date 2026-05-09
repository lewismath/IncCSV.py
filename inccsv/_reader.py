# inccsv/_reader.py
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Any

from ._parser import split_inc, parse_metadata, MetadataDict


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


def _parse_structure_raw(meta_lines: list[str]) -> dict[str, str]:
    """
    Re-parse only the [structure] section from raw metadata lines without comment stripping.

    The parser's _strip_comment treats '#' and ';' as comment characters, which corrupts
    structure values like 'delimiter = ;' or 'comment = #'. We recover the raw values here.
    """
    in_structure = False
    result: dict[str, str] = {}
    for line in meta_lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('['):
            in_structure = stripped == '[structure]'
            continue
        if in_structure and '=' in stripped:
            key, _, raw_value = stripped.partition('=')
            key = key.strip()
            value = raw_value.strip()
            result[key] = value
    return result


def _csv_kwargs_from_metadata(
    metadata: MetadataDict,
    meta_lines: list[str],
) -> tuple[dict[str, Any], str | None]:
    """Extract csv.DictReader kwargs and comment char from [structure] metadata section."""
    # Use raw-parsed structure values to avoid comment-stripping corruption
    raw_structure = _parse_structure_raw(meta_lines)

    kwargs: dict[str, Any] = {}
    comment_char: str | None = None

    if "delimiter" in raw_structure:
        kwargs["delimiter"] = raw_structure["delimiter"]
    if "quotechar" in raw_structure:
        kwargs["quotechar"] = raw_structure["quotechar"]
    if "comment" in raw_structure:
        comment_char = raw_structure["comment"]

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

    base_kwargs, comment_char = _csv_kwargs_from_metadata(metadata, meta_lines)

    # Caller comment kwarg overrides structure metadata
    if "comment" in csv_kwargs:
        comment_char = str(csv_kwargs.pop("comment"))

    # Caller kwargs override structure metadata
    base_kwargs.update(csv_kwargs)

    with open(path, encoding="utf-8") as f:
        all_lines = f.readlines()

    csv_lines = all_lines[csv_start - 1:]

    if comment_char:
        csv_lines = [ln for ln in csv_lines if not ln.lstrip().startswith(comment_char)]

    reader = csv.DictReader(io.StringIO("".join(csv_lines)), **base_kwargs)
    rows = [dict(row) for row in reader]

    return IncFile(metadata=metadata, rows=rows, path=path)
