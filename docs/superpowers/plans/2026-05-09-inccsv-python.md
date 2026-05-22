# IncCSV Python Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `inccsv`, a Python library that reads and writes the INC file format (INI-style metadata header + CSV data body), interoperable with the Julia reference implementation at https://github.com/mroughan/IncCSV.jl.

**Architecture:** A pure-stdlib core (`_parser.py`, `_reader.py`, `_writer.py`) with optional pandas integration. The parser splits INC files into a metadata block (INI-style) and a CSV block, parses metadata into a nested `dict`, and delegates CSV I/O to Python's `csv` module. Schema validation and file summaries are separate modules.

**Tech Stack:** Python ≥ 3.9, stdlib only for core (`csv`, `re`, `unicodedata`, `dataclasses`); `pandas ≥ 1.3` as an optional dep; `pytest ≥ 7.0` for testing.

---

## File Map

| File | Responsibility |
|---|---|
| `pyproject.toml` | Package metadata, deps, pytest config |
| `inccsv/__init__.py` | Public re-exports |
| `inccsv/_parser.py` | Delimiter detection, `split_inc()`, `parse_metadata()`, `_parse_value()` |
| `inccsv/_reader.py` | `IncFile` dataclass, `read_inc()`, CSV-options mapping |
| `inccsv/_writer.py` | `write_inc()`, metadata serialisation |
| `inccsv/_schema.py` | `IncSchema`, `SchemaValidation`, `read_schema()`, `validate_schema()` |
| `inccsv/_summary.py` | `IncSummary`, `summarise()`, `print_summary()` |
| `tests/test_parser.py` | Unit tests for `_parser.py` |
| `tests/test_reader.py` | Unit tests for `_reader.py` |
| `tests/test_writer.py` | Unit tests for `_writer.py` |
| `tests/test_schema.py` | Unit tests for `_schema.py` |
| `tests/test_summary.py` | Unit tests for `_summary.py` |
| `tests/test_integration.py` | Roundtrip + pandas integration tests |

---

## Task 1: Package Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `inccsv/__init__.py`
- Create: `inccsv/_parser.py`
- Create: `inccsv/_reader.py`
- Create: `inccsv/_writer.py`
- Create: `inccsv/_schema.py`
- Create: `inccsv/_summary.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p inccsv tests
touch inccsv/__init__.py inccsv/_parser.py inccsv/_reader.py \
      inccsv/_writer.py inccsv/_schema.py inccsv/_summary.py \
      tests/__init__.py
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "inccsv"
version = "0.1.0"
description = "Python implementation of the INC file format (INI metadata + CSV data)"
requires-python = ">=3.9"
dependencies = []

[project.optional-dependencies]
pandas = ["pandas>=1.3"]
dev = ["pytest>=7.0", "pandas>=1.3"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 3: Install in editable mode**

```bash
pip install -e ".[dev]"
```

Expected: package installs without error; `python -c "import inccsv"` succeeds.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml inccsv/ tests/
git commit -m "chore: package scaffold for inccsv"
```

---

## Task 2: Metadata Parser (`_parser.py`)

**Files:**
- Modify: `inccsv/_parser.py`
- Create: `tests/test_parser.py`

### Background

An INC file looks like:

```
---
title = My Dataset
version = 1
[columns]
time = seconds
---
time,temperature
0,21.4
1,21.8
```

The opening `---` line is any sequence of 3+ Unicode "dash" characters (`Pd` category: `-`, `–`, `—`, etc.) optionally surrounded by whitespace, optionally followed by a `#` or `;` comment. The metadata block is everything between the first and second delimiter lines. If there is no opening delimiter, the file is treated as a plain CSV.

Metadata rules:
- `key = value` pairs at global scope or inside `[section]` blocks
- One level of nesting only
- Keys and section names must not contain `[`, `]`, `=`, `;`, `#`, or whitespace
- `#` and `;` introduce inline comments (stripped before parsing)
- Integer values (`^[+-]?\d+$`) are parsed as `int`; quoted values return `str`; all other values return `str`
- Duplicate keys or sections → `ValueError` with line number
- Empty sections (declared but no properties before next section or end of block) → `ValueError`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_parser.py
from __future__ import annotations
import pytest
from inccsv._parser import (
    _is_delimiter_line,
    _parse_value,
    split_inc,
    parse_metadata,
)


# --- _is_delimiter_line ---

def test_delimiter_three_hyphens():
    assert _is_delimiter_line("---\n") is True

def test_delimiter_four_hyphens():
    assert _is_delimiter_line("----") is True

def test_delimiter_with_leading_whitespace():
    assert _is_delimiter_line("  ---  \n") is True

def test_delimiter_with_hash_comment():
    assert _is_delimiter_line("--- # end of metadata\n") is True

def test_delimiter_with_semicolon_comment():
    assert _is_delimiter_line("--- ; comment\n") is True

def test_delimiter_unicode_en_dashes():
    assert _is_delimiter_line("–––\n") is True  # en-dashes

def test_delimiter_unicode_em_dashes():
    assert _is_delimiter_line("———\n") is True  # em-dashes

def test_delimiter_too_short():
    assert _is_delimiter_line("--\n") is False

