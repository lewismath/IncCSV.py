# Response to IncCSV.jl Review

Original review: `review/inccsv-jl-review.md`  
Response date: 2026-05-11

This note records the changes made in response to the Julia/Python interoperability review, plus the issues deliberately left unchanged. The main goals were to improve round-trip safety, make schema behavior explicit, and preserve the lightweight INC design.

## Changes Made

### Metadata Parsing

- Bare `;` and `#` values are now parsed as literal values, so entries such as `delim = ;` and `comment = #` work as intended.
- Inline comments are now comments only when they follow a nonempty value and are separated by whitespace.
- Backslash is treated as an escape character only inside quoted strings. Outside quotes it is ordinary metadata text.
- Quoted metadata now round-trips `#`, `;`, `"`, and `\` correctly.
- Empty metadata sections are rejected during parsing.
- Missing closing delimiter errors now include the file path and the last metadata line read, which makes malformed files easier to diagnose.

### Metadata Writing

- String values containing `\n` or `\r` are rejected because they would produce malformed INC metadata.
- Strings containing `"` or `\` are quoted and escaped when written.
- Writer-side key and section validation now uses the same naming rules as the reader.
- Empty sections are rejected at write time.
- Metadata is written in deterministic sorted order: top-level scalar keys first, then sections, then sorted keys inside each section.

### CSV Structure Interoperability

- `[structure] delimiter = ...` is accepted as a read-only alias for CSV.jl's `delim` keyword.
- Both `delim` and `delimiter` canonicalize to `:delim`.
- If both appear, `delimiter` wins, matching the Python implementation.
- CSV keyword options are applied to the CSV component of the file, not to the metadata preamble.

### Schema Validation

- Schema paths declared in more than one requirement class are rejected, including RFC 2119 aliases such as `REQUIRED`, `SHALL`, `SHALL_NOT`, and `MAY`.
- Schema paths are explicitly limited to either top-level names or one-level `section.key` paths.
- Deeper paths such as `a.b.c` are rejected with an `ArgumentError`.
- Parent sections are treated as known when a declared schema field uses that parent, so `columns.score` prevents `columns` from being reported as extra.
- `MUST_NOT` fields are supported and reported through `SchemaValidation.forbidden`.

### Examples And Tests

- Added valid examples for parser edge cases, escaped metadata, delimiter aliases, and delimiter precedence.
- Added `artifacts/invalid_examples/` with small malformed files demonstrating invalid behaviors.
- Added parser tests for literal comment markers, whitespace-delimited comments, quoted values, backslashes, empty sections, and missing delimiters.
- Added writer tests for escaping, newline rejection, invalid names, empty sections, and stable ordering.
- Added structure tests for `delimiter`, comment markers, and `delim`/`delimiter` precedence.
- Added schema tests for duplicate requirement declarations, alias collisions, parent-section handling, `MUST_NOT`, and unsupported deep paths.
- Updated `printsummary` so pretty-printed summaries end with a newline.

### Documentation

- Metadata documentation now describes UTF-8 assumptions, comment parsing, empty metadata values, invalid empty sections, naming rules, writer validation, common error messages, and `[structure]` behavior.
- README now includes installation instructions for the unregistered GitHub package.
- README now mentions `readschema`, `validateschema`, `summarise`, and `printsummary`.
- README documents that plain CSV passthrough returns empty metadata and does not expose a separate "was INC" flag.
- Schema documentation now states that requirement words follow RFC 2119, with `MUST_NOT` using an underscore to fit the INC grammar.
- Architecture documentation now lists `IncSummary`, `summarise`, and `printsummary` as public APIs and records the one-level schema path model.

## Non-Changes And Rationale

### Plain CSV Passthrough

Plain CSV passthrough is retained. It is a core design principle: existing CSV files should remain readable without conversion. The ambiguity is now documented: a plain CSV file reads as an INC file with empty metadata, and there is no separate flag indicating whether an INC metadata block was present.

### No Automatic `[structure]` Metadata On Write

`writeinc(...; delim=...)` still does not invent or update `[structure]` metadata automatically. This avoids hidden precedence rules between explicit user metadata and writer keyword arguments. INC files can still store structure metadata, but the metadata must be supplied deliberately.

### Mixed Unicode Dash Delimiters

Mixed Unicode dash delimiters remain accepted. This was an explicit format choice to allow any three consecutive Unicode dash-punctuation characters as the metadata/data separator. The behavior is documented and tested.

### No Interior Whitespace In Delimiter Lines

Delimiter lines such as `- - -` remain invalid. The delimiter rule stays simple: the three dash-punctuation characters must be consecutive.

### Informational Schema Type Descriptors

Schema type descriptors remain arbitrary strings. They are intended to be lightweight documentation for humans and downstream tools, not a complete type system enforced by IncCSV.jl.

### `SchemaValidation.missing`

`SchemaValidation.missing` is retained for public API compatibility, even though the name overlaps with Julia's `missing` value. The review concern is valid, but renaming the field would be a breaking API change with limited practical benefit.

### One-Level Schema Paths

Julia's one-level `section.key` schema path model is retained as the canonical INC behavior. It keeps validation close to the underlying metadata grammar and avoids introducing nested data structures into the lightweight schema layer.

### Section Parents In Field Paths

Section parents may still appear in field-path summaries. They are useful for reporting and inspection, while validation now avoids incorrectly treating declared parent sections as unexpected extras.

### File-Oriented `writeinc`

The current file-oriented `writeinc` API is retained. More general stream-oriented writing could be useful later, but it is not needed to resolve the correctness and interoperability bugs identified by the review.
