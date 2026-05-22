# IncCSV.py Interoperability Review

Repository reviewed: <https://github.com/lewismath/IncCSV.py>  
Review date: 2026-05-13  
Reference implementation: local `IncCSV.jl`

This review considers whether `IncCSV.py` interoperates with the Julia implementation and whether it generally meets the goals and aspirations of INC: lightweight inclusive metadata, plain CSV compatibility, simple parsing rules, and minimal dependency burden.

## Overall Assessment

`IncCSV.py` is already close to the Julia implementation. It has the right overall shape: no required third-party dependencies, standard-library CSV handling, UTF-8 files, plain CSV passthrough, simple `int | str` metadata values, optional pandas conversion, schemas stored as INC files, and a compact public API.

The main remaining risks are contract drift rather than philosophical drift. The Python package generally understands the INC model, but a few parser, writer, and schema edge cases should be tightened so that files written by either implementation remain readable by the other.

## Interoperability Issues

### Writer Does Not Validate Metadata Names

`inccsv/_writer.py` serializes metadata keys and section names directly. This allows Python to write files that both Python and Julia later reject.

For example, Python can currently write:

```ini
---
bad key = v
---
a
1
```

This violates the INC metadata name rules because keys and section names must not contain whitespace or reserved syntax characters. The writer should validate top-level keys, section names, and section keys using the same rules as the reader.

Priority: high. This is the clearest remaining round-trip safety issue.

### Schema Alias Sections Are Not Merged

`inccsv/_schema.py` returns only the first section matching a set of aliases. For example, if a schema contains both `[MUST]` and `[REQUIRED]`, only one is used.

This differs from Julia, which merges alias sections into the same requirement class and rejects duplicate paths across requirement classes. The Python behavior can silently drop schema declarations, which is risky.

The Python implementation should either:

- merge all alias sections for each requirement class, matching Julia; or
- reject multiple alias sections for the same class with a clear error.

The first option is more interoperable with Julia.

Priority: high.

### README Still Uses `[MAYBE]`

The Python README still shows `[MAYBE]` in the schema example. The current Julia-canonical schema language follows RFC 2119 and uses:

- `[MUST]`
- `[MUST_NOT]`
- `[OPTIONAL]`

Aliases such as `[REQUIRED]`, `[SHALL]`, `[SHALL_NOT]`, and `[MAY]` may be accepted for reading, but examples should teach the canonical form. `[MAYBE]` should be removed from prominent documentation unless it is explicitly described as a legacy alias.

Priority: medium.

### Schema Path Validation Is Weaker Than Julia

Python rejects paths deeper than one section level, such as `a.b.c`, which matches Julia. However, it does not appear to validate each path component with the same name rules as metadata keys.

This means malformed schema paths such as:

```ini
[MUST]
a. = String
.key = String
bad key = String
```

may not be rejected consistently. Julia requires schema paths to be either a top-level name or a one-level `section.key` path, with each component satisfying the metadata name rules.

Priority: medium.

### `[structure]` Validation Is Looser

The Julia implementation now treats `[structure]` as a small explicit allowlist:

- `delim`
- `delimiter`
- `quotechar`
- `escapechar`
- `comment`
- `header`
- `footerskip`

Python currently accepts a broader set of Julia-oriented keys for compatibility, including keys that are no longer part of the Julia `[structure]` contract, such as `skipto`, `limit`, `ignoreemptyrows`, and `normalizenames`.

That means Python may silently accept a file with structure metadata that Julia would reject. For interoperability, Python should align to the Julia allowlist above and validate values according to the same classes:

- character values: `delimiter`, `delim`, `quotechar`, and `escapechar`;
- string values: `comment`;
- integer values: `header` and `footerskip`.

Other CSV parser options should be passed as language-specific reader arguments rather than stored in `[structure]`.

Python should also accept Julia's `"\\t"` tab alias in addition to `tab`.

Priority: medium.

### Missing Closing Delimiter Diagnostics Are Slightly Behind Julia

Python includes the path when an opening metadata delimiter has no closing delimiter. Julia now also reports the last metadata line read. Python could improve this message for easier debugging.

Priority: low.

## Interoperability Strengths

`IncCSV.py` already matches Julia well in several important places:

- bare `;` and `#` metadata values are preserved;
- quoted strings, escaped quotes, escaped backslashes, integers, and empty strings are mostly aligned;
- empty metadata sections are rejected;
- Unicode dash delimiters are supported;
- `delimiter` and `delim` are both accepted, with `delimiter` taking precedence;
- plain CSV passthrough is supported;
- metadata writing is deterministic;
- strings are quoted conservatively enough to avoid common parser surprises;
- `MUST`, `MUST_NOT`, `OPTIONAL`, and several RFC 2119 aliases are present;
- pandas support is optional rather than mandatory.

These choices fit the INC goal of staying small, readable, and easy to adopt.

## Fit To INC Goals

The Python implementation is philosophically well aligned with INC. It does not attempt to replace richer metadata systems. Instead, it provides a small amount of metadata directly inside the file, while leaving the tabular payload as ordinary CSV.

That is the right direction. INC is valuable precisely because it keeps the common case simple: a human-readable metadata block, a clear delimiter, and familiar CSV data. The Python implementation preserves that feel.

The main recommendation is to add shared cross-language fixtures and tests, not to make the Python implementation more elaborate. A small compatibility suite using checked-in valid and invalid `.inc` files would catch most remaining drift without adding conceptual weight.

## Recommended Follow-Up

1. Add writer-side metadata name validation in Python.
2. Merge schema alias sections or reject multiple aliases explicitly.
3. Update Python documentation to prefer `[OPTIONAL]` over `[MAYBE]`.
4. Validate schema path components using the same rules as metadata names.
5. Align `[structure]` value validation with Julia's explicit allowlist: `delim`, `delimiter`, `quotechar`, `escapechar`, `comment`, `header`, and `footerskip`.
6. Add cross-language fixtures shared between `IncCSV.jl` and `IncCSV.py`.
7. Keep the Python package dependency-light; optional pandas support is the right design.

## Verification Notes

The Python repository was cloned to `/tmp/IncCSV.py-review`. After installing `python3.12-venv`, a local virtual environment was created and the package was installed with development extras:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m pytest
```

The test suite passed:

```text
141 passed in 0.23s
```

Additional direct probes were run against the cloned repository to confirm the writer-name and schema-alias issues described above. The passing test suite is therefore a good sign for the covered behavior, but it does not cover all of the remaining Julia interoperability edge cases identified in this review.