def test_delimiter_not_dashes():
    assert _is_delimiter_line("key = value\n") is False

def test_delimiter_dashes_then_junk():
    assert _is_delimiter_line("--- not a comment marker\n") is False


# --- _parse_value ---

def test_parse_value_int():
    result = _parse_value("42")
    assert result == 42
    assert isinstance(result, int)

def test_parse_value_negative_int():
    assert _parse_value("-5") == -5

def test_parse_value_positive_sign_int():
    assert _parse_value("+7") == 7

def test_parse_value_plain_string():
    assert _parse_value("hello world") == "hello world"
    assert isinstance(_parse_value("hello world"), str)

def test_parse_value_quoted_string():
    result = _parse_value('"hello world"')
    assert result == "hello world"
    assert isinstance(result, str)

def test_parse_value_quoted_integer_stays_string():
    result = _parse_value('"42"')
    assert result == "42"
    assert isinstance(result, str)

def test_parse_value_escape_quote():
    assert _parse_value(r'"say \"hi\""') == 'say "hi"'

def test_parse_value_escape_backslash():
    assert _parse_value(r'"back\\slash"') == "back\\slash"

def test_parse_value_empty_string():
    assert _parse_value("") == ""

def test_parse_value_leading_whitespace_stripped():
    assert _parse_value("  hello  ") == "hello"


# --- split_inc ---

def test_split_inc_plain_csv(tmp_path):
    f = tmp_path / "plain.csv"
    f.write_text("name,score\nAda,10\n", encoding="utf-8")
    lines, start = split_inc(str(f))
    assert lines == []
    assert start == 1

def test_split_inc_with_metadata(tmp_path):
    f = tmp_path / "data.inc"
    f.write_text("---\ntitle = Test\n---\nname,score\nAda,10\n", encoding="utf-8")
    lines, start = split_inc(str(f))
    assert lines == ["title = Test"]
    assert start == 4  # "name,score" is line 4

def test_split_inc_empty_metadata_block(tmp_path):
    f = tmp_path / "empty.inc"
    f.write_text("---\n---\nname,score\nAda,10\n", encoding="utf-8")
    lines, start = split_inc(str(f))
    assert lines == []
    assert start == 3

def test_split_inc_missing_closing_delimiter(tmp_path):
    f = tmp_path / "bad.inc"
    f.write_text("---\ntitle = Test\n", encoding="utf-8")
    with pytest.raises(ValueError, match="closing delimiter"):
        split_inc(str(f))

def test_split_inc_delimiter_comment_ignored(tmp_path):
    f = tmp_path / "data.inc"
    f.write_text("--- # start\ntitle = Test\n--- # end\nname,score\n", encoding="utf-8")
    lines, start = split_inc(str(f))
    assert lines == ["title = Test"]
    assert start == 4


# --- parse_metadata ---

def test_parse_metadata_global_keys():
    result = parse_metadata(["title = My Data", "version = 1"])
    assert result == {"title": "My Data", "version": 1}

def test_parse_metadata_section():
    result = parse_metadata(["[columns]", "time = seconds", "temp = Celsius"])
    assert result == {"columns": {"time": "seconds", "temp": "Celsius"}}

def test_parse_metadata_global_and_section():
    result = parse_metadata(["title = Test", "[columns]", "x = meters"])
    assert result == {"title": "Test", "columns": {"x": "meters"}}

def test_parse_metadata_int_value():
    result = parse_metadata(["version = 42"])
    assert result["version"] == 42
    assert isinstance(result["version"], int)

def test_parse_metadata_quoted_int_stays_string():
    result = parse_metadata(['id = "007"'])
    assert result["id"] == "007"
    assert isinstance(result["id"], str)

def test_parse_metadata_comments_stripped():
    result = parse_metadata(["# full line comment", "title = Test # inline"])
    assert result == {"title": "Test"}

def test_parse_metadata_blank_lines_ignored():
    result = parse_metadata(["", "title = Test", ""])
    assert result == {"title": "Test"}

def test_parse_metadata_whitespace_around_key_value():
    result = parse_metadata(["  title   =   My Data  "])
    assert result == {"title": "My Data"}

def test_parse_metadata_duplicate_global_key_raises():
    with pytest.raises(ValueError, match="duplicate key"):
        parse_metadata(["title = A", "title = B"])

def test_parse_metadata_duplicate_section_raises():
    with pytest.raises(ValueError, match="duplicate section"):
        parse_metadata(["[columns]", "x = 1", "[columns]", "y = 2"])

def test_parse_metadata_duplicate_key_in_section_raises():
    with pytest.raises(ValueError, match="duplicate key"):
        parse_metadata(["[columns]", "time = seconds", "time = minutes"])

def test_parse_metadata_invalid_key_characters_raises():
    with pytest.raises(ValueError, match="invalid characters"):
        parse_metadata(["bad key = value"])

def test_parse_metadata_invalid_section_name_raises():
    with pytest.raises(ValueError, match="invalid characters"):
        parse_metadata(["[bad section]", "x = 1"])

def test_parse_metadata_empty_section_raises():
    with pytest.raises(ValueError, match="empty"):
        parse_metadata(["[columns]", "[structure]", "delimiter = ,"])

