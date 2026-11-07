"""T091 BF (verifier BD1) — a resume notices a moved world chemistry.

The record re-draft (``guards.recorded_worlds_violation``) compares what a
record holds about its world — task id, oracle, question, affordances — and
none of those covers the chemistry, the compartments, the flows or the
population laws. A yaml edit that moved only the world (a ``compartments:``
scope added, ``drain_rate`` changed on a document-level ``!Chemistry``)
resumed silently and two worlds shared one store. The manifest now carries
``world_fingerprints`` (``{label: guards.world_fingerprint}`` of each
condition's first-trial world, from the preflight ``draft`` check) and a
resume refuses a world that moved; a manifest from before the field gains
the stamps, never a refusal. Record lines are untouched.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, cast

import pytest

from alienbio.bio.chemistry import ChemistryImpl
from alienbio.bio.molecule import MoleculeImpl
from alienbio.bio.world import Compartment, WorldImpl
from alienbio.expr.yaml_tags import read_spec_text
from alienbio.infra.mk import mk
from alienbio.suite.drafters import DRAFTERS
from alienbio.suite.experiment import run_experiment
from alienbio.suite.expr_experiment import load_experiment
from alienbio.suite.guards import preflight, world_fingerprint
from alienbio.suite.spec import with_source
from alienbio.suite.store import read_manifest

REPO = Path(__file__).resolve().parents[2]
MICROCOSM = REPO / "catalog" / "examples" / "microcosm"
SCOPED = (MICROCOSM / "microcosm.yaml").read_text()


def _load(yml: Path):
    spec = load_experiment(yml.resolve(), text=read_spec_text(yml.resolve()), trusted=True)
    return with_source(spec, {"spec_path": str(yml.resolve()), "helper_modules": [str(yml.parent / "helpers.py")]})


@pytest.fixture
def microcosm(tmp_path):
    """A copy of the Microcosm example; returns (yaml path, run dir).

    ``DRAFTERS`` keeps the adapter of the first ``microcosm`` head it
    resolved — in a full test session, another test's copy, reading the yaml
    beside THAT helpers file. The cached entry is dropped for this test (and
    restored after), so the head this copy's helpers register is the one
    the run drafts with; on teardown the entry this test cached is dropped
    again (or the earlier one put back), so no later test drafts from this
    test's deleted directory."""
    before = dict.get(DRAFTERS, "microcosm")
    DRAFTERS.pop("microcosm", None)
    d = tmp_path / "mc"
    d.mkdir()
    shutil.copy(MICROCOSM / "helpers.py", d / "helpers.py")
    yield d / "microcosm.yaml", d / "run"
    DRAFTERS.pop("microcosm", None)
    if before is not None:
        DRAFTERS["microcosm"] = before


def _crashed_run(yml: Path, out: Path, text: str) -> None:
    """Run ``text`` to completion, then cut the store to two trials (a crash)."""
    yml.write_text(text)
    run_experiment(_load(yml), out_dir=str(out))
    lines = (out / "records.jsonl").read_text().splitlines()
    (out / "records.jsonl").write_text("\n".join(lines[:2]) + "\n")


def _resume(yml: Path, out: Path) -> list[str]:
    notes: list[str] = []
    run_experiment(_load(yml), out_dir=str(out), resume=True, notes=notes.append)
    return notes


@pytest.mark.parametrize(
    ("before", "after"),
    [
        # BD probe_resume_scope_drift: the unscoped world, then the scope added.
        (SCOPED.replace(", compartments: [pond]", ""), SCOPED),
        # BD probe_resume_rate_drift: drain_rate moved on the document's !Chemistry.
        (SCOPED, SCOPED.replace("drain_rate: 0.02", "drain_rate: 0.08")),
    ],
    ids=["scope-added", "rate-moved"],
)
def test_a_resume_refuses_a_world_the_yaml_moved(microcosm, before, after):
    yml, out = microcosm
    _crashed_run(yml, out, before)
    kept = (out / "records.jsonl").read_text()
    yml.write_text(after)
    with pytest.raises(ValueError, match=r"world chemistry/compartments of condition\(s\) \['feed_rate=0.3'"):
        _resume(yml, out)
    assert (out / "records.jsonl").read_text() == kept
    # The --dry preview names the same refusal.
    flight = preflight(_load(yml), out_dir=str(out), resume=True)
    assert "world_fingerprints" in str(flight.refusal)


def test_a_clean_resume_of_a_stamped_store_passes_without_a_note(microcosm):
    yml, out = microcosm
    _crashed_run(yml, out, SCOPED)
    stamped = read_manifest(out / "manifest.json")["world_fingerprints"]
    assert sorted(stamped) == ["feed_rate=0.3", "feed_rate=0.9"]
    notes = _resume(yml, out)
    assert not any("world_fingerprints" in n for n in notes)
    assert read_manifest(out / "manifest.json")["world_fingerprints"] == stamped
    assert len((out / "records.jsonl").read_text().splitlines()) == 4


def test_an_old_manifest_gains_the_stamps_with_a_note(microcosm):
    yml, out = microcosm
    _crashed_run(yml, out, SCOPED)
    path = out / "manifest.json"
    manifest = json.loads(path.read_text())
    stamped = manifest.pop("world_fingerprints")
    path.write_text(json.dumps(manifest))
    notes = _resume(yml, out)
    assert any("had no world_fingerprints; stamping 2 condition(s)" in n for n in notes)
    assert read_manifest(path)["world_fingerprints"] == stamped
    # The second press is the stamped case: no note.
    assert not any("world_fingerprints" in n for n in _resume(yml, out))


def _scoped_world(order: tuple[str, ...]) -> WorldImpl:
    food = cast(MoleculeImpl, mk.M("food"))
    supply = mk.R("supply", {}, {food: 1.0}, rate=0.5, compartments=list(order))
    chem = cast(ChemistryImpl, mk.C("chem", [food], [supply]))
    comps = (
        Compartment("pond", None, "environment", 10.0, concentrations={"food": 1.0}),
        Compartment("fish", "pond", "population", 0.2, multiplicity=3.0),
    )
    return WorldImpl(chem, comps)


def test_the_fingerprint_is_stable_and_reads_the_scope_as_a_list():
    dials = {"pi": 0.5, "levers": []}
    world, _task = DRAFTERS["pressure"](7, dials)
    first = world_fingerprint(world)
    assert world_fingerprint(world) == first and len(first) == 64
    again, _ = DRAFTERS["pressure"](7, dials)
    assert world_fingerprint(again) == first
    # The scope is a list: its order is content, so two orders differ (a set,
    # which has none, is refused at the reaction — BD2).
    a: Any = world_fingerprint(_scoped_world(("pond", "fish")))
    b: Any = world_fingerprint(_scoped_world(("fish", "pond")))
    assert a != b
    assert world_fingerprint(_scoped_world(("pond", "fish"))) == a
