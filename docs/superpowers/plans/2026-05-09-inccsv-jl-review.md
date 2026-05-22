# IncCSV.jl Code Review Plan

> **For agentic workers:** This is a research/review plan, not an implementation plan. Each task fetches source material and produces written findings. Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` to run it task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a written report on bugs, design issues, test gaps, documentation gaps, and interoperability concerns in [`IncCSV.jl`](https://github.com/mroughan/IncCSV.jl), suitable to send to the library's author.

**Architecture:** Six analysis tasks — one per concern area — each fetching the relevant source material and producing a section of findings. A final task assembles everything into a polished report saved to `outputs/inccsv-jl-review.md`.

**Tech Stack:** WebFetch to retrieve source from GitHub raw URLs; comparison against the local Python implementation at `/Users/lewis_math/Library/CloudStorage/Box-Box/work/IncCSV.py/inccsv/`.

---

## Output file

All findings accumulate in:
```
outputs/inccsv-jl-review.md
```
Create this file at the start of Task 1 with the header below; each subsequent task appends its section.

```markdown
# Code Review: IncCSV.jl

**Repo:** https://github.com/mroughan/IncCSV.jl  
**Reviewed:** 2026-05-09  
**Reviewer:** Claude (on behalf of the IncCSV.py project)  
**Python counterpart:** https://github.com/lewismath/IncCSV.py

---
```

---

## Source URLs

All source is fetched via raw GitHub URLs:

| File | URL |
|---|---|
| `src/IncCSV.jl` | `https://raw.githubusercontent.com/mroughan/IncCSV.jl/main/src/IncCSV.jl` |
| `test/runtests.jl` | `https://raw.githubusercontent.com/mroughan/IncCSV.jl/main/test/runtests.jl` |
| `README.md` | `https://raw.githubusercontent.com/mroughan/IncCSV.jl/main/README.md` |
| `ARCHITECTURE.md` | `https://raw.githubusercontent.com/mroughan/IncCSV.jl/main/ARCHITECTURE.md` |
| `docs/src/index.md` | `https://raw.githubusercontent.com/mroughan/IncCSV.jl/main/docs/src/index.md` |
| `docs/src/api.md` | `https://raw.githubusercontent.com/mroughan/IncCSV.jl/main/docs/src/api.md` |
| `docs/src/metadata.md` | `https://raw.githubusercontent.com/mroughan/IncCSV.jl/main/docs/src/metadata.md` |
| `docs/src/schema.md` | `https://raw.githubusercontent.com/mroughan/IncCSV.jl/main/docs/src/schema.md` |
| `test/test.dat` | `https://raw.githubusercontent.com/mroughan/IncCSV.jl/main/test/test.dat` |
| Tutorial example | `https://raw.githubusercontent.com/mroughan/IncCSV.jl/main/artifacts/examples/tutorial.inc` |

---

## Task 1: Parser Internals

**Focus:** `isdelimiter`, `strip_comment`, `parse_value`, and the metadata-block splitting logic inside `src/IncCSV.jl`.

**Files:**
- Fetch: `src/IncCSV.jl` (full source)
- Append findings to: `outputs/inccsv-jl-review.md`

- [ ] **Step 1: Fetch the source**

  Fetch `https://raw.githubusercontent.com/mroughan/IncCSV.jl/main/src/IncCSV.jl` in full.