def test_parse_metadata_empty_last_section_raises():
    with pytest.raises(ValueError, match="empty"):
        parse_metadata(["[columns]"])

def test_parse_metadata_error_includes_line_number():
    with pytest.raises(ValueError, match="2"):  # line 2
        parse_metadata(["title = A", "title = B"])
```

- [ ] **Step 2: Run tests to verify they all fail**

```bash
pytest tests/test_parser.py -v 2>&1 | head -30
```

Expected: `ImportError` or `AttributeError` — functions don't exist yet.

- [ ] **Step 3: Implement `inccsv/_parser.py`**

```python
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
    """Strip trailing # or ; comment from a line, respecting quoted strings."""
    in_quote = False
    for i, ch in enumerate(line):
        if ch == '"':
            in_quote = not in_quote
        elif ch in '#;' and not in_quote:
            return line[:i].rstrip()
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
            return meta_lines, i + 1

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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_parser.py -v
```

Expected: all tests pass. Fix any failures before continuing.

- [ ] **Step 5: Commit**

```bash
git add inccsv/_parser.py tests/test_parser.py
git commit -m "feat: metadata parser (split_inc, parse_metadata)"
```

---

## Task 3: IncFile Reader (`_reader.py`)

**Files:**
- Modify: `inccsv/_reader.py`
- Create: `tests/test_reader.py`

### Background

`read_inc(path, **csv_kwargs)` reads an INC or plain CSV file and returns an `IncFile`. The `[structure]` metadata section maps to `csv.DictReader` kwargs:

| `[structure]` key | csv.reader kwarg |
|---|---|
| `delimiter` | `delimiter` |
| `quotechar` | `quotechar` |
| `comment` | manual pre-filter (not a csv kwarg) |

Caller-supplied `**csv_kwargs` override `[structure]` values. The `comment` key is consumed for line filtering and never passed to `csv.DictReader`.

`IncFile.rows` returns `list[dict[str, str]]` (all CSV values as strings). `IncFile.to_dataframe()` converts to a pandas DataFrame (pandas must be installed).

- [ ] **Step 1: Write failing tests**

```python
# tests/test_reader.py
from __future__ import annotations
import pytest
from inccsv._reader import IncFile, read_inc


def write_file(tmp_path, name: str, content: str) -> str:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return str(p)


# --- IncFile ---

def test_incfile_metadata_attribute():
    f = IncFile(metadata={"title": "T"}, rows=[{"a": "1"}], path=None)
    assert f.metadata == {"title": "T"}

def test_incfile_rows_attribute():
    f = IncFile(metadata={}, rows=[{"a": "1"}], path=None)
    assert f.rows == [{"a": "1"}]

def test_incfile_to_dataframe_requires_pandas():
    pytest.importorskip("pandas")
    f = IncFile(metadata={}, rows=[{"a": "1", "b": "2"}], path=None)
    df = f.to_dataframe()
    assert list(df.columns) == ["a", "b"]
    assert df.shape == (1, 2)


# --- read_inc plain CSV ---

def test_read_plain_csv(tmp_path):
    path = write_file(tmp_path, "data.csv", "name,score\nAda,10\nBabbage,12\n")
    result = read_inc(path)
    assert result.metadata == {}
    assert result.rows == [{"name": "Ada", "score": "10"}, {"name": "Babbage", "score": "12"}]

def test_read_plain_csv_stores_path(tmp_path):
    path = write_file(tmp_path, "data.csv", "name,score\nAda,10\n")
    result = read_inc(path)
    assert result.path == path


# --- read_inc with metadata ---

def test_read_inc_basic_metadata(tmp_path):
    content = "---\ntitle = My Data\nversion = 1\n---\nname,score\nAda,10\n"
    path = write_file(tmp_path, "data.inc", content)
    result = read_inc(path)
    assert result.metadata["title"] == "My Data"
    assert result.metadata["version"] == 1
    assert result.rows == [{"name": "Ada", "score": "10"}]

def test_read_inc_section_metadata(tmp_path):
    content = "---\n[columns]\ntime = seconds\n---\ntime,temp\n0,21.4\n"
    path = write_file(tmp_path, "data.inc", content)
    result = read_inc(path)
    assert result.metadata["columns"]["time"] == "seconds"


# --- structure section kwargs ---

def test_read_inc_semicolon_delimiter_from_structure(tmp_path):
    content = "---\n[structure]\ndelimiter = ;\n---\nname;score\nAda;10\n"
    path = write_file(tmp_path, "data.inc", content)
    result = read_inc(path)
    assert result.rows == [{"name": "Ada", "score": "10"}]

def test_read_inc_caller_kwargs_override_structure(tmp_path):
    content = "---\n[structure]\ndelimiter = ;\n---\nname|score\nAda|10\n"
    path = write_file(tmp_path, "data.inc", content)
    # caller says "|", overriding the ";" in [structure]
    result = read_inc(path, delimiter="|")
    assert result.rows == [{"name": "Ada", "score": "10"}]

