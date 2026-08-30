"""The catalog zeros as golden regressions (M48.4, landed with M47.4).

Every scripted ``catalog/experiments/*.yaml`` runs end to end and the
canonical hash of its ``records.jsonl`` — every line as sorted-key JSON with
the one wall-clock field (``wall_time_s``) removed — must equal the pinned
value. Any change to generation, scoring, the brief, the oracle or the record
store shows up here as a diff; that is the point. When a change is *meant*
to alter records, re-pin with ``GOLDEN_UPDATE=1 uv run pytest
tests/suite/test_golden_experiments.py`` and review the new hashes in the
commit.

The pinned values are the pre-M47.4 loader's output (2026-08-30), so this
is also the proof that the ``!experiment`` front end changed nothing at
runtime. ``exp4-first-live`` is paid and excluded. Offline, scripted only.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from alienbio.suite.experiment import load_spec, run_experiment

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "catalog" / "experiments"

#: name -> sha256 of the canonical record store (see module docstring).
GOLDEN: dict[str, str] = {
    "exp1": "d27df0c9a76a0860",
    "exp10": "7592c98d42ad46a2",
    "exp2": "889a9f34d31d935b",
    "exp3": "6bc15405378e2870",
    "exp4": "8e0e6722ae158c93",
    "exp4-diagnose-zero": "73856a219c32e9fe",
    "exp4-zero": "a13008737eabb995",
    "exp5": "17efc79e61ef29a1",
    "exp6": "3586c2ca5e14eef1",
    "exp7": "7f094eaeb6870b6b",
    "exp8": "b1107aa7472e30c6",
    "exp9": "1085bdce1c0e862f",
}

PAID = {"exp4-first-live"}


def canonical_digest(records_path: Path) -> str:
    """sha256 (first 16 hex) of ``records.jsonl`` with ``wall_time_s`` removed."""
    h = hashlib.sha256()
    for line in records_path.read_text().splitlines():
        d = json.loads(line)
        d.pop("wall_time_s", None)
        h.update((json.dumps(d, sort_keys=True, separators=(",", ":")) + "\n").encode())
    return h.hexdigest()[:16]


def test_every_scripted_catalog_experiment_is_pinned():
    names = {p.stem for p in CATALOG.glob("*.yaml")} - PAID
    assert names == set(GOLDEN), f"pin or drop: {sorted(names ^ set(GOLDEN))}"


@pytest.mark.parametrize("name", sorted(GOLDEN))
def test_catalog_zero_matches_its_golden_hash(name, tmp_path):
    spec = load_spec(CATALOG / f"{name}.yaml")
    out = tmp_path / name
    run_experiment(spec, out_dir=str(out))
    digest = canonical_digest(out / "records.jsonl")
    if os.environ.get("GOLDEN_UPDATE"):
        print(f'    "{name}": "{digest}",')
        return
    assert digest == GOLDEN[name], (
        f"{name}: records.jsonl hash {digest} != pinned {GOLDEN[name]} — generation, scoring, the brief, "
        "the oracle or the record store changed; if intended, re-pin with GOLDEN_UPDATE=1"
    )
