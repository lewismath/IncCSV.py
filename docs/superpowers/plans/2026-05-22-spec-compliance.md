# INC Spec Compliance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining interoperability gaps between IncCSV.py, IncCSV.jl, IncCSV.js, and the INCspec formal specification (v0.1.0-draft).

**Architecture:** Ten targeted changes across four files — `_writer.py`, `_reader.py`, `_parser.py`, `_schema.py` — plus a README update and a new fixture-based test suite that tracks all INCspec canonical test cases. Tasks are ordered so each one leaves the test suite green before the next begins. Tasks 3, 4, and 5 all touch `_reader.py`; complete them in order.

**Tech Stack:** Python 3.10+, stdlib `csv`/`re`/`unicodedata`, pytest. No new dependencies.

---

## File Map

| File | Changes |
|---|---|
| `inccsv/_writer.py` | Task 1: add `_validate_name`, call it from `_metadata_to_lines` |
| `inccsv/_schema.py` | Task 2: replace `_get_section` with `_merge_sections`; Task 6: validate path components |
| `inccsv/_reader.py` | Task 3: remove Julia-only structure keys; Task 4: `\t` alias + type validation; Task 5: apply `header`/`footerskip` |
| `inccsv/_parser.py` | Task 7: richer missing-delimiter error |
| `README.md` | Task 7: replace `[MAYBE]` with `[OPTIONAL]` |
| `tests/test_writer.py` | Tasks 1 |
| `tests/test_schema.py` | Tasks 2, 6 |
| `tests/test_reader.py` | Tasks 3, 4, 5 |
| `tests/test_parser.py` | Task 7 |
| `tests/fixtures/positive/*.inc` | Task 8: 11 new fixture files |
| `tests/fixtures/negative/*.inc` | Task 8: 10 new fixture files |
| `tests/fixtures/roundtrip/*.inc` | Task 8: 2 new fixture files |
| `tests/test_fixtures.py` | Task 8: new test module |

---

## Task 1: Writer Name Validation

**Files:**
- Modify: `inccsv/_writer.py`
- Test: `tests/test_writer.py`

The spec says writers MUST reject invalid metadata names. Currently `_metadata_to_lines` passes whatever key strings the caller supplies through to the file without checking them, allowing Python to write files that both Python and Julia then refuse to parse.

- [ ] **Step 1: Write the failing tests**

Add at the bottom of `tests/test_writer.py`:

```python
def test_write_invalid_top_level_key_raises():
    with pytest.raises(ValueError, match="[Ii]nvalid"):
        write_inc("/dev/null", [], metadata={"bad key": "v"})

def test_write_invalid_section_name_raises():
    with pytest.raises(ValueError, match="[Ii]nvalid"):
        write_inc("/dev/null", [], metadata={"bad section": {"k": "v"}})

def test_write_invalid_section_key_raises():
    with pytest.raises(ValueError, match="[Ii]nvalid"):
        write_inc("/dev/null", [], metadata={"section": {"bad key": "v"}})

def test_write_empty_key_name_raises():
    with pytest.raises(ValueError, match="[Ii]nvalid"):
        write_inc("/dev/null", [], metadata={"": "v"})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_writer.py::test_write_invalid_top_level_key_raises \
       tests/test_writer.py::test_write_invalid_section_name_raises \
       tests/test_writer.py::test_write_invalid_section_key_raises \
       tests/test_writer.py::test_write_empty_key_name_raises -v
```

Expected: 4 FAILED (no error raised currently).

- [ ] **Step 3: Implement name validation in `_writer.py`**

The updated full `inccsv/_writer.py`:

```python
# inccsv/_writer.py
from __future__ import annotations

import csv
import re
from typing import Any

from ._parser import MetadataDict, _INVALID_NAME_RE

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
        **csv_kwargs: Forwarded to csv.DictWriter (e.g., delimiter=';').

    Raises:
        ValueError: if metadata contains invalid names, values, or empty sections.
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
```

- [ ] **Step 4: Run the new tests**

```bash
pytest tests/test_writer.py -v
```

Expected: all pass (was 21, now 25).

- [ ] **Step 5: Commit**

```bash
git add inccsv/_writer.py tests/test_writer.py
git commit -m "feat: validate metadata names in writer"
```

---

## Task 2: Schema Alias Section Merging

**Files:**
- Modify: `inccsv/_schema.py`
- Test: `tests/test_schema.py`

`_get_section` returns only the first section whose lowercased name matches the alias set. If a schema file has both `[MUST]` and `[REQUIRED]`, one is silently discarded. The spec says alias sections for the same requirement class should be merged.

- [ ] **Step 1: Write the failing tests**

Add at the bottom of `tests/test_schema.py`:

```python
# --- alias section merging ---

def test_read_schema_merges_must_and_required(tmp_path):
    content = "---\n[MUST]\ntitle = String\n[REQUIRED]\nversion = Int\n---\n"
    path = make_schema_file(tmp_path, content)
    schema = read_schema(path)
    assert schema.must == {"title": "String", "version": "Int"}

def test_read_schema_merges_maybe_and_optional(tmp_path):
    content = "---\n[MAYBE]\ntitle = String\n[OPTIONAL]\nversion = Int\n---\n"
    path = make_schema_file(tmp_path, content)
    schema = read_schema(path)
    assert schema.maybe == {"title": "String", "version": "Int"}

def test_read_schema_duplicate_path_via_alias_raises(tmp_path):
    content = "---\n[MUST]\ntitle = String\n[MAY]\ntitle = String\n---\n"
    path = make_schema_file(tmp_path, content)
    with pytest.raises(ValueError, match="declared in both"):
        read_schema(path)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_schema.py::test_read_schema_merges_must_and_required \
       tests/test_schema.py::test_read_schema_merges_maybe_and_optional \
       tests/test_schema.py::test_read_schema_duplicate_path_via_alias_raises -v
```

Expected: first two FAILED (only first alias section found), third may pass or fail.

- [ ] **Step 3: Replace `_get_section` with `_merge_sections` in `inccsv/_schema.py`**

Replace the `_get_section` function and all its call sites. The updated full `inccsv/_schema.py`:

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
    forbidden: list[str] = field(default_factory=list)


@dataclass
class IncSchema:
    must: dict[str, str]
    maybe: dict[str, str]
    must_not: dict[str, str] = field(default_factory=dict)
    allow_extra: bool = True
    description: dict[str, str] = field(default_factory=dict)


# Section name aliases — case-insensitive, matching Julia's getsection().
_MUST_ALIASES     = frozenset({"must", "required", "shall"})
_MAYBE_ALIASES    = frozenset({"maybe", "optional", "may"})
_MUST_NOT_ALIASES = frozenset({"must_not", "shall_not"})
_SCHEMA_ALIASES   = frozenset({"schema", "options"})
_DESC_ALIASES     = frozenset({"description", "descriptions", "describe"})

# Values that mean False for allow_extra — matches Julia's parse_schema_bool.
_FALSY_ALLOW_EXTRA = frozenset({"false", "0", "no", "deny", "closed"})


def _merge_sections(meta: MetadataDict, aliases: frozenset[str]) -> dict:
    """Merge all sections whose lowercased name is in aliases into one dict."""
    merged: dict = {}
    for key, value in meta.items():
        if key.lower() in aliases and isinstance(value, dict):
            merged.update(value)
    return merged


def _has_path(metadata: MetadataDict, path: str) -> bool:
    if '.' in path:
        section, key = path.split('.', 1)
        val = metadata.get(section)
        return isinstance(val, dict) and key in val
    return path in metadata


def _file_paths(metadata: MetadataDict) -> set[str]:
    paths: set[str] = set()
    for k, v in metadata.items():
        if isinstance(v, dict):
            for ck in v:
                paths.add(f"{k}.{ck}")
        else:
            paths.add(k)
    return paths


def read_schema(path: str) -> IncSchema:
    """Read a schema definition from an INC file."""
    inc = read_inc(path)
    meta = inc.metadata

    schema_section = _merge_sections(meta, _SCHEMA_ALIASES)
    ae_raw = schema_section.get("allow_extra", "true")
    allow_extra = str(ae_raw).lower() not in _FALSY_ALLOW_EXTRA

    must        = {k: str(v) for k, v in _merge_sections(meta, _MUST_ALIASES).items()}
    maybe       = {k: str(v) for k, v in _merge_sections(meta, _MAYBE_ALIASES).items()}
    must_not    = {k: str(v) for k, v in _merge_sections(meta, _MUST_NOT_ALIASES).items()}
    description = {k: str(v) for k, v in _merge_sections(meta, _DESC_ALIASES).items()}

    all_entries = (
        [(p, "MUST") for p in must]
        + [(p, "MAYBE") for p in maybe]
        + [(p, "MUST_NOT") for p in must_not]
    )
    seen: dict[str, str] = {}
    for path_str, req_class in all_entries:
        if path_str.count('.') > 1:
            raise ValueError(
                f"Schema path {path_str!r} in [{req_class}] has more than one level "
                f"of nesting; only top-level names or 'section.key' paths are allowed."
            )
        if path_str in seen:
            raise ValueError(
                f"Schema path {path_str!r} is declared in both "
                f"[{seen[path_str]}] and [{req_class}]; each path may appear in at most one class."
            )
        seen[path_str] = req_class

    return IncSchema(
        must=must, maybe=maybe, must_not=must_not,
        allow_extra=allow_extra, description=description,
    )


def validate_schema(file: IncFile, schema: IncSchema) -> SchemaValidation:
    """
    Validate an IncFile's metadata against a schema.

    Checks both top-level scalar keys and section.child dotted paths.
    Section names themselves are never reported as extra — only their dotted children are.
    """
    paths = _file_paths(file.metadata)
    schema_paths = set(schema.must) | set(schema.maybe) | set(schema.must_not)

    missing  = [p for p in sorted(schema.must)     if not _has_path(file.metadata, p)]
    forbidden = [p for p in sorted(schema.must_not) if     _has_path(file.metadata, p)]
    extra    = [p for p in sorted(paths)            if p not in schema_paths]

    valid = not missing and not forbidden and (schema.allow_extra or not extra)
    return SchemaValidation(valid=valid, missing=missing, extra=extra, forbidden=forbidden)