def test_read_inc_comment_filter(tmp_path):
    content = "---\n[structure]\ncomment = #\n---\nname,score\n# this is a comment\nAda,10\n"
    path = write_file(tmp_path, "data.inc", content)
    result = read_inc(path)
    assert len(result.rows) == 1
    assert result.rows[0]["name"] == "Ada"

def test_read_inc_caller_comment_kwarg(tmp_path):
    content = "---\n---\nname,score\n# comment\nAda,10\n"
    path = write_file(tmp_path, "data.inc", content)
    result = read_inc(path, comment="#")
    assert len(result.rows) == 1


# --- unicode ---

def test_read_inc_unicode_metadata(tmp_path):
    content = "---\ntitle = Données\n---\nnom,valeur\nAlice,42\n"
    path = write_file(tmp_path, "unicode.inc", content)
    result = read_inc(path)
    assert result.metadata["title"] == "Données"
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_reader.py -v 2>&1 | head -20
```

Expected: `ImportError` — `_reader.py` is empty.

- [ ] **Step 3: Implement `inccsv/_reader.py`**

```python
# inccsv/_reader.py
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
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


def _csv_kwargs_from_metadata(metadata: MetadataDict) -> dict[str, Any]:
    """Extract csv.DictReader kwargs and comment char from [structure] metadata section."""
    structure = metadata.get("structure", {})
    kwargs: dict[str, Any] = {}
    comment_char: str | None = None
    if isinstance(structure, dict):
        if "delimiter" in structure:
            kwargs["delimiter"] = str(structure["delimiter"])
        if "quotechar" in structure:
            kwargs["quotechar"] = str(structure["quotechar"])
        if "comment" in structure:
            comment_char = str(structure["comment"])
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_reader.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add inccsv/_reader.py tests/test_reader.py
git commit -m "feat: IncFile dataclass and read_inc"
```

---

## Task 4: Writer (`_writer.py`)

**Files:**
- Modify: `inccsv/_writer.py`
- Create: `tests/test_writer.py`

### Background

`write_inc(path, rows, metadata=None, **csv_kwargs)` writes an INC file with a `---` / `---` delimited metadata block followed by CSV rows. Rules:
- Metadata values must be `int` or `str`; floats, lists, etc. raise `ValueError`
- String values that look like integers (`^[+-]?\d+$`), are empty, have leading/trailing whitespace, or contain `"` or `\` are written quoted
- All other strings are written unquoted
- Global keys are written before sections
- Empty sections raise `ValueError`
- Newlines in string values raise `ValueError`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_writer.py
from __future__ import annotations
import pytest
from inccsv._writer import write_inc
from inccsv._reader import read_inc


def test_write_basic_roundtrip(tmp_path):
    path = str(tmp_path / "out.inc")
    rows = [{"name": "Ada", "score": "10"}, {"name": "Babbage", "score": "12"}]
    metadata = {"title": "My Data", "version": 1}
    write_inc(path, rows, metadata=metadata)
    result = read_inc(path)
    assert result.metadata["title"] == "My Data"
    assert result.metadata["version"] == 1
    assert result.rows == rows

def test_write_empty_metadata(tmp_path):
    path = str(tmp_path / "out.inc")
    rows = [{"x": "1"}]
    write_inc(path, rows, metadata={})
    result = read_inc(path)
    assert result.metadata == {}
    assert result.rows == [{"x": "1"}]

def test_write_with_section(tmp_path):
    path = str(tmp_path / "out.inc")
    rows = [{"time": "0", "temp": "21.4"}]
    metadata = {"title": "Sensor Data", "columns": {"time": "seconds", "temp": "Celsius"}}
    write_inc(path, rows, metadata=metadata)
    result = read_inc(path)
    assert result.metadata["columns"]["time"] == "seconds"
    assert result.rows == rows

def test_write_string_that_looks_like_int_is_quoted(tmp_path):
    path = str(tmp_path / "out.inc")
    rows = [{"x": "1"}]
    # '42' as a Python str must survive roundtrip as str, not become int 42
    write_inc(path, rows, metadata={"id": "42"})
    result = read_inc(path)
    assert result.metadata["id"] == "42"
    assert isinstance(result.metadata["id"], str)

def test_write_string_with_quotes_escaped(tmp_path):
    path = str(tmp_path / "out.inc")
    rows = [{"x": "1"}]
    write_inc(path, rows, metadata={"note": 'say "hi"'})
    result = read_inc(path)
    assert result.metadata["note"] == 'say "hi"'

def test_write_invalid_float_raises():
    import io
    with pytest.raises(ValueError, match="int or str"):
        write_inc("/dev/null", [{"x": "1"}], metadata={"bad": 3.14})

def test_write_invalid_list_raises():
    with pytest.raises(ValueError, match="int or str"):
        write_inc("/dev/null", [{"x": "1"}], metadata={"bad": [1, 2]})

def test_write_empty_section_raises():
    with pytest.raises(ValueError, match="empty"):
        write_inc("/dev/null", [{"x": "1"}], metadata={"columns": {}})

def test_write_newline_in_value_raises():
    with pytest.raises(ValueError, match="newline"):
        write_inc("/dev/null", [{"x": "1"}], metadata={"bad": "line1\nline2"})

