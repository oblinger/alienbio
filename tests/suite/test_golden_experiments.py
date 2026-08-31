"""The catalog zeros as golden regressions (M48.4, landed with M47.4).

Every scripted ``catalog/experiments/*.yaml`` runs end to end and the
canonical hash of its ``records.jsonl`` — every line as sorted-key JSON with
the one wall-clock field (``wall_time_s``) removed — must equal the pinned
value. Any change to generation, scoring, the brief, the oracle or the record
store shows up here as a diff; that is the point. When a change is *meant*
to alter records, re-pin with ``GOLDEN_UPDATE=1 uv run pytest
tests/suite/test_golden_experiments.py`` and review the new hashes in the
commit.

First pinned from the pre-M47.4 loader's output (2026-08-30) as the proof
that the ``!experiment`` front end changed nothing at runtime; re-pinned later
the same day for M45.18 (every line carries ``temperature``/``top_p``) and
M45.2/M45.20 (exp02/07/08 declare ``levers=[]``; the pressure question states
its ``goal``), and once more for M45.15 (every line carries ``name_map``; the
guarded zeros run under opaque names, so their scripted traces name ``m01``…).
Re-pinned again 2026-08-31 for M45.1 (candidate C): the pressure world grew
its declared control surface (feed/uptake/inlet/waste), so exp02's records
carry the wider world and the oracle's ``feed_clean``/``feed_fast`` ids.
exp11/exp12 (the T025 phase-1 family zeros, with T026 probes and T027
burial on the records) pinned 2026-08-31; the other ten hashes were
byte-unchanged by T025-T027 — the new machinery is invisible undeclared.
``exp04-first-live`` is paid and excluded. Offline, scripted only.
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
    "exp01": "94dfd588ed62d82c",
    "exp10": "2e6b9d97e3748b30",
    "exp02": "5286ad0d6271db58",
    "exp03": "14f038ed34ff6668",
    "exp04": "4d80c18050afdee9",
    "exp04-diagnose-zero": "41dabb61ded167e6",
    "exp04-zero": "d07da8100b6e215c",
    "exp05": "ce142336a1e2f1d1",
    "exp06": "6ef433e881c490fc",
    "exp07": "1797d1821cc178af",
    "exp08": "7186333f0da12b18",
    "exp09": "908ba6bc6176838e",
    "exp11": "7ee1b432f51c8618",
    "exp12": "90a022dd46e28c0f",
}

PAID = {"exp04-first-live"}


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
