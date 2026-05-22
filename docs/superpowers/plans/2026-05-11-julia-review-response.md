# Julia Review Response — IncCSV.py Updates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align IncCSV.py with the changes the Julia developer made in response to our review, specifically: sorted metadata output, schema section.key path validation, MUST_NOT requirement class, RFC 2119 section-name aliases, and read_schema input guards.

**Architecture:** The Julia developer fixed five bugs we reported and added MUST_NOT as a new schema requirement class. We respond by (1) sorting our writer output to match Julia's new deterministic order, (2) upgrading `validate_schema` to walk `section.child` dotted paths the same way Julia does, (3) adding MUST_NOT / RFC 2119 aliases to our schema layer, and (4) adding guards in `read_schema` that reject deep paths and duplicate requirement-class entries, matching Julia's new `ArgumentError` behavior. All changes are in three existing files; no new files are created.

**Tech Stack:** Python 3.9+, `dataclasses`, `csv`, `pytest`. No new dependencies.

---

## File Map

| File | Changes |
|---|---|
| `inccsv/_writer.py` | Sort scalars, sections, and section keys in `_metadata_to_lines` |
| `inccsv/_schema.py` | Add `must_not` to `IncSchema`, add `forbidden` to `SchemaValidation`, add RFC 2119 aliases, rewrite `validate_schema`, add guards to `read_schema` |
| `tests/test_writer.py` | 4 new tests for sorted output |
| `tests/test_schema.py` | Update 2 existing tests; add 14 new tests |

---

## Context for subagents

The project is a Python library (`inccsv/`) that reads and writes INC files (metadata block + CSV). The test command is `pytest tests/ -v`. All tests must pass before committing.

The Julia counterpart library received a code review from this project. The Julia developer responded by fixing bugs and adding features. This plan aligns the Python library to match the canonical behavior Julia established.

**Key invariant:** `validate_schema` in Python must now give the same results as Julia's `validateschema` for the same `(file, schema)` pair. The canonical behavior is:
- Scalar top-level keys AND `section.child` dotted paths are both validated.
- Section names themselves are never in `extra` — only their dotted children are.
- MUST_NOT paths found in the file make `valid = False` and appear in `forbidden`.

---

## Task 1: Sorted Writer Output

**Files:**
- Modify: `inccsv/_writer.py:58-78` (`_metadata_to_lines`)
- Test: `tests/test_writer.py`

Julia now writes metadata in deterministic sorted order: scalar keys first (alphabetical), then sections (alphabetical), with keys inside each section also sorted alphabetically. Python should match this.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_writer.py`:

```python
def test_write_scalars_before_sections(tmp_path):
    path = str(tmp_path / "out.inc")
    write_inc(path, [], metadata={"columns": {"a": "1"}, "title": "Test"})
    content = (tmp_path / "out.inc").read_text()
    assert content.index("title") < content.index("[columns]")

def test_write_scalar_keys_sorted(tmp_path):
    path = str(tmp_path / "out.inc")
    write_inc(path, [], metadata={"z_key": "last", "a_key": "first", "m_key": "mid"})
    content = (tmp_path / "out.inc").read_text()
    assert content.index("a_key") < content.index("m_key") < content.index("z_key")

def test_write_sections_sorted(tmp_path):
    path = str(tmp_path / "out.inc")
    write_inc(path, [], metadata={"z_sec": {"k": "v"}, "a_sec": {"k": "v"}})
    content = (tmp_path / "out.inc").read_text()
    assert content.index("[a_sec]") < content.index("[z_sec]")

def test_write_section_keys_sorted(tmp_path):
    path = str(tmp_path / "out.inc")
    write_inc(path, [], metadata={"cols": {"z": "last", "a": "first"}})
    content = (tmp_path / "out.inc").read_text()
    assert content.index("a = ") < content.index("z = ")