- [ ] **Step 2: Analyse `isdelimiter`**

  Find the `isdelimiter` function. Answer:
  - Does it use `\p{Pd}` (Unicode dash category) or a hardcoded character list?
  - Does it require exactly 3+ dashes, or is the threshold configurable?
  - Does it correctly allow optional whitespace before, between, or after the dashes?
  - Does it allow trailing `#`/`;` comments on the delimiter line, as the spec requires?
  - What happens with a line like `--- not a comment` (text after dashes that isn't a comment marker)?
  - What happens with mixed-category dashes, e.g. `--—` (2 ASCII hyphens + 1 em-dash)?

- [ ] **Step 3: Analyse `strip_comment`**

  Find the `strip_comment` function. Answer:
  - Does it handle inline comments on `key = value` lines?
  - Does it correctly preserve values that ARE a comment character, e.g. `delimiter = ;`?
    (If it strips bare `;` from the value, this is a bug — the Python implementation had to fix the same issue.)
  - Does it respect double-quoted values? E.g. `title = "say # hi"` should not be stripped.
  - Does it handle escaped quotes inside quoted values (`\"`)?

- [ ] **Step 4: Analyse `parse_value`**

  Find `parse_value`. Answer:
  - What types does it return? The spec says only `Int` and `String`. Are there any others (e.g. `Bool`, `Float64`)?
  - Does it correctly infer integers only for the pattern `^[+-]?\d+$`? Or does it also infer floats?
  - Does quoted `"007"` return a `String` rather than `Int`?
  - What happens with an empty value (`key = ` with nothing after `=`)?
  - What happens with a value that is only whitespace (`key =   `)?

- [ ] **Step 5: Analyse the metadata-block splitting**

  Find the function that opens a file and splits it into metadata lines + CSV start position. Answer:
  - Does it read the whole file into memory, or does it read line-by-line and stop at the closing delimiter? (The spec recommends line-by-line to handle large files.)
  - What error is raised when the opening delimiter exists but the closing delimiter is missing? Is the message human-readable with a filename/line number?
  - What happens with a plain CSV file (no opening delimiter)? Does it return cleanly with empty metadata?
  - What happens with an empty file?
  - Is the closing-delimiter search non-greedy (stops at the FIRST closing delimiter), or could it skip past it?

- [ ] **Step 6: Analyse key/section name validation**

  Find where key names and section names are validated. Answer:
  - What characters are forbidden in key and section names?
  - Is whitespace in names rejected? (The spec explicitly requires this.)
  - Are duplicate keys detected? Is the error message specific (includes line number)?
  - Are duplicate sections detected?
  - Are empty sections (declared but no properties) rejected?
  - Are empty key names (lines like `= value`) rejected?

- [ ] **Step 7: Document findings**

  Append a section to `outputs/inccsv-jl-review.md`:

  ```markdown
  ## 1. Parser Internals

  ### Findings
  [List each finding as a bullet: Bug / Design Issue / Confirmed Correct / Note]

  #### Bugs
  [Each bug: description, the input that triggers it, what happens vs. what should happen]

  #### Design Issues
  [Each design concern with explanation]

  #### Confirmed Correct
  [Notable things that work as specified]
  ```

---

## Task 2: I/O Functions (`readinc` / `writeinc`)

**Focus:** How `readinc` and `writeinc` handle the `[structure]` section, CSV options, type validation, and edge cases.

**Files:**
- Fetch: `src/IncCSV.jl` (already fetched in Task 1 — do not re-fetch)
- Fetch: `https://raw.githubusercontent.com/mroughan/IncCSV.jl/main/artifacts/examples/tutorial.inc`
- Append findings to: `outputs/inccsv-jl-review.md`

- [ ] **Step 1: Analyse `readinc` signature and overloads**

  Find all definitions of `readinc`. Answer:
  - What is the full function signature? Does it accept `**kwargs` (Julia: keyword args) forwarded to CSV.jl?
  - What keyword argument names does it accept/forward? Are they the same as CSV.jl's, or renamed?
  - Does it accept a `sink` type (e.g. `DataFrame`) as the second argument for direct conversion?
  - What does it return when reading a plain CSV (no INC metadata)?

- [ ] **Step 2: Analyse `[structure]` handling in `readinc`**

  Find where `[structure]` metadata keys are mapped to CSV.jl keyword arguments. Answer:
  - What `[structure]` keys are mapped? Make a complete list.
  - Are caller-supplied keyword arguments given priority over `[structure]` values?
  - Is the `comment` key handled specially (line-level filtering vs. passed to CSV.jl)?
  - What happens with an unknown key in `[structure]`? Silently ignored, warning, or error?

- [ ] **Step 3: Analyse `writeinc`**

  Find `writeinc`. Answer:
  - Does it validate metadata value types before writing? What types are rejected?
  - Does it correctly quote string values that look like integers (e.g. writing `"42"` so they round-trip as strings)?
  - Does it handle string values containing `"` or `\`? Are they escaped in the output?
  - Does it handle values containing newlines? Are they rejected or silently truncated?
  - Does it write global keys before section keys?
  - What happens if `rows` is empty?
  - What happens with ragged rows (different keys across rows)?

- [ ] **Step 4: Analyse `metadata()` and `table()` accessors**

  Find the `metadata()` and `table()` accessor functions. Answer:
  - What does `metadata()` return? A flat `Dict`, a nested `Dict`, or a custom type?
  - What does `table()` return? A `DataFrame`? A `Tables.jl`-compatible object?
  - Can the result of `table()` be sunk to an arbitrary `Tables.jl` sink?

- [ ] **Step 5: Document findings**

  Append to `outputs/inccsv-jl-review.md`:

  ```markdown
  ## 2. I/O Functions

  ### Findings
  [Bugs / Design Issues / Confirmed Correct, same structure as Task 1]

  ### [structure] key mapping table
  | `[structure]` key | CSV.jl kwarg | Notes |
  |---|---|---|
  | ... | ... | ... |
  ```

---

## Task 3: Schema Validation and Summary

**Focus:** `readschema`, `validateschema`, `IncSchema`, `IncSummary`, `summarise`.

**Files:**
- Fetch: `src/IncCSV.jl` (already fetched)
- Fetch: `https://raw.githubusercontent.com/mroughan/IncCSV.jl/main/docs/src/schema.md`
- Fetch one schema example: `https://raw.githubusercontent.com/mroughan/IncCSV.jl/main/artifacts/schema_examples/restrictive/schema.inc`
- Append findings to: `outputs/inccsv-jl-review.md`

- [ ] **Step 1: Analyse `IncSchema` type**

  Find the `IncSchema` type definition. Answer:
  - What fields does it have?
  - How is `allow_extra` represented and what is its default?
  - Are the `MUST`/`MAYBE` section names hardcoded in the schema reader, or configurable?

- [ ] **Step 2: Analyse `validateschema`**

  Find all overloads of `validateschema`. Answer:
  - What does it return? Does `SchemaValidation` have `valid`, `missing`, `extra` fields?
  - Does it validate only global metadata keys, or also section contents?
  - When `allow_extra = false`, does an extra field make `valid = false`?
  - When a MUST field is absent, does it appear in `missing`?
  - Does a field in MAYBE that is present count as extra?
  - Are section dicts (e.g. `[columns]`) counted as extra global keys? They should not be.

- [ ] **Step 3: Analyse `readschema`**

  Find `readschema`. Answer:
  - Does it read schema files using `readinc` (code reuse) or has its own parsing path?
  - How does it handle `allow_extra = false` vs. `false` as a string (case sensitivity)?
  - Does it recognise `[schema]`, `[MUST]`, `[MAYBE]`, `[description]` — are these case-sensitive?

- [ ] **Step 4: Analyse `summarise` and `IncSummary`**

  Find the type and function. Answer:
  - What fields does `IncSummary` have?
  - Does `summarise` count section keys toward `n_metadata_keys`, or only global keys?
  - Does `printsummary` write to stdout or to an IO argument?

- [ ] **Step 5: Document findings**

  Append to `outputs/inccsv-jl-review.md`:

  ```markdown
  ## 3. Schema Validation and Summary

  ### Findings
  [Bugs / Design Issues / Confirmed Correct]
  ```

---

## Task 4: Test Coverage Analysis

**Focus:** What the test suite covers, and what it misses.

**Files:**
- Fetch: `https://raw.githubusercontent.com/mroughan/IncCSV.jl/main/test/runtests.jl`
- Fetch: `https://raw.githubusercontent.com/mroughan/IncCSV.jl/main/test/test.dat`
- Append findings to: `outputs/inccsv-jl-review.md`

- [ ] **Step 1: Map the 19 test cases**

  List every `@testset` block and what it tests (one line per test case).

- [ ] **Step 2: Check for missing coverage against this checklist**

  For each item, note whether it is tested (✓), partially tested (△), or absent (✗):

  **Parser edge cases:**
  - `✓/△/✗` Delimiter line: exactly 3 dashes
  - `✓/△/✗` Delimiter line: 4+ dashes
  - `✓/△/✗` Delimiter line: Unicode dashes (en-dash, em-dash)
  - `✓/△/✗` Delimiter line: leading/trailing whitespace
  - `✓/△/✗` Delimiter line: trailing `#` comment
  - `✓/△/✗` Delimiter line: non-comment trailing text (should NOT be a delimiter)
  - `✓/△/✗` Missing closing delimiter → error
  - `✓/△/✗` Empty metadata block (two consecutive `---`)
  - `✓/△/✗` Empty file
  - `✓/△/✗` Duplicate global key → error with line number
  - `✓/△/✗` Duplicate section → error with line number
  - `✓/△/✗` Invalid characters in key name → error
  - `✓/△/✗` Invalid characters in section name → error
  - `✓/△/✗` Empty section body → error
  - `✓/△/✗` `parse_value`: bare `;` or `#` as value (e.g. `delimiter = ;`)
  - `✓/△/✗` `parse_value`: quoted integer stays as string (`"42"` → `String`)
  - `✓/△/✗` `parse_value`: empty value (`key = `)
  - `✓/△/✗` `parse_value`: value with escaped quote (`"say \"hi\""`)
  - `✓/△/✗` `parse_value`: value with escaped backslash (`"back\\slash"`)

  **I/O edge cases:**
  - `✓/△/✗` `writeinc`: float metadata value → error
  - `✓/△/✗` `writeinc`: bool metadata value → error (or correct handling)
  - `✓/△/✗` `writeinc`: string value that looks like integer round-trips as string
  - `✓/△/✗` `writeinc`: string value containing `"` → escaped correctly
  - `✓/△/✗` `writeinc`: string value containing newline → error
  - `✓/△/✗` `writeinc`: empty rows
  - `✓/△/✗` `readinc`: caller kwargs override `[structure]` values
  - `✓/△/✗` `readinc`: `comment` key in `[structure]` filters CSV lines

  **Schema:**
  - `✓/△/✗` `allow_extra = false` rejects extra fields
  - `✓/△/✗` MAYBE field present is not counted as extra
  - `✓/△/✗` Section dicts not counted as extra global keys
  - `✓/△/✗` Case sensitivity of section names (`[MUST]` vs `[must]`)

- [ ] **Step 3: Document findings**

  Append to `outputs/inccsv-jl-review.md`:

  ```markdown
  ## 4. Test Coverage

  ### Test case map
  | # | Name | What it covers |
  |---|---|---|
  | 1 | ... | ... |
  ...

  ### Coverage gaps (untested behaviours)
  [List each ✗ item with a note on why it matters]

  ### Partial coverage (△)
  [List each △ item with a note on what's missing]
  ```

---

## Task 5: Documentation Review

**Focus:** README, API docs, architecture doc — accuracy, completeness, and usability.

**Files:**
- Fetch: `https://raw.githubusercontent.com/mroughan/IncCSV.jl/main/README.md`
- Fetch: `https://raw.githubusercontent.com/mroughan/IncCSV.jl/main/ARCHITECTURE.md`
- Fetch: `https://raw.githubusercontent.com/mroughan/IncCSV.jl/main/docs/src/index.md`
- Fetch: `https://raw.githubusercontent.com/mroughan/IncCSV.jl/main/docs/src/api.md`
- Fetch: `https://raw.githubusercontent.com/mroughan/IncCSV.jl/main/docs/src/metadata.md`
- Append findings to: `outputs/inccsv-jl-review.md`

- [ ] **Step 1: Review the README**

  Answer:
  - Does the README explain what the INC format is?
  - Does it show a quick-start example (read and write) that a new user can copy-paste?
  - Are all public API functions mentioned?
  - Are installation instructions present and accurate?
  - Are there any code examples that reference functions that don't exist or have been renamed?
  - Is the format spec (delimiter syntax, metadata rules, `[structure]` keys) documented here or linked?

- [ ] **Step 2: Review the API docs**

  Answer:
  - Does every exported function have a docstring?
  - Are argument types and return types documented?
  - Are the `[structure]` keys documented with their effect?
  - Are error conditions documented (what raises, what the message contains)?

- [ ] **Step 3: Review the architecture doc**

  Answer:
  - Does `ARCHITECTURE.md` explain the split between metadata parsing and CSV I/O?
  - Does it cover the design decisions (why INI, why `---`, why Int/String only)?
  - Is it up to date with the current implementation?

- [ ] **Step 4: Check example files for accuracy**

  Fetch `https://raw.githubusercontent.com/mroughan/IncCSV.jl/main/artifacts/examples/tutorial.inc`.
  
  Answer:
  - Do the example files conform to the format spec (valid metadata syntax, correct delimiter)?
  - Does any example use features not yet implemented (would break a new user trying to run them)?

- [ ] **Step 5: Document findings**

  Append to `outputs/inccsv-jl-review.md`:

  ```markdown
  ## 5. Documentation

  ### Findings
  [Accuracy issues / Missing content / Outdated content / Confirmed Good]
  ```

---

## Task 6: Interoperability Analysis

**Focus:** Specific behaviours where the Julia and Python implementations might diverge, producing files that one can write but the other cannot read.

**Files:**
- Fetch: `src/IncCSV.jl` (already fetched)
- Read local Python source: `inccsv/_parser.py`, `inccsv/_reader.py`, `inccsv/_writer.py`
- Append findings to: `outputs/inccsv-jl-review.md`

- [ ] **Step 1: Compare delimiter detection**

  Answer for both Julia and Python:
  - Same Unicode category check (`\p{Pd}` / `unicodedata.category == 'Pd'`)?
  - Same minimum dash count (3)?
  - Same whitespace tolerance?
  - Same comment-on-delimiter-line behaviour?

  **Interop risk:** If Julia accepts a delimiter line that Python rejects (or vice versa), a file written by one cannot be read by the other.

- [ ] **Step 2: Compare `parse_value` / integer inference**

  Answer:
  - Does Julia infer integers with the same regex (`^[+-]?\d+$`)?
  - Does Julia handle leading zeros differently (e.g. `007` → `Int(7)` vs. string)?
  - Does Julia's quoting escape syntax match Python's (`\"` and `\\`)?
  - Does Julia handle empty values the same way?

  **Interop risk:** A file written by Julia with a value like `+5` or `007` may be read differently by Python.

- [ ] **Step 3: Compare `[structure]` key names**

  Make a mapping table:

  | Behaviour | Julia key | Python key | Same? |
  |---|---|---|---|
  | CSV delimiter | `delimiter` | `delimiter` | ? |
  | Quote character | `quotechar` | `quotechar` | ? |
  | Comment character | `comment` | `comment` | ? |
  | ... | ... | ... | ? |

  Note any keys that Julia supports but Python does not, or vice versa.

- [ ] **Step 4: Compare metadata write quoting**

  Answer:
  - Does Julia quote string values that look like integers (so they round-trip as strings)?
  - Does Julia quote empty strings?
  - Does Julia quote strings with leading/trailing whitespace?
  - Are the escape sequences for `"` and `\` identical?

  **Interop risk:** A file written by Python with `id = "42"` must be read by Julia as the string `"42"`, not the integer `42`.

- [ ] **Step 5: Compare error messages**

  The format spec says error messages should be human-friendly and agreed across implementations. List any error conditions where the messages differ significantly.

- [ ] **Step 6: Identify any Julia-only features**

  Note any features in `IncCSV.jl` that are not present in `inccsv` (Python), e.g.:
  - Additional `[structure]` keys
  - Additional metadata type support
  - Any format extensions

- [ ] **Step 7: Document findings**

  Append to `outputs/inccsv-jl-review.md`:

  ```markdown
  ## 6. Interoperability with inccsv (Python)

  ### Confirmed compatible behaviours
  [Things that work the same way in both]

  ### Interoperability risks
  [Each risk: the behaviour, what Julia does, what Python does, which files are affected]

  ### Julia-only features (not yet in Python)
  [List with brief notes on whether they should be ported]
  ```

---

## Task 7: Assemble the Final Report

**Focus:** Polish findings into a clean, author-facing document.

**Files:**
- Read: `outputs/inccsv-jl-review.md` (accumulated findings from Tasks 1–6)
- Rewrite: `outputs/inccsv-jl-review.md` (final polished version)

- [ ] **Step 1: Read all accumulated findings**

  Read `outputs/inccsv-jl-review.md` in full.

- [ ] **Step 2: Write a prioritised executive summary**

  Prepend to the report (after the header):

  ```markdown
  ## Executive Summary

  Brief 2–3 sentence overview of the library's overall quality.

  ### Issues by priority

  #### Critical (correctness bugs — affect all users)
  - [Issue]: [one-line description]
  ...

  #### Important (design concerns or significant gaps)
  - [Issue]: [one-line description]
  ...

  #### Minor (documentation, style, nice-to-have)
  - [Issue]: [one-line description]
  ...

  ### Interoperability verdict
  [One paragraph: is the Python implementation compatible? What are the risks?]
  ```

- [ ] **Step 3: Verify every finding has a reproduction case**

  For each Bug or Interoperability Risk in the report:
  - Does it include a concrete example (the input that triggers it, and what happens vs. what should happen)?
  - If not, add one. Use the format:

    ```
    Input:  `key = value`
    Got:    <what IncCSV.jl produces>
    Want:   <what the spec requires>
    ```

- [ ] **Step 4: Remove duplicates and smooth transitions**

  Read the report top-to-bottom and:
  - Remove any finding that appears more than once.
  - Add one-sentence section intros where context is missing.
  - Check that the Executive Summary matches the body.

- [ ] **Step 5: Save the final report**

  Write the polished version to `outputs/inccsv-jl-review.md`. Print a confirmation with the file path and a one-line summary of how many issues were found at each priority level.

---

## Appendix: Python implementation files for reference

When doing the interoperability analysis (Task 6), read these local files directly:

```
/Users/lewis_math/Library/CloudStorage/Box-Box/work/IncCSV.py/inccsv/_parser.py
/Users/lewis_math/Library/CloudStorage/Box-Box/work/IncCSV.py/inccsv/_reader.py
/Users/lewis_math/Library/CloudStorage/Box-Box/work/IncCSV.py/inccsv/_writer.py
/Users/lewis_math/Library/CloudStorage/Box-Box/work/IncCSV.py/inccsv/_schema.py
/Users/lewis_math/Library/CloudStorage/Box-Box/work/IncCSV.py/inccsv/_summary.py
```
