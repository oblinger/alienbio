"""T030 — registration-gated awareness-dial admission (AUP phase 2's unlock).

The no-peeking rule (:func:`~alienbio.suite.experiment.no_peeking_violation`)
refuses a live model wherever an awareness dial (``monitoring`` / ``framing``
/ ``stakes`` / a guarded drafter's dials …) is in play — correct until the
awareness pre-registration is FILED. Phase 2 needs exactly those arms
admitted on exactly the registered family, and the unlock must be as
auditable as the lock: not an environment variable an agent can export, but
a declaration the guard verifies.

The mechanism:

- **The registry** — ``catalog/registrations.yaml``, a commit-tracked,
  repo-local mapping ``registration id -> entry``. An entry names the OSF id,
  the filing date, the admitted dial set, and the admitted drafter set —
  nothing else (an unknown key is refused, so the registry cannot quietly
  grow side channels). The file only lands by commit, so every unlock has
  provenance.
- **The claim** — an :class:`~alienbio.suite.experiment.ExperimentSpec`
  carries ``registration: <id>``. The guard resolves the claim against the
  registry and admits **exactly** the scoped dials on **exactly** the named
  drafters; any mismatch — missing registry, unknown id, malformed entry,
  a drafter the entry does not name, a guarded dial outside the entry's
  scope — refuses visibly (``ValueError`` or a violation string), never
  silently. An unlicensed sweep stays impossible by construction.
- **The stamp** — the registration id rides every ``records.jsonl`` line
  (written only when a registration is claimed, so unregistered runs'
  records — and the golden hashes — stay byte-unchanged) and the manifest
  carries the fully-resolved entry, so a published record proves its own
  license.

This module is the registry side (parse + validate + resolve); the guard
integration lives in :mod:`~alienbio.suite.guards`
(``registration_admission`` / ``no_peeking_violation``, re-exported by
:mod:`~alienbio.suite.experiment`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

#: The commit-tracked registry, relative to the repository root (resolved by
#: the caller — :mod:`~alienbio.suite.guards` passes ``spec.REPO_ROOT``).
REGISTRY_RELPATH = Path("catalog") / "registrations.yaml"

#: Exactly the keys a registry entry may carry (AUP's preference, verbatim:
#: "the OSF id + filing timestamp + admitted dial set + drafter set, nothing
#: else").
_ENTRY_KEYS = frozenset({"osf", "filed", "dials", "drafters"})

_FILED_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class Registration:
    """One resolved registry entry — a filed pre-registration's license."""

    id: str
    osf: str
    filed: str
    dials: frozenset[str]
    drafters: frozenset[str]

    def to_dict(self) -> dict[str, Any]:
        """The manifest's stamp: the resolved license, JSON-able and sorted."""
        return {
            "id": self.id,
            "osf": self.osf,
            "filed": self.filed,
            "dials": sorted(self.dials),
            "drafters": sorted(self.drafters),
        }


def _str_set(entry_id: str, key: str, value: Any) -> frozenset[str]:
    if (
        not isinstance(value, (list, tuple))
        or not value
        or not all(isinstance(v, str) and v for v in value)
    ):
        raise ValueError(
            f"registration {entry_id!r}: {key!r} must be a non-empty list of names, got {value!r}"
        )
    return frozenset(value)


def _parse_entry(entry_id: str, raw: Any) -> Registration:
    if not isinstance(raw, Mapping):
        raise ValueError(f"registration {entry_id!r}: entry must be a mapping, got {raw!r}")
    unknown = sorted(set(raw) - _ENTRY_KEYS)
    if unknown:
        raise ValueError(
            f"registration {entry_id!r}: unknown key(s) {unknown} — an entry carries exactly "
            f"{sorted(_ENTRY_KEYS)}, nothing else"
        )
    missing = sorted(_ENTRY_KEYS - set(raw))
    if missing:
        raise ValueError(f"registration {entry_id!r}: missing key(s) {missing}")
    osf = raw["osf"]
    if not isinstance(osf, str) or not osf.strip():
        raise ValueError(f"registration {entry_id!r}: 'osf' must be a non-empty string, got {osf!r}")
    filed = raw["filed"]
    filed_str = filed.isoformat() if hasattr(filed, "isoformat") else filed
    if not isinstance(filed_str, str) or not _FILED_RE.match(filed_str):
        raise ValueError(
            f"registration {entry_id!r}: 'filed' must be a YYYY-MM-DD date, got {filed!r}"
        )
    return Registration(
        id=entry_id,
        osf=osf,
        filed=filed_str,
        dials=_str_set(entry_id, "dials", raw["dials"]),
        drafters=_str_set(entry_id, "drafters", raw["drafters"]),
    )


class _UniqueKeyLoader(yaml.SafeLoader):
    """``SafeLoader`` that refuses a mapping with two equal keys (T088
    registration 1: ``safe_load`` keeps the last, so a second ``a:`` block
    silently replaced the license a reviewer reads first)."""


def _construct_unique_mapping(loader: yaml.SafeLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
    seen: set = set()
    for key_node, _value in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise ValueError(f"duplicate key {key!r} at line {key_node.start_mark.line + 1}")
        seen.add(key)
    return loader.construct_mapping(node, deep=deep)


_UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping)


def load_registry(path: Path) -> dict[str, Registration]:
    """Parse + validate the whole registry file at ``path``.

    A missing file is an error only when someone claims a registration —
    callers reach this via :func:`resolve_registration`. An empty (or
    comments-only) file is a valid empty registry. A repeated key — two
    entries under one id, or one field twice — refuses. Any malformed entry
    refuses every claim (fail closed: the file is one audited unit).
    """
    try:
        raw = yaml.load(path.read_text(), Loader=_UniqueKeyLoader) or {}
    except ValueError as exc:
        raise ValueError(f"registration registry {path}: {exc}") from None
    if not isinstance(raw, Mapping):
        raise ValueError(f"registration registry {path}: top level must be a mapping, got {type(raw).__name__}")
    registry: dict[str, Registration] = {}
    for entry_id, entry in raw.items():
        if not isinstance(entry_id, str) or not entry_id.strip():
            raise ValueError(f"registration registry {path}: entry id must be a non-empty string, got {entry_id!r}")
        registry[entry_id] = _parse_entry(entry_id, entry)
    return registry


def resolve_registration(reg_id: str, path: Path) -> Registration:
    """The registration ``reg_id`` claims — refused visibly when the registry
    is missing, unparseable, or does not name the id."""
    if not path.exists():
        raise ValueError(
            f"registration {reg_id!r} claimed but the registry {path} does not exist — "
            "the registry only lands by commit; file the entry first"
        )
    registry = load_registry(path)
    if reg_id not in registry:
        raise ValueError(
            f"registration {reg_id!r} is not in the registry {path} "
            f"(it has: {sorted(registry) or 'no entries'}) — file the entry first"
        )
    return registry[reg_id]