```

- [ ] **Step 2: Run the new tests to confirm they fail**

```bash
pytest tests/test_writer.py::test_write_scalars_before_sections \
       tests/test_writer.py::test_write_scalar_keys_sorted \
       tests/test_writer.py::test_write_sections_sorted \
       tests/test_writer.py::test_write_section_keys_sorted -v
```

Expected: 1–4 tests fail (dict iteration order is insertion order, not sorted).

- [ ] **Step 3: Replace `_metadata_to_lines` in `inccsv/_writer.py`**

Replace lines 58–78 (the entire `_metadata_to_lines` function) with:

```python
def _metadata_to_lines(metadata: MetadataDict) -> list[str]:
    """Serialise a metadata dict to INI lines (without delimiters)."""
    lines: list[str] = []

    # Global scalar keys first, sorted alphabetically
    for key in sorted(k for k, v in metadata.items() if not isinstance(v, dict)):
        lines.append(f"{key} = {_validate_and_format(metadata[key], repr(key))}")

    # Sections next, sorted alphabetically
    for section in sorted(k for k, v in metadata.items() if isinstance(v, dict)):
        content = metadata[section]
        if not content:
            raise ValueError(f"Section [{section}] is empty (no properties defined)")
        lines.append(f"[{section}]")
        for key in sorted(content.keys()):
            lines.append(
                f"{key} = {_validate_and_format(content[key], f'[{section}].{key!r}')}"
            )

    return lines
```

- [ ] **Step 4: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: all tests pass (sorting is a superset of the old iteration order for any single-pass write).

- [ ] **Step 5: Commit**

```bash
git add inccsv/_writer.py tests/test_writer.py
git commit -m "feat: write metadata in deterministic sorted order (scalars, then sections)"
```

---

## Task 2: Schema Data Model — `must_not`, `forbidden`, RFC 2119 Aliases

**Files:**
- Modify: `inccsv/_schema.py:1-56`
- Test: `tests/test_schema.py`

Julia added `MUST_NOT` as a new requirement class and RFC 2119 aliases (`SHALL` → MUST, `MAY` → MAYBE, `SHALL_NOT` → MUST_NOT). We need to add `must_not` to `IncSchema`, `forbidden` to `SchemaValidation`, the new alias set, and update `read_schema` to extract the MUST_NOT section.

Note that `test_incschema_defaults` will need updating (add assertion for `must_not`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_schema.py`:

```python
# --- must_not field ---

def test_incschema_must_not_default():
    s = IncSchema(must={}, maybe={})
    assert s.must_not == {}

def test_schema_validation_forbidden_field_default():
    schema = IncSchema(must={"title": "String"}, maybe={})
    f = make_file({"title": "Test"})
    result = validate_schema(f, schema)
    assert result.forbidden == []

def test_read_schema_must_not_section(tmp_path):
    content = "---\n[MUST_NOT]\ninternal_id = String\n---\n"
    path = make_schema_file(tmp_path, content)
    schema = read_schema(path)
    assert schema.must_not == {"internal_id": "String"}

def test_read_schema_shall_not_alias(tmp_path):
    content = "---\n[SHALL_NOT]\nfoo = String\n---\n"
    path = make_schema_file(tmp_path, content)
    schema = read_schema(path)
    assert schema.must_not == {"foo": "String"}

def test_read_schema_shall_alias(tmp_path):
    content = "---\n[SHALL]\ntitle = String\n---\n"
    path = make_schema_file(tmp_path, content)
    schema = read_schema(path)
    assert schema.must == {"title": "String"}

def test_read_schema_may_alias(tmp_path):
    content = "---\n[MAY]\nauthor = String\n---\n"
    path = make_schema_file(tmp_path, content)
    schema = read_schema(path)
    assert schema.maybe == {"author": "String"}
```

Also update the existing `test_incschema_defaults` test (replace the entire function body):

```python
def test_incschema_defaults():
    s = IncSchema(must={}, maybe={})
    assert s.allow_extra is True
    assert s.description == {}
    assert s.must_not == {}
```