def test_write_custom_delimiter(tmp_path):
    path = str(tmp_path / "out.inc")
    rows = [{"name": "Ada", "score": "10"}]
    write_inc(path, rows, metadata={}, delimiter=";")
    # Read back with explicit delimiter since no [structure] section was written
    result = read_inc(path, delimiter=";")
    assert result.rows == [{"name": "Ada", "score": "10"}]

def test_write_no_rows(tmp_path):
    path = str(tmp_path / "out.inc")
    write_inc(path, [], metadata={"title": "Empty"})
    result = read_inc(path)
    assert result.metadata["title"] == "Empty"
    assert result.rows == []
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_writer.py -v 2>&1 | head -20
```

Expected: `ImportError` — `_writer.py` is empty.

- [ ] **Step 3: Implement `inccsv/_writer.py`**

```python
# inccsv/_writer.py
from __future__ import annotations

import csv
import re
from typing import Any

from ._parser import MetadataDict, MetadataValue

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
        rows: List of dicts representing CSV rows. Values are converted to str by csv.DictWriter.
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
            writer = csv.DictWriter(
                f, fieldnames=fieldnames, lineterminator='\n', **csv_kwargs
            )
            writer.writeheader()
            writer.writerows(rows)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_writer.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add inccsv/_writer.py tests/test_writer.py
git commit -m "feat: write_inc with metadata serialisation"
```

---

## Task 5: Schema Validation (`_schema.py`)

**Files:**
- Modify: `inccsv/_schema.py`
- Create: `tests/test_schema.py`

### Background

A schema is itself an INC file. It declares required fields (`[MUST]`), optional fields (`[MAYBE]`), and whether extra fields are allowed (`[schema]` section with `allow_extra = false`). The schema describes only **global-scope** metadata keys (not section contents).

Schema file example:
```
---
[schema]
allow_extra = false

[MUST]
title = String
version = Int

[MAYBE]
author = String
---
```

`validate_schema(file, schema)` checks an `IncFile`'s global metadata keys against the schema. It returns `SchemaValidation(valid, missing, extra)`.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_schema.py
from __future__ import annotations
import pytest
from inccsv._schema import IncSchema, SchemaValidation, read_schema, validate_schema
from inccsv._reader import IncFile


def make_schema_file(tmp_path, content: str) -> str:
    p = tmp_path / "schema.inc"
    p.write_text(content, encoding="utf-8")
    return str(p)


# --- IncSchema ---

def test_incschema_defaults():
    s = IncSchema(must={}, maybe={})
    assert s.allow_extra is True
    assert s.description == {}


# --- read_schema ---

def test_read_schema_must_fields(tmp_path):
    content = "---\n[MUST]\ntitle = String\nversion = Int\n---\n"
    path = make_schema_file(tmp_path, content)
    schema = read_schema(path)
    assert schema.must == {"title": "String", "version": "Int"}

def test_read_schema_maybe_fields(tmp_path):
    content = "---\n[MAYBE]\nauthor = String\n---\n"
    path = make_schema_file(tmp_path, content)
    schema = read_schema(path)
    assert schema.maybe == {"author": "String"}

def test_read_schema_allow_extra_false(tmp_path):
    content = "---\n[schema]\nallow_extra = false\n[MUST]\ntitle = String\n---\n"
    path = make_schema_file(tmp_path, content)
    schema = read_schema(path)
    assert schema.allow_extra is False

def test_read_schema_allow_extra_true_by_default(tmp_path):
    content = "---\n[MUST]\ntitle = String\n---\n"
    path = make_schema_file(tmp_path, content)
    schema = read_schema(path)
    assert schema.allow_extra is True

def test_read_schema_description(tmp_path):
    content = "---\n[MUST]\ntitle = String\n[description]\ntitle = The dataset title\n---\n"
    path = make_schema_file(tmp_path, content)
    schema = read_schema(path)
    assert schema.description == {"title": "The dataset title"}

def test_read_schema_empty_schema_file(tmp_path):
    content = "---\n---\n"
    path = make_schema_file(tmp_path, content)
    schema = read_schema(path)
    assert schema.must == {}
    assert schema.maybe == {}
    assert schema.allow_extra is True


# --- validate_schema ---

def make_file(metadata: dict) -> IncFile:
    return IncFile(metadata=metadata, rows=[], path=None)

def test_validate_all_must_present():
    schema = IncSchema(must={"title": "String", "version": "Int"}, maybe={})
    f = make_file({"title": "Test", "version": 1})
    result = validate_schema(f, schema)
    assert result.valid is True
    assert result.missing == []
    assert result.extra == []

def test_validate_missing_required_field():
    schema = IncSchema(must={"title": "String", "version": "Int"}, maybe={})
    f = make_file({"title": "Test"})
    result = validate_schema(f, schema)
    assert result.valid is False
    assert "version" in result.missing

def test_validate_extra_field_allowed_by_default():
    schema = IncSchema(must={"title": "String"}, maybe={})
    f = make_file({"title": "Test", "extra_key": "value"})
    result = validate_schema(f, schema)
    assert result.valid is True
    assert "extra_key" in result.extra

def test_validate_extra_field_rejected_when_not_allowed():
    schema = IncSchema(must={"title": "String"}, maybe={}, allow_extra=False)
    f = make_file({"title": "Test", "extra_key": "value"})
    result = validate_schema(f, schema)
    assert result.valid is False
    assert "extra_key" in result.extra

def test_validate_maybe_field_not_required():
    schema = IncSchema(must={"title": "String"}, maybe={"author": "String"})
    f = make_file({"title": "Test"})  # author missing but it's MAYBE
    result = validate_schema(f, schema)
    assert result.valid is True
    assert result.missing == []

def test_validate_maybe_field_not_counted_as_extra():
    schema = IncSchema(must={}, maybe={"author": "String"})
    f = make_file({"author": "Ada"})
    result = validate_schema(f, schema)
    assert result.valid is True
    assert result.extra == []

def test_validate_empty_file_against_must_schema():
    schema = IncSchema(must={"title": "String"}, maybe={})
    f = make_file({})
    result = validate_schema(f, schema)
    assert result.valid is False
    assert "title" in result.missing

def test_validate_schema_ignores_section_keys():
    """Section contents are not checked against the schema — only global keys."""
    schema = IncSchema(must={"title": "String"}, maybe={}, allow_extra=False)
    f = make_file({"title": "Test", "columns": {"time": "seconds"}})
    result = validate_schema(f, schema)
    # "columns" section should not be counted as an "extra" global key
    assert result.valid is True
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_schema.py -v 2>&1 | head -20
```

