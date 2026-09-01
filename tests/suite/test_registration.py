"""T030 — registration-gated awareness-dial admission (AUP's phase-2
unlock): registry parsing, mismatch refusals, scope-exact admission, and the
license stamp on records + manifest."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import alienbio.suite.experiment as experiment_mod
from alienbio.suite.experiment import (
    no_peeking_violation,
    registration_admission,
    run_experiment,
    spec_from_dict,
)
from alienbio.suite.registration import REGISTRY_RELPATH, load_registry, resolve_registration

GOOD_ENTRY = """
aup-phase2:
  osf: "osf.io/abc12"
  filed: "2026-09-15"
  dials: [monitoring, framing]
  drafters: [phase1_pressure, pressure]
"""


def _registry(tmp_path: Path, text: str = GOOD_ENTRY) -> Path:
    path = tmp_path / "registrations.yaml"
    path.write_text(text)
    return path


def _spec(agent="llm", drafter="phase1_pressure", registration="aup-phase2", fixed=None, axes=None, dk=None):
    return spec_from_dict(
        {
            "name": "t",
            "axes": axes or {},
            "drafter": drafter,
            "agent": agent,
            "trials_per_condition": 1,
            "base_seed": 1,
            "fixed_dials": {"levers": ["root/uptake_route_in", "root/uptake_neutral_in"], **(fixed or {})},
            "drafter_kwargs": dk or {"variant": "coupling_told"},
            "registration": registration,
        }
    )


def test_registry_entry_shape(tmp_path):
    reg = resolve_registration("aup-phase2", _registry(tmp_path))
    assert reg.osf == "osf.io/abc12"
    assert reg.filed == "2026-09-15"
    assert reg.dials == frozenset({"monitoring", "framing"})
    assert reg.drafters == frozenset({"phase1_pressure", "pressure"})
    assert reg.to_dict()["dials"] == ["framing", "monitoring"]


def test_registry_refuses_malformed_entries(tmp_path):
    cases = {
        "extra key": GOOD_ENTRY.replace('drafters: [phase1_pressure, pressure]', 'drafters: [pressure]\n  note: hi'),
        "bad date": GOOD_ENTRY.replace('"2026-09-15"', '"Sept 15"'),
        "empty dials": GOOD_ENTRY.replace("[monitoring, framing]", "[]"),
        "missing osf": GOOD_ENTRY.replace('  osf: "osf.io/abc12"\n', ""),
    }
    for label, text in cases.items():
        with pytest.raises(ValueError):
            load_registry(_registry(tmp_path, text))


def test_missing_registry_and_unknown_id_refuse_visibly(tmp_path):
    with pytest.raises(ValueError, match="does not exist"):
        resolve_registration("aup-phase2", tmp_path / "nope.yaml")
    with pytest.raises(ValueError, match="not in the registry"):
        resolve_registration("other-id", _registry(tmp_path))


def test_admission_is_none_without_a_claim():
    assert registration_admission(_spec(registration=None)) is None


def test_admission_refuses_a_drafter_outside_the_entry(tmp_path):
    with pytest.raises(ValueError, match="does not cover drafter"):
        registration_admission(_spec(drafter="conflict", dk={"rung": "single"}), _registry(tmp_path))


def test_admission_refuses_an_entry_naming_an_unknown_drafter(tmp_path):
    text = GOOD_ENTRY.replace("[phase1_pressure, pressure]", "[phase1_pressure, presure]")
    with pytest.raises(ValueError, match="unknown drafter"):
        registration_admission(_spec(), _registry(tmp_path, text))


def test_registration_admits_exactly_the_scoped_dials(tmp_path):
    registry = _registry(tmp_path)
    # In scope: monitoring on the registered family — admitted.
    ok = _spec(fixed={"monitoring": "logged"})
    assert no_peeking_violation(ok, registry) is None
    # In scope on the GUARDED drafter the entry names: the drafter-level
    # refusal is lifted, the scope still governs.
    guarded_ok = _spec(drafter="pressure", fixed={"monitoring": "logged"}, dk={"pi": 0.0})
    assert no_peeking_violation(guarded_ok, registry) is None
    # Out of scope: stakes is not in the entry — still refused, naming the license.
    out = _spec(fixed={"monitoring": "logged", "stakes": "high"})
    violation = no_peeking_violation(out, registry)
    assert violation is not None and "aup-phase2" in violation and "stakes" in violation
    # A guarded-drafter dial outside the scope refuses too (pi in play).
    pi_out = _spec(drafter="pressure", dk=None, axes={"pi": [0.0, 0.5]})
    violation2 = no_peeking_violation(pi_out, registry)
    assert violation2 is not None and "pi" in str(violation2)


def test_unregistered_specs_are_unchanged(tmp_path):
    registry = _registry(tmp_path)
    still = _spec(registration=None, drafter="pressure", dk={"pi": 0.5})
    assert no_peeking_violation(still, registry) is not None


def test_scripted_run_with_a_false_claim_is_refused(tmp_path, monkeypatch):
    """A mismatched license claim is a spec error regardless of agent —
    run_experiment refuses before anything is drafted."""
    monkeypatch.setattr(experiment_mod, "REGISTRY_RELPATH", _registry(tmp_path))
    spec = _spec(agent="idle", drafter="conflict", dk={"rung": "single"})
    with pytest.raises(ValueError, match="does not cover drafter"):
        run_experiment(spec, out_dir=str(tmp_path / "out"))


def test_license_is_stamped_on_every_record_line_and_the_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(experiment_mod, "REGISTRY_RELPATH", _registry(tmp_path))
    spec = _spec(agent="idle", fixed={"monitoring": "logged"})
    run_experiment(spec, out_dir=str(tmp_path / "out"))
    lines = [json.loads(l) for l in (tmp_path / "out" / "records.jsonl").read_text().splitlines()]
    assert lines and all(l["registration"] == "aup-phase2" for l in lines)
    manifest = json.loads((tmp_path / "out" / "manifest.json").read_text())
    assert manifest["registration"]["id"] == "aup-phase2"
    assert manifest["registration"]["osf"] == "osf.io/abc12"
    assert manifest["spec"]["registration"] == "aup-phase2"


def test_unregistered_record_lines_carry_no_registration_key(tmp_path):
    """Golden safety: without a claim, the key is absent (not null) — every
    pre-T030 records.jsonl stays byte-identical."""
    spec = _spec(agent="idle", registration=None)
    run_experiment(spec, out_dir=str(tmp_path / "out"))
    lines = [json.loads(l) for l in (tmp_path / "out" / "records.jsonl").read_text().splitlines()]
    assert lines and all("registration" not in l for l in lines)
    manifest = json.loads((tmp_path / "out" / "manifest.json").read_text())
    assert manifest["registration"] is None


def test_shipped_registry_is_a_valid_empty_registry():
    repo_registry = experiment_mod._REPO_ROOT / REGISTRY_RELPATH
    assert repo_registry.exists()
    assert load_registry(repo_registry) == {}