- [ ] **Step 2: Run the new tests to confirm they fail**

```bash
pytest tests/test_schema.py::test_incschema_must_not_default \
       tests/test_schema.py::test_schema_validation_forbidden_field_default \
       tests/test_schema.py::test_read_schema_must_not_section \
       tests/test_schema.py::test_read_schema_shall_not_alias \
       tests/test_schema.py::test_read_schema_shall_alias \
       tests/test_schema.py::test_read_schema_may_alias -v
```

Expected: all 6 fail.

- [ ] **Step 3: Update `inccsv/_schema.py` — data model and aliases**

Replace the entire file content with:

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


def _get_section(meta: MetadataDict, aliases: frozenset[str]) -> dict:
    """Return the first section whose lowercased name is in aliases, or {}."""
    for key, value in meta.items():
        if key.lower() in aliases and isinstance(value, dict):
            return value
    return {}


def _has_path(metadata: MetadataDict, path: str) -> bool:
    """Return True if path (top-level key or section.child) exists in metadata."""
    if '.' in path:
        section, key = path.split('.', 1)
        val = metadata.get(section)
        return isinstance(val, dict) and key in val
    return path in metadata


def _file_paths(metadata: MetadataDict) -> set[str]:
    """Return all leaf paths: top-level scalars and section.child dotted paths."""
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

    schema_section = _get_section(meta, _SCHEMA_ALIASES)
    ae_raw = schema_section.get("allow_extra", "true")
    allow_extra = str(ae_raw).lower() not in _FALSY_ALLOW_EXTRA

    must        = {k: str(v) for k, v in _get_section(meta, _MUST_ALIASES).items()}
    maybe       = {k: str(v) for k, v in _get_section(meta, _MAYBE_ALIASES).items()}
    must_not    = {k: str(v) for k, v in _get_section(meta, _MUST_NOT_ALIASES).items()}
    description = {k: str(v) for k, v in _get_section(meta, _DESC_ALIASES).items()}

    # Validate: no deep paths (only `name` or `section.name` allowed)
    all_entries: list[tuple[str, str]] = [
        *((p, "MUST") for p in must),
        *((p, "MAYBE") for p in maybe),
        *((p, "MUST_NOT") for p in must_not),
    ]
    for path_str, req_class in all_entries:
        if path_str.count('.') > 1:
            raise ValueError(
                f"Schema path {path_str!r} in [{req_class}] has more than one level "
                f"of nesting; only top-level names or 'section.key' paths are allowed."
            )

    # Validate: no duplicate paths across requirement classes
    seen: dict[str, str] = {}
    for path_str, req_class in all_entries:
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
    Section names themselves are never reported as extra — only their dotted children.
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
pytest tests/test_schema.py::test_incschema_must_not_default \
       tests/test_schema.py::test_schema_validation_forbidden_field_default \
       tests/test_schema.py::test_read_schema_must_not_section \
       tests/test_schema.py::test_read_schema_shall_not_alias \
       tests/test_schema.py::test_read_schema_shall_alias \
       tests/test_schema.py::test_read_schema_may_alias \
       tests/test_schema.py::test_incschema_defaults -v
```

Expected: all 7 pass.

- [ ] **Step 5: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: all tests pass (or only the old `test_validate_schema_ignores_section_keys` fails — that is intentional and will be fixed in Task 3).

- [ ] **Step 6: Commit**

```bash
git add inccsv/_schema.py tests/test_schema.py
git commit -m "feat: add MUST_NOT class, RFC 2119 aliases, and SchemaValidation.forbidden"
```

---

## Task 3: Schema Validation — section.key Paths and Forbidden Check

**Files:**
- Modify: `inccsv/_schema.py` (already rewritten in Task 2 — `validate_schema` is new)
- Modify: `tests/test_schema.py` — update one existing test, add new tests

The new `validate_schema` from Task 2 already handles `section.child` paths and `forbidden`. This task adds tests for that behavior and updates the one existing test whose expectation is now wrong.

The test `test_validate_schema_ignores_section_keys` documented the OLD behavior ("section contents are not checked"). The new canonical behavior is that section children ARE checked. The test must be replaced.

- [ ] **Step 1: Write the failing/updated tests**

In `tests/test_schema.py`, **replace** the entire `test_validate_schema_ignores_section_keys` function with:

```python
def test_validate_section_names_not_counted_as_extra():
    """Section names are never extra; only undeclared dotted children are."""
    schema = IncSchema(must={"title": "String"}, maybe={}, allow_extra=False)
    f = make_file({"title": "Test", "columns": {"time": "seconds"}})
    result = validate_schema(f, schema)
    assert "columns" not in result.extra
    assert "columns.time" in result.extra
    assert result.valid is False
