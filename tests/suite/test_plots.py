"""suite.plots — the one key figure per experiment run: the readout is chosen
from what the records carry in report order (or declared by ``key_readout``),
drawn from the aggregated summaries, written as key.png + key.json beside
report.txt, and reloadable from the record store alone."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from alienbio.suite.experiment import aggregate, load_spec, run_experiment, spec_from_dict, spec_to_dict
from alienbio.suite.plots import PLOTTERS, key_figure, write_key_figure

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "catalog" / "experiments"

#: Every scripted catalog experiment and the readout its key figure must draw.
EXPECTED = {
    "exp01": "caution",
    "exp02": "dose",
    "exp03": "monitoring",
    "exp04": "hazard",
    "exp04-diagnose-zero": "cells",
    "exp04-zero": "cells",
    "exp05": "consideration",
    "exp06": "blindspot",
    "exp07": "conflict",
    "exp08": "delta",
    "exp09": "caution",
    "exp10": "degradation",
    "exp11": "cells",
    "exp12": "cells",
}


@pytest.fixture(scope="module")
def zero(tmp_path_factory):
    """exp04-zero run once: the cheapest end-to-end run with a record store."""
    out = tmp_path_factory.mktemp("zero") / "run"
    spec = load_spec(CATALOG / "exp04-zero.yaml")
    return spec, out, run_experiment(spec, out_dir=str(out))


def test_the_run_writes_the_key_figure_beside_the_report(zero):
    _, out, _ = zero
    assert (out / "key.png").exists() and (out / "report.txt").exists()
    meta = json.loads((out / "key.json").read_text())
    assert meta["readout"] == "cells" and meta["caption"]
    assert (out / "key.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_the_figure_reads_the_same_from_the_reloaded_store(zero, tmp_path):
    _, out, rmap = zero
    reloaded = aggregate(out)
    assert len(reloaded.records) == len(rmap.records) == 4  # aggregate carries the records (it dropped them before)
    assert key_figure(reloaded).readout == key_figure(rmap).readout == "cells"  # type: ignore[union-attr]
    assert write_key_figure(reloaded, tmp_path) == tmp_path / "key.png"


def test_a_declared_readout_wins_and_an_undrawable_one_is_refused(zero):
    _, _, rmap = zero
    assert key_figure(rmap, "cells").readout == "cells"  # type: ignore[union-attr]
    with pytest.raises(ValueError, match="carry nothing"):
        key_figure(rmap, "dose")
    with pytest.raises(ValueError, match="unknown readout"):
        key_figure(rmap, "pie")


def test_key_readout_is_a_validated_spec_key_that_round_trips():
    spec = load_spec(CATALOG / "exp04.yaml")
    assert spec.key_readout == "hazard"
    assert spec_from_dict(spec_to_dict(spec)).key_readout == "hazard"
    with pytest.raises(ValueError, match="key_readout"):
        spec_from_dict({**spec_to_dict(spec), "key_readout": "pie"})
    assert load_spec(CATALOG / "exp02.yaml").key_readout is None


def test_every_catalog_experiment_names_a_readout_the_plotters_know():
    names = {name for name, _ in PLOTTERS}
    assert set(EXPECTED.values()) <= names
    assert {p.stem for p in CATALOG.glob("*.yaml")} - {"exp04-first-live"} == set(EXPECTED)


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_each_catalog_zero_draws_its_own_readout(name, tmp_path):
    spec = load_spec(CATALOG / f"{name}.yaml")
    rmap = run_experiment(spec, out_dir=str(tmp_path / name))
    assert json.loads((tmp_path / name / "key.json").read_text())["readout"] == EXPECTED[name]
    assert key_figure(rmap, spec.key_readout).readout == EXPECTED[name]  # type: ignore[union-attr]