Expected: `ImportError`.

- [ ] **Step 3: Implement `inccsv/_schema.py`**

```python
# inccsv/_schema.py
from __future__ import annotations

from dataclasses import dataclass, field

from ._parser import MetadataDict
from ._reader import IncFile, read_inc


@dataclass
class SchemaValidation:
    valid: bool
    missing: list[str]
    extra: list[str]


@dataclass
class IncSchema:
    must: dict[str, str]
    maybe: dict[str, str]
    allow_extra: bool = True
    description: dict[str, str] = field(default_factory=dict)


def read_schema(path: str) -> IncSchema:
    """Read a schema definition from an INC file."""
    inc = read_inc(path)
    meta = inc.metadata

    allow_extra = True
    schema_section = meta.get("schema", {})
    if isinstance(schema_section, dict):
        ae_raw = schema_section.get("allow_extra", "true")
        allow_extra = str(ae_raw).lower() not in ("false", "0", "no")

    must: dict[str, str] = {}
    must_section = meta.get("MUST", {})
    if isinstance(must_section, dict):
        must = {k: str(v) for k, v in must_section.items()}

    maybe: dict[str, str] = {}
    maybe_section = meta.get("MAYBE", {})
    if isinstance(maybe_section, dict):
        maybe = {k: str(v) for k, v in maybe_section.items()}

    description: dict[str, str] = {}
    desc_section = meta.get("description", {})
    if isinstance(desc_section, dict):
        description = {k: str(v) for k, v in desc_section.items()}

    return IncSchema(must=must, maybe=maybe, allow_extra=allow_extra, description=description)


def validate_schema(file: IncFile, schema: IncSchema) -> SchemaValidation:
    """
    Validate an IncFile's global metadata keys against a schema.

    Only top-level scalar keys (not section dicts) are compared to the schema.
    """
    file_keys: set[str] = {
        k for k, v in file.metadata.items() if not isinstance(v, dict)
    }
    schema_keys = set(schema.must) | set(schema.maybe)

    missing = [k for k in schema.must if k not in file_keys]
    extra = [k for k in sorted(file_keys) if k not in schema_keys]

    valid = not missing and (schema.allow_extra or not extra)

    return SchemaValidation(valid=valid, missing=missing, extra=extra)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_schema.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add inccsv/_schema.py tests/test_schema.py
git commit -m "feat: schema validation (read_schema, validate_schema)"
```

---

## Task 6: Summary (`_summary.py`)

**Files:**
- Modify: `inccsv/_summary.py`
- Create: `tests/test_summary.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_summary.py
from __future__ import annotations
import pytest
from inccsv._summary import IncSummary, summarise, print_summary
from inccsv._reader import IncFile


def make_file(metadata: dict, rows: list[dict]) -> IncFile:
    return IncFile(metadata=metadata, rows=rows, path="/data/test.inc")


def test_summarise_row_and_col_counts():
    f = make_file({}, [{"a": "1", "b": "2"}, {"a": "3", "b": "4"}])
    s = summarise(f)
    assert s.n_rows == 2
    assert s.n_cols == 2

def test_summarise_columns():
    f = make_file({}, [{"time": "0", "temp": "21.4"}])
    s = summarise(f)
    assert s.columns == ["time", "temp"]

def test_summarise_empty_rows():
    f = make_file({}, [])
    s = summarise(f)
    assert s.n_rows == 0
    assert s.n_cols == 0
    assert s.columns == []

def test_summarise_metadata_key_count():
    f = make_file({"title": "T", "version": 1}, [{"x": "1"}])
    s = summarise(f)
    assert s.n_metadata_keys == 2

def test_summarise_section_keys_counted():
    f = make_file({"columns": {"time": "seconds", "temp": "Celsius"}}, [{"x": "1"}])
    s = summarise(f)
    assert s.n_metadata_keys == 2  # 2 keys inside the section
    assert s.sections == ["columns"]

def test_summarise_path():
    f = make_file({}, [{"x": "1"}])
    s = summarise(f)
    assert s.path == "/data/test.inc"

def test_summarise_returns_incSummary():
    f = make_file({}, [{"x": "1"}])
    assert isinstance(summarise(f), IncSummary)

def test_print_summary_includes_row_count(capsys):
    f = make_file({"title": "T"}, [{"x": "1"}, {"x": "2"}])
    print_summary(f)
    captured = capsys.readouterr()
    assert "2" in captured.out

def test_print_summary_includes_columns(capsys):
    f = make_file({}, [{"time": "0", "temp": "21.4"}])
    print_summary(f)
    captured = capsys.readouterr()
    assert "time" in captured.out
    assert "temp" in captured.out
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_summary.py -v 2>&1 | head -20
```

