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
            overlap = set(value) & set(merged)
            if overlap:
                raise ValueError(
                    f"Schema path(s) {sorted(overlap)} appear in multiple "
                    f"[{key}]-aliased sections; each path may appear only once."
                )
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
