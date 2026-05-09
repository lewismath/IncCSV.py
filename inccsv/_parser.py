# inccsv/_parser.py
from __future__ import annotations

import re
import unicodedata
from typing import Union

MetadataValue = Union[int, str]
SectionDict = dict[str, MetadataValue]
MetadataDict = dict[str, Union[MetadataValue, SectionDict]]

_INVALID_NAME_RE = re.compile(r'[\[\]=#;\s]')
_INT_RE = re.compile(r'^[+-]?\d+$')


def _is_delimiter_line(line: str) -> bool:
    """Return True if line is a metadata delimiter (3+ Unicode Pd chars, optional whitespace/comment)."""
    s = line.rstrip('\n\r').lstrip()
    # Count leading dash characters (Unicode Pd category)
    i = 0
    while i < len(s) and unicodedata.category(s[i]) == 'Pd':
        i += 1
    if i < 3:
        return False
    rest = s[i:].lstrip()
    # After dashes: nothing, or a comment starting with # or ;
    return not rest or rest[0] in '#;'


def _strip_comment(line: str) -> str:
    """Strip trailing # or ; comment from a line, respecting quoted strings.

    A comment marker is only recognised if it either:
    - starts the line (after optional whitespace), or
    - is preceded by at least one non-whitespace character in the value part
      (i.e., after the first '=' on the line).
    This allows bare comment characters as values: `delimiter = ;` is preserved.
    """
    in_quote = False
    after_eq = False
    value_has_content = False
    for i, ch in enumerate(line):
        if ch == '"':
            in_quote = not in_quote
        elif not in_quote:
            if ch in '#;':
                # Strip if: full-line comment (not after =), OR value has some content before marker
                if not after_eq or value_has_content:
                    return line[:i].rstrip()
            elif ch == '=':
                after_eq = True
            elif after_eq and ch not in ' \t':
                value_has_content = True
    return line.rstrip()


def _parse_value(raw: str) -> MetadataValue:
    """Parse a raw value string into int or str."""
    v = raw.strip()
    if not v:
        return ''
    if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
        inner = v[1:-1]
        inner = inner.replace('\\"', '"').replace('\\\\', '\\')
        return inner
    if _INT_RE.match(v):
        return int(v)
    return v


def split_inc(path: str) -> tuple[list[str], int]:
    """
    Split an INC file into metadata lines and the CSV start line number (1-based).

    If no opening delimiter is found, returns ([], 1) — plain CSV fallback.

    Raises:
        ValueError: if an opening delimiter exists but no closing delimiter follows.
    """
    with open(path, encoding='utf-8') as f:
        lines = f.readlines()

    if not lines or not _is_delimiter_line(lines[0]):
        return [], 1

    for i, line in enumerate(lines[1:], start=1):
        if _is_delimiter_line(line):
            meta_lines = [ln.rstrip('\n\r') for ln in lines[1:i]]
            return meta_lines, i + 2

    raise ValueError(
        f"Opening delimiter found in '{path}' but closing delimiter is missing."
    )


def parse_metadata(lines: list[str]) -> MetadataDict:
    """
    Parse INI-style metadata lines into a nested dict.

    Top-level keys and section keys map to int or str values.
    Sections produce nested dicts.

    Raises:
        ValueError: on syntax errors, duplicate keys/sections, invalid names, empty sections.
    """
    result: MetadataDict = {}
    current_section: str | None = None
    seen_sections: dict[str, int] = {}
    seen_keys: dict[tuple[str | None, str], int] = {}
    section_start_lines: dict[str, int] = {}

    def _check_current_section_not_empty(at_lineno: int) -> None:
        if current_section is not None:
            sect = result.get(current_section)
            if isinstance(sect, dict) and not sect:
                raise ValueError(
                    f"Line {section_start_lines[current_section]}: "
                    f"section [{current_section}] is empty (no properties defined)"
                )

    for lineno, raw in enumerate(lines, start=1):
        line = _strip_comment(raw).strip()
        if not line:
            continue

        if line.startswith('['):
            _check_current_section_not_empty(lineno)
            if not line.endswith(']'):
                raise ValueError(f"Line {lineno}: malformed section header: {raw!r}")
            section_name = line[1:-1].strip()
            if not section_name:
                raise ValueError(f"Line {lineno}: empty section name")
            if _INVALID_NAME_RE.search(section_name):
                raise ValueError(
                    f"Line {lineno}: invalid characters in section name {section_name!r}"
                )
            if section_name in seen_sections:
                raise ValueError(
                    f"Line {lineno}: duplicate section [{section_name}] "
                    f"(first seen at line {seen_sections[section_name]})"
                )
            seen_sections[section_name] = lineno
            section_start_lines[section_name] = lineno
            result[section_name] = {}
            current_section = section_name
            continue

        if '=' not in line:
            raise ValueError(f"Line {lineno}: expected 'key = value', got: {raw!r}")

        key, _, raw_value = line.partition('=')
        key = key.strip()

        if not key:
            raise ValueError(f"Line {lineno}: empty key name")
        if _INVALID_NAME_RE.search(key):
            raise ValueError(
                f"Line {lineno}: invalid characters in key {key!r}"
            )

        scope = (current_section, key)
        if scope in seen_keys:
            raise ValueError(
                f"Line {lineno}: duplicate key {key!r} in "
                f"{'[' + current_section + ']' if current_section else 'global section'} "
                f"(first seen at line {seen_keys[scope]})"
            )
        seen_keys[scope] = lineno

        value = _parse_value(raw_value)

        if current_section is None:
            result[key] = value
        else:
            result[current_section][key] = value  # type: ignore[index]

    # Check last section
    _check_current_section_not_empty(len(lines) + 1)

    return result