Expected: `ImportError`.

- [ ] **Step 3: Implement `inccsv/_summary.py`**

```python
# inccsv/_summary.py
from __future__ import annotations

from dataclasses import dataclass

from ._reader import IncFile


@dataclass
class IncSummary:
    path: str | None
    n_rows: int
    n_cols: int
    columns: list[str]
    n_metadata_keys: int
    sections: list[str]


def summarise(file: IncFile) -> IncSummary:
    """Generate a summary of an IncFile."""
    columns = list(file.rows[0].keys()) if file.rows else []
    n_metadata_keys = 0
    sections: list[str] = []

    for k, v in file.metadata.items():
        if isinstance(v, dict):
            sections.append(k)
            n_metadata_keys += len(v)
        else:
            n_metadata_keys += 1

    return IncSummary(
        path=file.path,
        n_rows=len(file.rows),
        n_cols=len(columns),
        columns=columns,
        n_metadata_keys=n_metadata_keys,
        sections=sections,
    )


def print_summary(file: IncFile) -> None:
    """Print a human-readable summary of an IncFile to stdout."""
    s = summarise(file)
    print(f"File:     {s.path or '(unknown)'}")
    print(f"Rows:     {s.n_rows}")
    print(f"Columns:  {s.n_cols}")
    if s.columns:
        print(f"  Names: {', '.join(s.columns)}")
    print(f"Metadata keys: {s.n_metadata_keys}")
    if s.sections:
        print(f"  Sections: {', '.join(s.sections)}")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_summary.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add inccsv/_summary.py tests/test_summary.py
git commit -m "feat: IncSummary, summarise, print_summary"
```

---

## Task 7: Public API + Integration Tests

**Files:**
- Modify: `inccsv/__init__.py`
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write failing integration tests**