```

- [ ] **Step 4: Run the new tests**

```bash
pytest tests/test_schema.py -v
```

Expected: all pass (was 38, now 41).

- [ ] **Step 5: Commit**

```bash
git add inccsv/_schema.py tests/test_schema.py
git commit -m "feat: merge all alias sections per requirement class in read_schema"
```

---

## Task 3: Structure Allowlist Enforcement

**Files:**
- Modify: `inccsv/_reader.py`
- Test: `tests/test_reader.py`

The spec says keys outside the 7-key allowlist (`delim`, `delimiter`, `quotechar`, `escapechar`, `comment`, `header`, `footerskip`) MUST be rejected. Python currently silently accepts many Julia-specific keys (`skipto`, `limit`, `missingstring`, etc.) via `_STRUCTURE_JULIA_ONLY_KEYS`. Both Julia and JS now reject them.

- [ ] **Step 1: Update the existing test and add new failing tests**

In `tests/test_reader.py`, change `test_read_inc_julia_only_structure_key_accepted` so it now expects a ValueError, and add two more specific tests:

```python
# CHANGE this existing test (line 116-121) to:
def test_read_inc_julia_only_structure_key_raises(tmp_path):
    content = "---\n[structure]\nmissingstring = NA\n---\nname,score\nAda,10\n"
    path = write_file(tmp_path, "data.inc", content)
    with pytest.raises(ValueError, match="unknown key"):
        read_inc(path)

# ADD these new tests at the bottom:
def test_read_inc_skipto_structure_key_raises(tmp_path):
    content = "---\n[structure]\nskipto = 2\n---\nname,score\nAda,10\n"
    path = write_file(tmp_path, "data.inc", content)
    with pytest.raises(ValueError, match="unknown key"):
        read_inc(path)

def test_read_inc_limit_structure_key_raises(tmp_path):
    content = "---\n[structure]\nlimit = 100\n---\nname,score\nAda,10\n"
    path = write_file(tmp_path, "data.inc", content)
    with pytest.raises(ValueError, match="unknown key"):
        read_inc(path)
```

- [ ] **Step 2: Run tests to verify the updated test now fails**

```bash
pytest tests/test_reader.py::test_read_inc_julia_only_structure_key_raises \
       tests/test_reader.py::test_read_inc_skipto_structure_key_raises \
       tests/test_reader.py::test_read_inc_limit_structure_key_raises -v
```

Expected: all 3 FAILED (keys currently accepted).

- [ ] **Step 3: Update `inccsv/_reader.py`**

Replace `_STRUCTURE_JULIA_ONLY_KEYS`, `_STRUCTURE_KNOWN_KEYS`, and the error message. The updated top of the file through `_csv_kwargs_from_metadata`:

```python
# inccsv/_reader.py
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Any

from ._parser import split_inc, parse_metadata, MetadataDict

# Keyword aliases for single-character [structure] values.
_CHAR_ALIASES: dict[str, str] = {"tab": "\t", "space": " "}

