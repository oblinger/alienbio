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
Re-pinned 2026-09-08 for T046 (Intervene ``value``/``delta`` on the
action log): only the four zeros whose scripted agents intervene changed
(exp01/09/11/12); the other ten were byte-unchanged (only-when-set).
Re-pinned 2026-09-10 for T055 (AUP's call (A)): phase-1's ``v_target`` is
derived on the episode's own horizon, so the two 8 s phase-1 zeros
(exp11/exp12) carry a reachable goal — ``pursue-target`` scores 1.0 where
it scored 0.86-0.94 — and ``oracle["phase1"]`` carries
``derivation_horizon_s``/``episode_horizon_s``; the other twelve were
byte-unchanged.
exp13 (the T047 W2 zero: depth × fan_out at pi=0.5, pursue-target + idle
twin, the bright-line commitment and in-world stakes on every brief) pinned
2026-09-10; the other fourteen were byte-unchanged by T047 — W2 is a new
head, W1 untouched. Re-pinned 2026-09-15 (AUP leg 3): the harm chain's
hop rate is 1000 (was 10) and the zero runs 0.01 s steps, so the chain's
lag is within the bound the head now enforces and ``oracle["w2"]`` carries
``k_harm_hop``/``sim_dt``/``turn_s``/``chain_lag_s``; the other fifteen
were byte-unchanged.
exp02/exp11/exp12/exp13 re-pinned 2026-09-17 (T062/T063): every
pressure-family record carries ``readout_series`` (the per-turn series of
the drafter's declared readouts — target, tracked pool, and on W2 the whole
harm branch) and W2's custodial reserve leaks into a hidden terminal
``harm_ledger`` pool (``oracle["w2"]`` carries ``harm_read`` /
``harm_branch`` / ``hop_delay_s``); the other twelve were byte-unchanged.
exp06/exp09 re-pinned 2026-10-28: the default control surface no longer
offers the task's readout molecule (``brief.lever_exclusion``), so the
predict and intervene zeros' records list one lever fewer (``m4``, the
target) in ``brief.affordances.levers`` / ``brief.irreversible``; no
action, score or other field moved, and the other thirteen were
byte-unchanged (their surfaces are declared or carry no readout).
exp08 re-pinned 2026-10-28 (T088 Q4 = A): ``source_b``'s sink drains at
1.0 (was 0.05), so on W_match the bigger supply is also the bigger level
at every time; only ``final_state`` moved (``source_b_out`` on all twelve
lines, ``route_drive_out`` on the six W_mismatch lines) — every score,
action and answer is byte-identical, and the other fifteen were
byte-unchanged. exp07 re-pinned the same day: the conflict question on
the two-target rungs names both ``(id, goal)`` pairs (it named V1's
alone); ``brief.question.target`` on all 36 lines is the only field that
moved — the oracle's supply, now read off the drafted world, is
byte-identical.
exp04-diagnose-zero re-pinned 2026-10-28 (T088 drafters 1, the Pilot's
call): ``observability`` and the forgetting dials joined
``WORLD_INVARIANT_DIALS``, so the 0.5 arm now draws its trial seed from
the same label as the 1.0 arm. Only the 12 ``observability=0.5`` lines
moved, and only in the visible-id lists the per-trial hidden draw sets —
``brief.affordances.levers`` / ``.probes`` and ``brief.irreversible`` —
plus ``action_log[0].target`` on three measure-commit lines; every score,
``final_state``, ``oracle`` and ``name_map`` is byte-identical, the 12
``observability=1.0`` lines are unchanged, and the other fifteen hashes
were byte-unchanged.
exp04, exp05 and exp04-diagnose-zero re-pinned 2026-10-28 (T088 archetype
drafters 1): a ``diagnose`` world without ``perturbation`` now runs the
chosen node's feeding reaction at ``DEFAULT_PERTURBATION`` = 3.0x, so the
answer is in the dynamics and each seed drafts its own world (it was one
world for every seed, the answer a label). Only ``final_state`` (the chain
pools, and ``hz`` on the hazard zeros), ``oracle.hazard.final_value`` and the
new ``oracle.perturbation`` block moved; every score, action and answer is
byte-identical (the scripted zeros commit no answer). exp09 re-pinned the
same day (T088 generative 1, the T055 shape): the intervene goal and the
oracle's ``passive`` are read on the episode's own 12 s horizon (they were
read at 20 s), the two horizons ride ``oracle.intervene``, and a goal above
the 100 units the chain holds refuses at draft — so exp09's
``target_margin`` is 0.03 (0.2 above the 12 s reach exceeds 100 on one
seed). ``oracle.intervene.goal`` / ``.passive``, ``objective_score`` and the
two horizon fields moved on all 24 lines; the other eleven were
byte-unchanged.
exp03, exp04, exp05 and exp04-diagnose-zero re-pinned 2026-10-29 (T091
A2): a ``diagnose`` target is drawn from ``m1 … m{n-1}`` (``m0`` drafted
the same world as ``m1``). Only ``oracle.perturbation.node`` (24 + 24 + 18
+ 12 lines), ``oracle.perturbation.reaction`` and the chain pools of
``final_state`` (on the lines whose perturbed reaction changed; none on
exp03, whose 24 moved lines went ``m0`` -> ``m1`` on the same ``r0``)
moved; every score, action and answer is byte-identical (the scripted zeros commit no answer). exp09
re-pinned the same day (T091 A1): the intervene outcome is scored at the
12 s horizon after the commit (the remaining turns run passively), so
``objective_score`` and the new ``oracle.intervene.scored_at_s`` and
``runout`` moved on all 24 lines (act-commit 0.0131 -> 0.2326,
survey-commit 0.0216 -> 0.2930); ``final_state`` and the action logs are
byte-identical, and the other eleven were byte-unchanged.
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
    "exp01": "df73d1293dfe65f8",
    "exp10": "2e6b9d97e3748b30",
    "exp02": "a23400c0bb583d18",
    "exp03": "b7fa0de50ec24de2",
    "exp04": "5b05aa164a6d8b8a",
    "exp04-diagnose-zero": "eba0349455c4ab1b",
    "exp04-zero": "d07da8100b6e215c",
    "exp05": "3f37ce5caad5299a",
    "exp06": "ffa26959c383e674",
    "exp07": "fcba846f9a5bf0ab",
    "exp08": "d63c1077400826a2",
    "exp09": "be85ae8eb101318e",
    "exp11": "5133aeda0c2af22c",
    "exp12": "1264a5892e887d4c",
    "exp13": "dffcdd961510011f",
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
