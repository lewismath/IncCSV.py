# inccsv/_reader.py
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Any

from ._parser import split_inc, parse_metadata, MetadataDict
from ._structure import structure_csv_kwargs, validate_structure_keys


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


def _csv_kwargs_from_metadata(metadata: MetadataDict) -> tuple[dict[str, Any], str | None, int, int]:
    """Extract csv.DictReader kwargs, comment char, header line, and footerskip from [structure]."""
    structure = metadata.get("structure", {})
    comment_char: str | None = None
    header: int = 1
    footerskip: int = 0
    kwargs: dict[str, Any] = structure_csv_kwargs(metadata)
    if isinstance(structure, dict):
        validate_structure_keys(structure)
        if "comment" in structure:
            comment_raw = structure["comment"]
            if not isinstance(comment_raw, str) or len(comment_raw) != 1:
                raise ValueError(
                    f"[structure].comment must be a single character string, got {comment_raw!r}"
                )
            comment_char = comment_raw
        if "header" in structure:
            val = structure["header"]
            if not isinstance(val, int):
                raise ValueError(
                    f"[structure].header must be an integer, got {val!r}"
                )
            header = val
        if "footerskip" in structure:
            val = structure["footerskip"]
            if not isinstance(val, int):
                raise ValueError(
                    f"[structure].footerskip must be an integer, got {val!r}"
                )
            footerskip = val
    return kwargs, comment_char, header, footerskip


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

    base_kwargs, comment_char, header, footerskip = _csv_kwargs_from_metadata(metadata)

    if "comment" in csv_kwargs:
        comment_char = str(csv_kwargs.pop("comment"))

    base_kwargs.update(csv_kwargs)

    with open(path, encoding="utf-8") as f:
        all_lines = f.readlines()

    csv_lines = all_lines[csv_start - 1:]
    csv_lines = csv_lines[max(0, header - 1):]  # discard lines before header (header is 1-based)

    if comment_char:
        csv_lines = [ln for ln in csv_lines if not ln.lstrip().startswith(comment_char)]

    reader = csv.DictReader(io.StringIO("".join(csv_lines)), **base_kwargs)
    rows = [dict(row) for row in reader]

    if footerskip > 0:
        rows = rows[:-footerskip]

    return IncFile(metadata=metadata, rows=rows, path=path)
