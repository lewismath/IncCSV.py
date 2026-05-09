# inccsv/_writer.py
from __future__ import annotations

import csv
import re
from typing import Any

from ._parser import MetadataDict

_INT_PATTERN = re.compile(r'^[+-]?\d+$')


def _needs_quoting(s: str) -> bool:
    """Return True if string value must be quoted in INI output."""
    if not s:
        return True
    if s != s.strip():
        return True
    if '"' in s or '\\' in s:
        return True
    if _INT_PATTERN.match(s):
        return True
    return False


def _format_value(value: int | str) -> str:
    """Serialise a metadata value to its INI representation."""
    if isinstance(value, int):
        return str(value)
    if '\n' in value:
        raise ValueError(f"Metadata string value cannot contain newlines: {value!r}")
    if _needs_quoting(value):
        escaped = value.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _validate_and_format(value: Any, context: str) -> str:
    """Validate value type and return formatted string."""
    if isinstance(value, bool):
        raise ValueError(
            f"Metadata value at {context} must be int or str, "
            f"got bool: {value!r}"
        )
    if not isinstance(value, (int, str)):
        raise ValueError(
            f"Metadata value at {context} must be int or str, "
            f"got {type(value).__name__}: {value!r}"
        )
    return _format_value(value)


def _metadata_to_lines(metadata: MetadataDict) -> list[str]:
    """Serialise a metadata dict to INI lines (without delimiters)."""
    lines: list[str] = []

    # Global keys first
    for key, value in metadata.items():
        if not isinstance(value, dict):
            lines.append(f"{key} = {_validate_and_format(value, repr(key))}")

    # Sections
    for section, content in metadata.items():
        if isinstance(content, dict):
            if not content:
                raise ValueError(f"Section [{section}] is empty (no properties defined)")
            lines.append(f"[{section}]")
            for key, value in content.items():
                lines.append(
                    f"{key} = {_validate_and_format(value, f'[{section}].{key!r}')}"
                )

    return lines


def write_inc(
    path: str,
    rows: list[dict[str, Any]],
    metadata: MetadataDict | None = None,
    **csv_kwargs: Any,
) -> None:
    """
    Write an INC file with a metadata header block followed by CSV rows.

    Args:
        path: Output file path.
        rows: List of dicts representing CSV rows.
        metadata: Nested metadata dict. Values must be int or str.
        **csv_kwargs: Forwarded to csv.DictWriter (e.g., delimiter=';').

    Raises:
        ValueError: if metadata contains invalid values or empty sections.
    """
    if metadata is None:
        metadata = {}

    meta_lines = _metadata_to_lines(metadata)

    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write('---\n')
        for line in meta_lines:
            f.write(line + '\n')
        f.write('---\n')

        if rows:
            fieldnames = list(rows[0].keys())
            expected = set(fieldnames)
            for idx, row in enumerate(rows[1:], start=1):
                if set(row.keys()) != expected:
                    raise ValueError(
                        f"Row {idx} has different keys than row 0: "
                        f"expected {sorted(expected)}, got {sorted(row.keys())}"
                    )
            writer = csv.DictWriter(
                f, fieldnames=fieldnames, lineterminator='\n', **csv_kwargs
            )
            writer.writeheader()
            writer.writerows(rows)