# Canonical [structure] key allowlist — spec structure.md.
_STRUCTURE_ALLOWED_KEYS = frozenset({
    "delim", "delimiter", "quotechar", "escapechar", "comment", "header", "footerskip"
})


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
            if key not in _STRUCTURE_ALLOWED_KEYS:
                raise ValueError(
                    f"[structure] contains unknown key {key!r}. "
                    f"Allowed keys: {sorted(_STRUCTURE_ALLOWED_KEYS)}"
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
```

- [ ] **Step 4: Run all reader tests**

```bash
pytest tests/test_reader.py -v
```

Expected: all pass. The renamed test now passes (raises as expected); the two new tests pass; the original unknown-key test still passes.

- [ ] **Step 5: Commit**

```bash
git add inccsv/_reader.py tests/test_reader.py
git commit -m "feat: enforce [structure] key allowlist, remove Julia-only passthrough"
```

---

## Task 4: `\t` Tab Alias and Structure Value Type Validation

**Files:**
- Modify: `inccsv/_reader.py`
- Test: `tests/test_reader.py`

Two related reader improvements: (a) the spec says readers MUST recognise `\t` (backslash-t) as the tab character, alongside the existing `tab` keyword; (b) character values that can't be coerced to a single character must be rejected, integer-valued keys (`header`, `footerskip`) must be integers, and `comment` must be a string.

- [ ] **Step 1: Write the failing tests**

Add at the bottom of `tests/test_reader.py`:

```python
def test_read_inc_backslash_t_tab_alias(tmp_path):
    # The literal two-character string \t in the file (backslash then t)
    content = "---\n[structure]\ndelim = \\t\n---\nname\tscore\nAda\t10\n"
    path = write_file(tmp_path, "data.inc", content)
    result = read_inc(path)
    assert result.rows == [{"name": "Ada", "score": "10"}]

def test_read_inc_invalid_char_value_raises(tmp_path):
    content = "---\n[structure]\ndelim = comma\n---\nname,score\nAda,10\n"
    path = write_file(tmp_path, "data.inc", content)
    with pytest.raises(ValueError, match="single character"):
        read_inc(path)

def test_read_inc_header_non_integer_raises(tmp_path):
    content = '---\n[structure]\nheader = "2"\n---\nname,score\nAda,10\n'
    path = write_file(tmp_path, "data.inc", content)
    with pytest.raises(ValueError, match="header.*integer"):
        read_inc(path)

def test_read_inc_footerskip_non_integer_raises(tmp_path):
    content = '---\n[structure]\nfooterskip = "1"\n---\nname,score\nAda,10\n'
    path = write_file(tmp_path, "data.inc", content)
    with pytest.raises(ValueError, match="footerskip.*integer"):
        read_inc(path)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_reader.py::test_read_inc_backslash_t_tab_alias \
       tests/test_reader.py::test_read_inc_invalid_char_value_raises \
       tests/test_reader.py::test_read_inc_header_non_integer_raises \
       tests/test_reader.py::test_read_inc_footerskip_non_integer_raises -v
```

Expected: all 4 FAILED.

- [ ] **Step 3: Update `inccsv/_reader.py`**

Change `_CHAR_ALIASES` and `_coerce_char`, and add type guards for `comment`, `header`, `footerskip` in `_csv_kwargs_from_metadata`. Only the changed sections are shown; everything else stays the same as after Task 3:

```python
# Keyword aliases for single-character [structure] values.
# "\\t" is the two-character string backslash+t as it appears in a parsed INC file.
_CHAR_ALIASES: dict[str, str] = {"tab": "\t", "\\t": "\t", "space": " "}


def _coerce_char(value: int | str) -> str:
    """Translate a [structure] char value: keyword alias or int code point → str."""
    if isinstance(value, int):
        return chr(value)
    s = _CHAR_ALIASES.get(str(value).lower(), str(value))
    if len(s) != 1:
        raise ValueError(
            f"[structure] character value must resolve to a single character, got {value!r}"
        )
    return s
```

And inside `_csv_kwargs_from_metadata`, after the existing `comment` block, add:

```python
        if "comment" in structure:
            comment_raw = structure["comment"]
            if not isinstance(comment_raw, str):
                raise ValueError(
                    f"[structure].comment must be a string, got {comment_raw!r}"
                )
            comment_char = comment_raw
        if "header" in structure:
            val = structure["header"]
            if not isinstance(val, int):
                raise ValueError(
                    f"[structure].header must be an integer, got {val!r}"
                )
        if "footerskip" in structure:
            val = structure["footerskip"]
            if not isinstance(val, int):
                raise ValueError(
                    f"[structure].footerskip must be an integer, got {val!r}"
                )
```

The complete updated `_csv_kwargs_from_metadata` (replacing the version from Task 3):

```python
def _csv_kwargs_from_metadata(metadata: MetadataDict) -> tuple[dict[str, Any], str | None]:
    """Extract csv.DictReader kwargs and comment char from [structure] metadata section."""
    structure = metadata.get("structure", {})
    kwargs: dict[str, Any] = {}
    comment_char: str | None = None
    if isinstance(structure, dict):
        for key in structure:
            if key not in _STRUCTURE_ALLOWED_KEYS:
                raise ValueError(
                    f"[structure] contains unknown key {key!r}. "
                    f"Allowed keys: {sorted(_STRUCTURE_ALLOWED_KEYS)}"
                )
        delim_value = structure.get("delimiter") if "delimiter" in structure else structure.get("delim")
        if delim_value is not None:
            kwargs["delimiter"] = _coerce_char(delim_value)
        if "quotechar" in structure:
            kwargs["quotechar"] = _coerce_char(structure["quotechar"])
        if "escapechar" in structure:
            kwargs["escapechar"] = _coerce_char(structure["escapechar"])
        if "comment" in structure:
            comment_raw = structure["comment"]
            if not isinstance(comment_raw, str):
                raise ValueError(
                    f"[structure].comment must be a string, got {comment_raw!r}"
                )
            comment_char = comment_raw
        if "header" in structure:
            val = structure["header"]
            if not isinstance(val, int):
                raise ValueError(
                    f"[structure].header must be an integer, got {val!r}"
                )
        if "footerskip" in structure:
            val = structure["footerskip"]
            if not isinstance(val, int):
                raise ValueError(
                    f"[structure].footerskip must be an integer, got {val!r}"
                )
    return kwargs, comment_char
```

- [ ] **Step 4: Run all reader tests**

```bash
pytest tests/test_reader.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add inccsv/_reader.py tests/test_reader.py
git commit -m "feat: add \\t tab alias and validate structure value types"
```

---

## Task 5: Apply `header` and `footerskip` to CSV Reading

**Files:**
- Modify: `inccsv/_reader.py`
- Test: `tests/test_reader.py`

The spec says readers MUST support all `[structure]` keys. `header = N` means line N of the CSV component contains the column names (1-based; default 1). `footerskip = N` means discard the last N rows.

- [ ] **Step 1: Write the failing tests**

Add at the bottom of `tests/test_reader.py`:

```python
def test_read_inc_header_2_skips_first_line(tmp_path):
    content = (
        "---\n[structure]\nheader = 2\n---\n"
        "discard,discard\nname,score\nAda,21\n"
    )
    path = write_file(tmp_path, "data.inc", content)
    result = read_inc(path)
    assert result.rows == [{"name": "Ada", "score": "21"}]

def test_read_inc_footerskip_1_drops_last_row(tmp_path):
    content = (
        "---\n[structure]\nfooterskip = 1\n---\n"
        "name,score\nAda,21\nTOTAL,33\n"
    )
    path = write_file(tmp_path, "data.inc", content)
    result = read_inc(path)
    assert result.rows == [{"name": "Ada", "score": "21"}]

def test_read_inc_header_and_footerskip_combined(tmp_path):
    content = (
        "---\n[structure]\nheader = 2\nfooterskip = 1\n---\n"
        "discard,discard\nname,score\nAda,21\nBabbage,12\nTOTAL,33\n"
    )
    path = write_file(tmp_path, "data.inc", content)
    result = read_inc(path)
    assert result.rows == [
        {"name": "Ada", "score": "21"},
        {"name": "Babbage", "score": "12"},
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_reader.py::test_read_inc_header_2_skips_first_line \
       tests/test_reader.py::test_read_inc_footerskip_1_drops_last_row \
       tests/test_reader.py::test_read_inc_header_and_footerskip_combined -v
```

Expected: all 3 FAILED.

- [ ] **Step 3: Update `inccsv/_reader.py`**

Change the return type of `_csv_kwargs_from_metadata` to a 4-tuple and update `read_inc` to use the new values. The complete updated file:

```python
# inccsv/_reader.py
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Any

from ._parser import split_inc, parse_metadata, MetadataDict

# Keyword aliases for single-character [structure] values.
# "\\t" is the two-character string backslash+t as it appears in a parsed INC file.
_CHAR_ALIASES: dict[str, str] = {"tab": "\t", "\\t": "\t", "space": " "}

# Canonical [structure] key allowlist — spec structure.md.
_STRUCTURE_ALLOWED_KEYS = frozenset({
    "delim", "delimiter", "quotechar", "escapechar", "comment", "header", "footerskip"
})


def _coerce_char(value: int | str) -> str:
    """Translate a [structure] char value: keyword alias or int code point → str."""
    if isinstance(value, int):
        return chr(value)
    s = _CHAR_ALIASES.get(str(value).lower(), str(value))
    if len(s) != 1:
        raise ValueError(
            f"[structure] character value must resolve to a single character, got {value!r}"
        )
    return s


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


def _csv_kwargs_from_metadata(
    metadata: MetadataDict,
) -> tuple[dict[str, Any], str | None, int, int]:
    """Extract csv.DictReader kwargs, comment char, header line, and footerskip from [structure]."""
    structure = metadata.get("structure", {})
    kwargs: dict[str, Any] = {}
    comment_char: str | None = None
    header: int = 1
    footerskip: int = 0
    if isinstance(structure, dict):
        for key in structure:
            if key not in _STRUCTURE_ALLOWED_KEYS:
                raise ValueError(
                    f"[structure] contains unknown key {key!r}. "
                    f"Allowed keys: {sorted(_STRUCTURE_ALLOWED_KEYS)}"
                )
        delim_value = structure.get("delimiter") if "delimiter" in structure else structure.get("delim")
        if delim_value is not None:
            kwargs["delimiter"] = _coerce_char(delim_value)
        if "quotechar" in structure:
            kwargs["quotechar"] = _coerce_char(structure["quotechar"])
        if "escapechar" in structure:
            kwargs["escapechar"] = _coerce_char(structure["escapechar"])
        if "comment" in structure:
            comment_raw = structure["comment"]
            if not isinstance(comment_raw, str):
                raise ValueError(
                    f"[structure].comment must be a string, got {comment_raw!r}"
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
    csv_lines = csv_lines[max(0, header - 1):]  # skip lines before header (header is 1-based)

    if comment_char:
        csv_lines = [ln for ln in csv_lines if not ln.lstrip().startswith(comment_char)]

    reader = csv.DictReader(io.StringIO("".join(csv_lines)), **base_kwargs)
    rows = [dict(row) for row in reader]

    if footerskip > 0:
        rows = rows[:-footerskip]

    return IncFile(metadata=metadata, rows=rows, path=path)
```

- [ ] **Step 4: Run all reader tests**

```bash
pytest tests/test_reader.py -v
```

Expected: all pass.

- [ ] **Step 5: Run full test suite**

```bash
pytest -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add inccsv/_reader.py tests/test_reader.py
git commit -m "feat: apply header and footerskip from [structure] to CSV reading"
```

---

## Task 6: Schema Path Component Name Validation

**Files:**
- Modify: `inccsv/_schema.py`
- Test: `tests/test_schema.py`

The spec says each component of a schema path must satisfy the metadata name rules. Python currently checks depth (≤ 1 dot) but not that individual components are non-empty. A key like `a.` or `.key` stored in a schema section slips through the depth check but produces an empty component when split on `.`.

- [ ] **Step 1: Write the failing tests**

Add at the bottom of `tests/test_schema.py`:

```python
# --- path component validation ---

def test_read_schema_trailing_dot_path_raises(tmp_path):
    content = "---\n[MUST]\na. = String\n---\n"
    path = make_schema_file(tmp_path, content)
    with pytest.raises(ValueError, match="empty name component"):
        read_schema(path)

def test_read_schema_leading_dot_path_raises(tmp_path):
    content = "---\n[MUST]\n.key = String\n---\n"
    path = make_schema_file(tmp_path, content)
    with pytest.raises(ValueError, match="empty name component"):
        read_schema(path)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_schema.py::test_read_schema_trailing_dot_path_raises \
       tests/test_schema.py::test_read_schema_leading_dot_path_raises -v
```

Expected: both FAILED (no error raised currently).

- [ ] **Step 3: Add component validation to `read_schema` in `inccsv/_schema.py`**

Replace the existing validation loop in `read_schema` (the `for path_str, req_class in all_entries:` block) with:

```python
    seen: dict[str, str] = {}
    for path_str, req_class in all_entries:
        if path_str.count('.') > 1:
            raise ValueError(
                f"Schema path {path_str!r} in [{req_class}] has more than one level "
                f"of nesting; only top-level names or 'section.key' paths are allowed."
            )
        parts = path_str.split('.') if '.' in path_str else [path_str]
        for part in parts:
            if not part:
                raise ValueError(
                    f"Schema path {path_str!r} in [{req_class}] contains an empty name component"
                )
        if path_str in seen:
            raise ValueError(
                f"Schema path {path_str!r} is declared in both "
                f"[{seen[path_str]}] and [{req_class}]; each path may appear in at most one class."
            )
        seen[path_str] = req_class
```

- [ ] **Step 4: Run all schema tests**

```bash
pytest tests/test_schema.py -v
```

Expected: all pass (was 41, now 43).

- [ ] **Step 5: Commit**

```bash
git add inccsv/_schema.py tests/test_schema.py
git commit -m "feat: validate schema path components are non-empty names"
```

---

## Task 7: Closing Delimiter Error Message and README

**Files:**
- Modify: `inccsv/_parser.py`
- Modify: `README.md`
- Test: `tests/test_parser.py`

Two small improvements: (a) the missing-closing-delimiter error now includes the last metadata line seen, matching Julia's diagnostic; (b) the README schema example uses `[OPTIONAL]` (canonical) instead of `[MAYBE]` (legacy alias).

- [ ] **Step 1: Write a failing test for the parser error message**

Add at the bottom of `tests/test_parser.py`:

```python
def test_split_inc_missing_delimiter_error_includes_last_line(tmp_path):
    f = tmp_path / "bad.inc"
    f.write_text("---\ntitle = Missing closer\nname,score\n", encoding="utf-8")
    with pytest.raises(ValueError, match="last metadata line"):
        split_inc(str(f))
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/test_parser.py::test_split_inc_missing_delimiter_error_includes_last_line -v
```

Expected: FAILED (error message doesn't mention last metadata line yet).

- [ ] **Step 3: Update `split_inc` in `inccsv/_parser.py`**

Replace the `raise ValueError` at the end of `split_inc`:

```python
    last_line = lines[-1].rstrip('\n\r') if len(lines) > 1 else ''
    raise ValueError(
        f"Opening delimiter found in '{path}' but closing delimiter is missing "
        f"(last metadata line: {last_line!r})."
    )
```

The complete updated `split_inc`:

```python
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

    last_line = lines[-1].rstrip('\n\r') if len(lines) > 1 else ''
    raise ValueError(
        f"Opening delimiter found in '{path}' but closing delimiter is missing "
        f"(last metadata line: {last_line!r})."
    )
```

- [ ] **Step 4: Update the README**

In `README.md`, find the schema example block:

```
[MAYBE]
author = String
```

Replace it with:

```
[OPTIONAL]
author = String
```

The full schema example block in the README should read:

```
---
[schema]
allow_extra = false

[MUST]
title = String
version = Int

[OPTIONAL]
author = String
---
```

- [ ] **Step 5: Run all parser tests**

```bash
pytest tests/test_parser.py -v
```

Expected: all pass (was 21, now 22).

- [ ] **Step 6: Run full test suite**

```bash
pytest -v
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add inccsv/_parser.py README.md tests/test_parser.py
git commit -m "fix: include last metadata line in missing-delimiter error; update README to canonical [OPTIONAL]"
```

---

## Task 8: Cross-Language Fixtures

**Files:**
- Create: `tests/fixtures/positive/` (11 files)
- Create: `tests/fixtures/negative/` (10 files)
- Create: `tests/fixtures/roundtrip/` (2 files)
- Create: `tests/test_fixtures.py`

These are the canonical INCspec test fixtures from https://github.com/mroughan/INCspec. Pinning them locally means the Python test suite will detect drift from the spec without needing network access.

- [ ] **Step 1: Create the fixture directories**

```bash
mkdir -p tests/fixtures/positive tests/fixtures/negative tests/fixtures/roundtrip
```

- [ ] **Step 2: Write the test file (it will fail until the fixtures exist)**

Create `tests/test_fixtures.py`:

```python
# tests/test_fixtures.py
from __future__ import annotations

import pytest
from pathlib import Path

from inccsv._reader import read_inc
from inccsv._schema import read_schema, validate_schema
from inccsv._writer import write_inc

FIXTURES = Path(__file__).parent / "fixtures"


# --- Positive: files that must parse without error ---

@pytest.mark.parametrize("filename", [
    "basic.inc",
    "escapechar_structure.inc",
    "header_footerskip_structure.inc",
    "metadata_edge_cases.inc",
    "plain.csv",
    "quotechar_structure.inc",
    "semicolon_structure.inc",
    "tab_structure.inc",
    "unicode.inc",
])
def test_positive_fixture_parses(filename):
    read_inc(str(FIXTURES / "positive" / filename))


def test_positive_schema_fixture_reads():
    read_schema(str(FIXTURES / "positive" / "schema.inc"))


def test_positive_schema_target_validates():
    schema = read_schema(str(FIXTURES / "positive" / "schema.inc"))
    target = read_inc(str(FIXTURES / "positive" / "schema_target_valid.inc"))
    result = validate_schema(target, schema)
    assert result.valid is True


# --- Negative: files that must raise ValueError ---

@pytest.mark.parametrize("filename", [
    "empty_section.inc",
    "invalid_key.inc",
    "invalid_section_key.inc",
    "invalid_structure_char.inc",
    "invalid_structure_int.inc",
    "missing_closing_delimiter.inc",
    "repeated_key.inc",
    "unsupported_structure_key.inc",
])
def test_negative_fixture_raises(filename):
    with pytest.raises(ValueError):
        read_inc(str(FIXTURES / "negative" / filename))


@pytest.mark.parametrize("filename", [
    "schema_deep_path.inc",
    "schema_duplicate_requirement.inc",
])
def test_negative_schema_fixture_raises(filename):
    with pytest.raises(ValueError):
        read_schema(str(FIXTURES / "negative" / filename))


# --- Roundtrip: read then write must reproduce expected output ---

def test_roundtrip_basic(tmp_path):
    fixture = FIXTURES / "roundtrip" / "basic_expected.inc"
    inc = read_inc(str(fixture))
    out = tmp_path / "out.inc"
    write_inc(str(out), inc.rows, metadata=inc.metadata)
    assert out.read_text() == fixture.read_text()


def test_roundtrip_escaped(tmp_path):
    fixture = FIXTURES / "roundtrip" / "escaped_expected.inc"
    inc = read_inc(str(fixture))
    out = tmp_path / "out.inc"
    write_inc(str(out), inc.rows, metadata=inc.metadata)
    assert out.read_text() == fixture.read_text()
```

- [ ] **Step 3: Run the test file to verify failures (fixtures don't exist yet)**

```bash
pytest tests/test_fixtures.py -v 2>&1 | head -30
```

Expected: errors about missing fixture files.

- [ ] **Step 4: Create the positive fixture files**

Create `tests/fixtures/positive/basic.inc`:
```
---
title = Basic data
version = 1
[columns]
score = points
---
name,score
Ada,21
Babbage,12
```

Create `tests/fixtures/positive/escapechar_structure.inc`:
```
---
title = Escape character data
[structure]
escapechar = |
---
name,note
Ada,"say |"hi|""
```

Create `tests/fixtures/positive/header_footerskip_structure.inc`:
```
---
title = Header and footer data
[structure]
header = 2
footerskip = 1
---
discard,discard
name,score
Ada,21
Babbage,12
TOTAL,33
```

Create `tests/fixtures/positive/metadata_edge_cases.inc`:
```
---
title = Metadata edge cases
empty =
hash = #
semicolon = ;
path = C:\tmp\data
quoted = "say \"hi\" with \\"
id = "007"
offset = -3
---
name,value
Ada,1
```

Create `tests/fixtures/positive/plain.csv`:
```
name,score
Ada,21
Babbage,12
```

Create `tests/fixtures/positive/quotechar_structure.inc`:
```
---
title = Quote character data
[structure]
quotechar = "'"
---
name,note
Ada,'hello, world'
```

Create `tests/fixtures/positive/schema.inc`:
```
---
[schema]
allow_extra = false
[MUST]
title = String
columns.score = String
[MUST_NOT]
internal_id = String
[OPTIONAL]
version = Int
[description]
title = Human-readable title
columns.score = Meaning of the score column
---
```

Create `tests/fixtures/positive/schema_target_valid.inc`:
```
---
title = Schema target
version = 1
[columns]
score = points
---
name,score
Ada,21
```

Create `tests/fixtures/positive/semicolon_structure.inc`:
```
---
title = Semicolon data
[structure]
delimiter = ;
---
name;score
Ada;21
Babbage;12
```

Create `tests/fixtures/positive/tab_structure.inc`:
```
---
title = Tab data
[structure]
delim = tab
---
name	score
Ada	21
Babbage	12
```

Create `tests/fixtures/positive/unicode.inc`:
```
---
title = Café temperatures
city = München
測定 = 温度
[columns]
temperature = °C
名前 = participant name
---
name,temperature,note
Anaïs,21,café
李,22,東京
```

- [ ] **Step 5: Create the negative fixture files**

Create `tests/fixtures/negative/empty_section.inc`:
```
---
title = Empty section
[columns]
---
name,score
Ada,21
```

Create `tests/fixtures/negative/invalid_key.inc`:
```
---
bad key = value
---
name,score
Ada,21
```

Create `tests/fixtures/negative/invalid_section_key.inc`:
```
---
title = Invalid section key
[columns]
bad key = points
---
name,score
Ada,21
```

Create `tests/fixtures/negative/invalid_structure_char.inc`:
```
---
title = Invalid structure char
[structure]
delim = comma
---
name,score
Ada,21
```

Create `tests/fixtures/negative/invalid_structure_int.inc`:
```
---
title = Invalid structure int
[structure]
header = "2"
---
discard,discard
name,score
Ada,21
```

Create `tests/fixtures/negative/missing_closing_delimiter.inc`:
```
---
title = Missing closing delimiter
name,score
Ada,21
```

Create `tests/fixtures/negative/repeated_key.inc`:
```
---
title = A
title = B
---
name,score
Ada,21
```

Create `tests/fixtures/negative/unsupported_structure_key.inc`:
```
---
title = Unsupported structure key
[structure]
skipto = 2
---
name,score
Ada,21
```

Create `tests/fixtures/negative/schema_deep_path.inc`:
```
---
[MUST]
a.b.c = String
---
```

Create `tests/fixtures/negative/schema_duplicate_requirement.inc`:
```
---
[MUST]
title = String
[OPTIONAL]
title = String
---
```

- [ ] **Step 6: Create the roundtrip fixture files**

Create `tests/fixtures/roundtrip/basic_expected.inc`:
```
---
title = Roundtrip data
version = 1
[columns]
score = points
---
name,score
Ada,21
Babbage,12
```

Create `tests/fixtures/roundtrip/escaped_expected.inc`:
```
---
id = "007"
note = "say \"hi\" with \\"
path = "C:\\tmp\\data"
---
name,value
Ada,1
```

- [ ] **Step 7: Run the fixture tests**

```bash
pytest tests/test_fixtures.py -v
```

Expected: all pass (11 positive + 2 schema positive + 8 negative + 2 schema negative + 2 roundtrip = 25 tests).

- [ ] **Step 8: Run the full test suite**

```bash
pytest -v
```

Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add tests/fixtures/ tests/test_fixtures.py
git commit -m "test: add INCspec cross-language fixtures and fixture test suite"
```

---

## Self-Review

**Spec coverage check:**

| Item | Task | Coverage |
|---|---|---|
| Writer rejects invalid names | Task 1 | `_validate_name` on all keys and section names |
| Schema alias sections merged | Task 2 | `_merge_sections` replaces `_get_section` |
| `[structure]` allowlist enforced | Task 3 | `_STRUCTURE_ALLOWED_KEYS`, removes Julia-only passthrough |
| `\t` tab alias | Task 4 | `_CHAR_ALIASES["\\t"]` |
| Character value single-char validation | Task 4 | `_coerce_char` length check |
| `comment` string validation | Task 4 | `isinstance(comment_raw, str)` guard |
| `header`/`footerskip` integer validation | Task 4 | `isinstance(val, int)` guards |
| `header` applied to CSV reading | Task 5 | `csv_lines = csv_lines[max(0, header - 1):]` |
| `footerskip` applied to CSV reading | Task 5 | `rows = rows[:-footerskip]` |
| Schema path component validation | Task 6 | empty-part check after splitting on `.` |
| Missing-delimiter diagnostic | Task 7 | `last_line` in error message |
| README uses `[OPTIONAL]` | Task 7 | README update |
| Cross-language fixtures | Task 8 | 23 fixture files + `test_fixtures.py` |

**No placeholders found.**

**Type consistency:** `_csv_kwargs_from_metadata` returns `tuple[dict, str|None, int, int]` after Task 5. `read_inc` unpacks with `base_kwargs, comment_char, header, footerskip = ...`. Consistent throughout.