```

Append the following new tests to `tests/test_schema.py`:

```python
# --- section.child path validation ---

def test_validate_section_child_in_must_passes():
    schema = IncSchema(must={"title": "String", "columns.score": "String"}, maybe={})
    f = make_file({"title": "Test", "columns": {"score": "Float"}})
    result = validate_schema(f, schema)
    assert result.valid is True
    assert result.missing == []

def test_validate_missing_section_child_path():
    schema = IncSchema(must={"columns.score": "String"}, maybe={})
    f = make_file({"title": "Test"})  # no columns section
    result = validate_schema(f, schema)
    assert result.valid is False
    assert "columns.score" in result.missing

def test_validate_section_child_extra_when_allow_extra_false():
    schema = IncSchema(must={"title": "String"}, maybe={}, allow_extra=False)
    f = make_file({"title": "Test", "columns": {"score": "Float"}})
    result = validate_schema(f, schema)
    assert result.valid is False
    assert "columns.score" in result.extra

def test_validate_section_child_not_extra_when_declared():
    schema = IncSchema(
        must={"title": "String", "columns.score": "String"}, maybe={}, allow_extra=False
    )
    f = make_file({"title": "Test", "columns": {"score": "Float"}})
    result = validate_schema(f, schema)
    assert result.valid is True
    assert result.extra == []

def test_validate_section_child_in_maybe_not_extra():
    schema = IncSchema(must={}, maybe={"columns.score": "String"})
    f = make_file({"columns": {"score": "Float"}})
    result = validate_schema(f, schema)
    assert result.valid is True
    assert result.extra == []

# --- MUST_NOT validation ---

def test_validate_must_not_field_present_is_invalid():
    schema = IncSchema(must={}, maybe={}, must_not={"internal_id": "String"})
    f = make_file({"internal_id": "secret"})
    result = validate_schema(f, schema)
    assert result.valid is False
    assert "internal_id" in result.forbidden

def test_validate_must_not_field_absent_is_valid():
    schema = IncSchema(must={"title": "String"}, maybe={}, must_not={"internal_id": "String"})
    f = make_file({"title": "Test"})
    result = validate_schema(f, schema)
    assert result.valid is True
    assert result.forbidden == []

def test_validate_must_not_section_child():
    schema = IncSchema(must={}, maybe={}, must_not={"private.key": "String"})
    f = make_file({"private": {"key": "secret"}})
    result = validate_schema(f, schema)
    assert result.valid is False
    assert "private.key" in result.forbidden
```

- [ ] **Step 2: Run all schema tests**

```bash
pytest tests/test_schema.py -v
```

Expected: all tests pass (the new `validate_schema` in Task 2 already handles these cases).

- [ ] **Step 3: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add tests/test_schema.py
git commit -m "test: add section.child path and MUST_NOT validation tests; update section-keys test"
```

---

## Task 4: read_schema Input Validation — Deep Paths and Duplicate Classes

**Files:**
- Test: `tests/test_schema.py`
- (Implementation already in `inccsv/_schema.py` from Task 2)

The `read_schema` function in Task 2 already guards against deep paths (more than one dot) and duplicate requirement-class entries. This task adds regression tests to pin that behaviour.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_schema.py`:

```python
# --- read_schema input guards ---

