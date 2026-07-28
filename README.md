# IncCSV.py

A Python implementation of the [INC file format](https://github.com/mroughan/IncCSV.jl), interoperable with the original Julia library [`IncCSV.jl`](https://github.com/mroughan/IncCSV.jl).

## What is INC?

INC (**IN**i-**C**sv) is a lightweight file format that embeds INI-style metadata directly inside a CSV file, separated by a `---` delimiter:

```
---
title = Sensor readings
version = 1
[columns]
time = seconds
temperature = Celsius
---
time,temperature
0,21.4
1,21.8
2,22.1
```

The goal is to make tabular data self-describing — units, provenance, and other context travel with the file rather than being stored separately. Plain CSV files are read without modification, so the format is fully backward compatible.

See the [Julia reference implementation](https://github.com/mroughan/IncCSV.jl) for the full format specification and design rationale.

## Interactive demos

**[lewismath.github.io/IncCSV.py](https://lewismath.github.io/IncCSV.py/)** — live Python demos in the browser (no installation needed):
- [Playground](https://lewismath.github.io/IncCSV.py/playground.html) — parse and write INC text interactively
- [Examples](https://lewismath.github.io/IncCSV.py/examples.html) — common patterns with Python code
- [Schema validator](https://lewismath.github.io/IncCSV.py/schema.html)
- [SIR epidemic model](https://lewismath.github.io/IncCSV.py/sir.html) — simulation with INC download
- [Linear regression](https://lewismath.github.io/IncCSV.py/regression.html) — annotate data with fitted parameters

## Installation

```bash
pip install inccsv
```

With pandas support:

```bash
pip install inccsv[pandas]
```

## Usage

### Reading

```python
import inccsv

# Read an INC file
f = inccsv.read_inc("data.inc")
print(f.metadata)          # {'title': 'Sensor readings', 'version': 1, 'columns': {...}}
print(f.rows)              # [{'time': '0', 'temperature': '21.4'}, ...]

# Convert to a pandas DataFrame
df = f.to_dataframe()

# Plain CSV files work too
f = inccsv.read_inc("data.csv")
```

### Writing

```python
rows = [
    {"time": "0", "temperature": "21.4"},
    {"time": "1", "temperature": "21.8"},
]
metadata = {
    "title": "Sensor readings",
    "version": 1,
    "columns": {"time": "seconds", "temperature": "Celsius"},
}

inccsv.write_inc("data.inc", rows, metadata=metadata)
```

### Schema validation

A schema is itself an INC file that declares required and optional metadata fields:

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

```python
schema = inccsv.read_schema("schema.inc")
result = inccsv.validate_schema(f, schema)
print(result.valid)    # True / False
print(result.missing)  # required fields absent from the file
print(result.extra)    # fields not declared in the schema
```

### Summary

```python
s = inccsv.summarise(f)
print(s.n_rows, s.n_cols)
inccsv.print_summary(f)
```

## Format notes

- Metadata values are `int` (unquoted integers) or `str` (everything else). Quote values that look like integers to preserve them as strings: `id = "007"`.
- The `[structure]` section passes CSV options to the reader: `delimiter`, `quotechar`, `comment`.
- `write_inc` also applies writer-relevant `[structure]` metadata (`delim`/`delimiter`, `quotechar`, `escapechar`) to the CSV component it writes. An explicit `csv_kwargs` value that contradicts `[structure]` metadata raises `ValueError` rather than writing a file whose metadata misdescribes its own CSV component. `write_inc` never infers or writes `[structure]` metadata on its own — supply it explicitly if a file needs it.
- The delimiter line accepts any sequence of 3+ Unicode dash characters (`-`, `–`, `—`, …).
- Files are UTF-8 encoded.

## Interoperability

This library aims to be fully interoperable with [`IncCSV.jl`](https://github.com/mroughan/IncCSV.jl). Files written by either library should be readable by the other.

## Development

```bash
git clone https://github.com/lewismath/IncCSV.py
cd IncCSV.py
pip install -e ".[dev]"
pytest
```