```python
# tests/test_integration.py
from __future__ import annotations
import pytest
import inccsv


# --- Public API surface ---

def test_public_exports():
    assert hasattr(inccsv, 'read_inc')
    assert hasattr(inccsv, 'write_inc')
    assert hasattr(inccsv, 'read_schema')
    assert hasattr(inccsv, 'validate_schema')
    assert hasattr(inccsv, 'summarise')
    assert hasattr(inccsv, 'print_summary')
    assert hasattr(inccsv, 'IncFile')
    assert hasattr(inccsv, 'IncSchema')
    assert hasattr(inccsv, 'SchemaValidation')
    assert hasattr(inccsv, 'IncSummary')


# --- Full roundtrip ---

def test_full_roundtrip(tmp_path):
    original_rows = [
        {"time": "0.000", "customers": "1", "event": "Arrival"},
        {"time": "0.203", "customers": "2", "event": "Arrival"},
        {"time": "0.431", "customers": "1", "event": "Departure"},
    ]
    original_metadata = {
        "filename": "simulation_1.inc",
        "source": "simulation",
        "version": 1,
        "parameters": {"seed": 100, "lambda": 2},
        "columns": {"time": "seconds", "customers": "count", "event": "type"},
    }
    path = str(tmp_path / "sim.inc")
    inccsv.write_inc(path, original_rows, metadata=original_metadata)
    result = inccsv.read_inc(path)

    assert result.metadata["filename"] == "simulation_1.inc"
    assert result.metadata["source"] == "simulation"
    assert result.metadata["version"] == 1
    assert result.metadata["parameters"]["seed"] == 100
    assert result.metadata["columns"]["time"] == "seconds"
    assert result.rows == original_rows


# --- Schema validation roundtrip ---

def test_schema_validation_roundtrip(tmp_path):
    schema_content = (
        "---\n"
        "[schema]\n"
        "allow_extra = false\n"
        "[MUST]\n"
        "title = String\n"
        "version = Int\n"
        "[MAYBE]\n"
        "author = String\n"
        "---\n"
    )
    schema_path = str(tmp_path / "schema.inc")
    (tmp_path / "schema.inc").write_text(schema_content, encoding="utf-8")
    schema = inccsv.read_schema(schema_path)

    # Valid file
    f_valid = inccsv.IncFile(
        metadata={"title": "Test", "version": 1}, rows=[], path=None
    )
    result = inccsv.validate_schema(f_valid, schema)
    assert result.valid is True

    # Missing required field
    f_missing = inccsv.IncFile(metadata={"title": "Test"}, rows=[], path=None)
    result = inccsv.validate_schema(f_missing, schema)
    assert result.valid is False
    assert "version" in result.missing

    # Extra field rejected
    f_extra = inccsv.IncFile(
        metadata={"title": "Test", "version": 1, "extra": "x"}, rows=[], path=None
    )
    result = inccsv.validate_schema(f_extra, schema)
    assert result.valid is False
    assert "extra" in result.extra


# --- Summary integration ---

def test_summarise_via_public_api(tmp_path):
    path = str(tmp_path / "data.inc")
    (tmp_path / "data.inc").write_text(
        "---\ntitle = Test\n[columns]\ntime = seconds\n---\ntime,temp\n0,21\n1,22\n",
        encoding="utf-8",
    )
    f = inccsv.read_inc(path)
    s = inccsv.summarise(f)
    assert s.n_rows == 2
    assert s.n_cols == 2
    assert s.n_metadata_keys == 2  # 1 global + 1 in [columns]
    assert "columns" in s.sections


# --- pandas integration ---

def test_to_dataframe(tmp_path):
    pd = pytest.importorskip("pandas")
    path = str(tmp_path / "data.inc")
    (tmp_path / "data.inc").write_text(
        "---\ntitle = Test\n---\nname,score\nAda,10\nBabbage,12\n",
        encoding="utf-8",
    )
    f = inccsv.read_inc(path)
    df = f.to_dataframe()
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["name", "score"]
    assert len(df) == 2
    assert df.iloc[0]["name"] == "Ada"


# --- backward compat: plain CSV readable ---

def test_plain_csv_readable(tmp_path):
    path = str(tmp_path / "plain.csv")
    (tmp_path / "plain.csv").write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
    f = inccsv.read_inc(path)
    assert f.metadata == {}
    assert len(f.rows) == 2


# --- unicode ---

def test_unicode_metadata_and_data_roundtrip(tmp_path):
    path = str(tmp_path / "unicode.inc")
    rows = [{"nom": "Élise", "valeur": "42"}]
    metadata = {"titre": "Données expérimentales", "auteur": "Müller"}
    inccsv.write_inc(path, rows, metadata=metadata)
    result = inccsv.read_inc(path)
    assert result.metadata["titre"] == "Données expérimentales"
    assert result.rows[0]["nom"] == "Élise"
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_integration.py -v 2>&1 | head -20
```

Expected: `AttributeError: module 'inccsv' has no attribute 'read_inc'` (public API not wired up yet).

- [ ] **Step 3: Implement `inccsv/__init__.py`**

```python
# inccsv/__init__.py
from ._reader import IncFile, read_inc
from ._writer import write_inc
from ._schema import IncSchema, SchemaValidation, read_schema, validate_schema
from ._summary import IncSummary, summarise, print_summary

__all__ = [
    "IncFile",
    "read_inc",
    "write_inc",
    "IncSchema",
    "SchemaValidation",
    "read_schema",
    "validate_schema",
    "IncSummary",
    "summarise",
    "print_summary",
]
```

- [ ] **Step 4: Run the full test suite**

```bash
pytest -v
```

Expected: all tests pass across all files. If any fail, fix before committing.

- [ ] **Step 5: Commit**

```bash
git add inccsv/__init__.py tests/test_integration.py
git commit -m "feat: public API and integration tests"
```

---

## Self-Review

### Spec coverage check

| Requirement | Task |
|---|---|
| Read INC file with metadata | Task 3 |
| Read plain CSV (no metadata) | Task 3 |
| Write INC file | Task 4 |
| Metadata as nested dict (global + sections) | Task 2 |
| Int inference for unquoted integers | Task 2 |
| Quoted values preserved as str | Task 2 |
| `[structure]` section maps to CSV kwargs | Task 3 |
| Caller kwargs override `[structure]` | Task 3 |
| Comment line filtering in CSV block | Task 3 |
| Strict errors (duplicate keys, invalid names, empty sections) | Task 2 |
| Missing closing delimiter error | Task 2 |
| Unicode delimiter lines (Pd category) | Task 2 |
| UTF-8 encoding throughout | Tasks 3, 4 |
| Schema validation (MUST/MAYBE/allow_extra) | Task 5 |
| File summary | Task 6 |
| Pandas DataFrame integration | Tasks 3, 7 |
| Roundtrip consistency | Task 7 |
| Public API surface | Task 7 |

All requirements covered. No placeholders.

### Type consistency check

- `MetadataDict` defined in `_parser.py`, imported in `_reader.py`, `_writer.py`, `_schema.py` ✓
- `IncFile` defined in `_reader.py`, imported in `_schema.py`, `_summary.py` ✓
- `_parse_value` returns `int | str`, consistent with `MetadataValue` ✓
- `write_inc` accepts `MetadataDict | None`, consistent with what `read_inc` produces ✓
- `validate_schema(file: IncFile, schema: IncSchema)` — both types used consistently ✓