def test_read_schema_deep_path_raises(tmp_path):
    content = "---\n[MUST]\na.b.c = String\n---\n"
    path = make_schema_file(tmp_path, content)
    with pytest.raises(ValueError, match="more than one level"):
        read_schema(path)

def test_read_schema_duplicate_must_maybe_raises(tmp_path):
    content = "---\n[MUST]\ntitle = String\n[MAYBE]\ntitle = String\n---\n"
    path = make_schema_file(tmp_path, content)
    with pytest.raises(ValueError, match="declared in both"):
        read_schema(path)

def test_read_schema_duplicate_must_must_not_raises(tmp_path):
    content = "---\n[MUST]\ntitle = String\n[MUST_NOT]\ntitle = String\n---\n"
    path = make_schema_file(tmp_path, content)
    with pytest.raises(ValueError, match="declared in both"):
        read_schema(path)

def test_read_schema_single_dot_path_valid(tmp_path):
    # section.key paths are allowed (exactly one dot)
    content = "---\n[MUST]\ncolumns.score = String\n---\n"
    path = make_schema_file(tmp_path, content)
    schema = read_schema(path)
    assert schema.must == {"columns.score": "String"}

def test_read_schema_top_level_path_valid(tmp_path):
    # Top-level names (no dot) are allowed
    content = "---\n[MUST]\ntitle = String\n---\n"
    path = make_schema_file(tmp_path, content)
    schema = read_schema(path)
    assert schema.must == {"title": "String"}
```

- [ ] **Step 2: Run the new tests to confirm they pass**

```bash
pytest tests/test_schema.py::test_read_schema_deep_path_raises \
       tests/test_schema.py::test_read_schema_duplicate_must_maybe_raises \
       tests/test_schema.py::test_read_schema_duplicate_must_must_not_raises \
       tests/test_schema.py::test_read_schema_single_dot_path_valid \
       tests/test_schema.py::test_read_schema_top_level_path_valid -v
```

Expected: all 5 pass (implementation already in place from Task 2).

- [ ] **Step 3: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add tests/test_schema.py
git commit -m "test: pin read_schema guards for deep paths and duplicate requirement classes"
```

---

## Self-Review

### Spec coverage

| Response item | Task |
|---|---|
| Metadata written in deterministic sorted order | Task 1 |
| `delimiter` accepted as alias (already done in Python; Julia now matches) | — (no-op) |
| Bare `;`/`#` fix (already done in Python parser; Julia now matches) | — (no-op) |
| Empty sections rejected (already done in Python; Julia now matches) | — (no-op) |
| Newline rejection (already done in Python; Julia now matches) | — (no-op) |
| `MUST_NOT` requirement class | Task 2 |
| RFC 2119 aliases (`SHALL`, `MAY`, `SHALL_NOT`) | Task 2 |
| `SchemaValidation.forbidden` | Task 2 |
| `IncSchema.must_not` | Task 2 |
| `validate_schema` section.child path walking | Task 3 |
| Section parents not reported as extra | Task 3 |
| Reject deep schema paths (a.b.c) | Task 4 |
| Reject duplicate requirement-class entries | Task 4 |

All response items are covered.

### Placeholder scan

No TBDs, todos, or "similar to" references. Every step has complete code.

### Type consistency

- `SchemaValidation.forbidden: list[str]` — used consistently in Task 2 (definition) and Task 3 (assertions in tests).
- `IncSchema.must_not: dict[str, str]` — defined in Task 2, used as `schema.must_not` in Task 2 (`read_schema`) and Task 3 (`validate_schema`).
- `_has_path`, `_file_paths` — defined in Task 2, used in Task 2's `validate_schema`. Not referenced elsewhere.
- `_MUST_NOT_ALIASES` — defined in Task 2, used in Task 2's `read_schema`. Consistent.
- `validate_schema` return type is `SchemaValidation` — consistent throughout Tasks 2–3.
