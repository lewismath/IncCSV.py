# inccsv/_writer.py
from __future__ import annotations

import csv
import re
from typing import Any

from ._parser import MetadataDict, _INVALID_NAME_RE
from ._structure import structure_write_kwargs

_INT_PATTERN = re.compile(r'^[+-]?\d+$')
# Characters that Julia's escape_value also quotes; quoting these prevents
# Julia's strip_comment from silently truncating Python-written values.
_NEEDS_QUOTE_CHARS = frozenset('#;=[]')


def _needs_quoting(s: str) -> bool:
    """Return True if string value must be quoted in INI output."""
    if not s:
        return True
    if s != s.strip():
        return True
    if '"' in s or '\\' in s:
        return True
    if _NEEDS_QUOTE_CHARS.intersection(s):
        return True
    if _INT_PATTERN.match(s):
        return True
    return False


def _format_value(value: int | str) -> str:
    """Serialise a metadata value to its INI representation."""
    if isinstance(value, int):
        return str(value)
    if '\n' in value or '\r' in value:
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


def _validate_name(name: str, context: str) -> None:
    if not name or _INVALID_NAME_RE.search(name):
        raise ValueError(f"Invalid metadata name {name!r} in {context}")


def _metadata_to_lines(metadata: MetadataDict) -> list[str]:
    """Serialise a metadata dict to INI lines (without delimiters)."""
    lines: list[str] = []

    scalar_keys = sorted(key for key, value in metadata.items() if not isinstance(value, dict))
    for key in scalar_keys:
        _validate_name(key, "top-level key")
        value = metadata[key]
        lines.append(f"{key} = {_validate_and_format(value, repr(key))}")

    section_keys = sorted(key for key, value in metadata.items() if isinstance(value, dict))
    for section in section_keys:
        _validate_name(section, "section name")
        content = metadata[section]
        if not content:
            raise ValueError(f"Section [{section}] is empty (no properties defined)")
        lines.append(f"[{section}]")
        for key in sorted(content):
            _validate_name(key, f"[{section}] key")
            value = content[key]
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
        **csv_kwargs: Forwarded to csv.DictWriter (e.g., delimiter=';'). Writer-relevant
                      [structure] metadata (delim/delimiter, quotechar, escapechar) is
                      applied automatically; an explicit kwarg here must agree with it.

    Raises:
        ValueError: if metadata contains invalid names, values, or empty sections,
            or if a csv_kwargs value contradicts [structure] metadata.
    """
    if metadata is None:
        metadata = {}

    csv_kwargs = structure_write_kwargs(metadata, csv_kwargs)
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
