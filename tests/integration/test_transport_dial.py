"""Integration tests for the M28.4 compartment / transport-structure dial.

The transport dial is a single, seed-deterministic parameter on the generator
entry point (``instantiate`` / ``BioSpec.build``) that monotonically scales the
STRUCTURE of a generated world's compartments — the number of container regions
(compartments) and the per-species population branching that carries
inter-compartment structure — so worlds can be dialed from a sparse,
few-compartment layout to a dense, many-compartment one. It is a sibling axis to
the M28.1 network size / complexity dial (which scales SIZE, not structure).

Properties under test:
- Determinism: same (transport_complexity, seed) -> identical topology.
- Monotonicity: larger dial -> >= compartments and >= populations, over seeds.
- Default identity: transport_complexity 1.0 / "simple" / None reproduces
  existing generation byte-identically.
- Named levels + spec-level default + input validation (raises, no clamp).
"""

from __future__ import annotations

import pytest

from alienbio.build import TRANSPORT_LEVELS, TemplateRegistry, instantiate, parse_template


# A compact spec that exercises BOTH structure levers the dial scales:
#   - regions.count                    -> compartment count
#   - populations.per_species_per_region -> per-compartment population branching
def _make_spec(transport_complexity=None):
    spec = {
        "_instantiate_": {
            "_as_ Krel": {"_template_": "species"},
            "_as_ Zorb": {"_template_": "species"},
        },
        "parameters": {
            "containers": {
                "regions": {
                    "count": 3,
                    "initial_substrates": {"nutrient": 100.0},
                },
                "populations": {
                    "per_species_per_region": 4,
                },
            }
        },
    }
    if transport_complexity is not None:
        spec["transport_complexity"] = transport_complexity
    return spec


def _build_registry():
    registry = TemplateRegistry()
    registry.register("species", parse_template({"molecules": {"M1": {}}}))
    return registry


def _build(seed=0, transport_complexity=None, spec=None):
    registry = _build_registry()
    spec = spec if spec is not None else _make_spec()
    return instantiate(
        spec, seed=seed, registry=registry, transport_complexity=transport_complexity
    )


def _n_regions(scenario) -> int:
    return len(scenario.regions)


def _n_organisms(scenario) -> int:
    return sum(len(r.organisms) for r in scenario.regions)


class TestTransportDeterminism:
    """Same (transport_complexity, seed) -> identical topology."""

    @pytest.mark.parametrize("value", [0.5, 1.0, 2.0, "branched"])
    def test_same_value_seed_identical(self, value):
        s1 = _build(seed=7, transport_complexity=value)
        s2 = _build(seed=7, transport_complexity=value)
        assert s1.regions == s2.regions


class TestTransportDefaultIdentity:
    """transport_complexity == 1.0 (and None / "simple") is byte-identical."""

    def test_none_equals_one_byte_identical(self):
        s_none = _build(seed=3, transport_complexity=None)
        s_one = _build(seed=3, transport_complexity=1.0)
        # Full generated world (not just container topology) is byte-identical.
        assert s_none.regions == s_one.regions
        assert s_none._ground_truth_ == s_one._ground_truth_
        assert s_none.molecules == s_one.molecules
        assert s_none.reactions == s_one.reactions

    def test_simple_named_equals_one(self):
        s_simple = _build(seed=3, transport_complexity="simple")
        s_one = _build(seed=3, transport_complexity=1.0)
        assert s_simple.regions == s_one.regions

    def test_default_build_matches_baseline(self):
        # A None dial reproduces the pre-dial baseline: 3 regions x 2 species x 4.
        s = _build(seed=3)
        assert _n_regions(s) == 3
        assert _n_organisms(s) == 3 * 2 * 4


class TestTransportMonotonicity:
    """Larger dial -> >= compartments and >= populations, across seeds."""

    def test_compartments_and_populations_monotone(self):
        levels = [0.5, 1.0, 2.0, 4.0]
        for seed in range(6):
            builds = [_build(seed=seed, transport_complexity=c) for c in levels]
            n_regions = [_n_regions(b) for b in builds]
            n_orgs = [_n_organisms(b) for b in builds]
            for i in range(len(levels) - 1):
                assert n_regions[i] <= n_regions[i + 1], (
                    f"compartments not monotone at seed={seed}: {n_regions}"
                )
                assert n_orgs[i] <= n_orgs[i + 1], (
                    f"populations not monotone at seed={seed}: {n_orgs}"
                )

    def test_dense_strictly_bigger_than_sparse(self):
        sparse = _build(seed=1, transport_complexity=0.5)
        dense = _build(seed=1, transport_complexity=4.0)
        assert _n_regions(dense) > _n_regions(sparse)
        assert _n_organisms(dense) > _n_organisms(sparse)


class TestTransportNamedLevels:
    """Named ordinal levels resolve to their numeric multipliers."""

    def test_levels_ordered(self):
        assert TRANSPORT_LEVELS["sparse"] < TRANSPORT_LEVELS["simple"]
        assert TRANSPORT_LEVELS["simple"] < TRANSPORT_LEVELS["branched"]
        assert TRANSPORT_LEVELS["branched"] < TRANSPORT_LEVELS["dense"]

    def test_named_matches_numeric(self):
        s_named = _build(seed=5, transport_complexity="branched")
        s_numeric = _build(seed=5, transport_complexity=TRANSPORT_LEVELS["branched"])
        assert s_named.regions == s_numeric.regions

    def test_spec_level_default_honored(self):
        spec = _make_spec(transport_complexity="branched")
        s_spec_default = _build(seed=5, transport_complexity=None, spec=spec)
        s_explicit = _build(seed=5, transport_complexity="branched")
        assert s_spec_default.regions == s_explicit.regions


class TestTransportValidation:
    """Invalid dial inputs fail loudly (no silent clamp/fallback)."""

    def test_unknown_named_level_raises(self):
        with pytest.raises(ValueError):
            _build(seed=0, transport_complexity="ginormous")

    def test_negative_raises(self):
        with pytest.raises(ValueError):
            _build(seed=0, transport_complexity=-1.0)


class TestTransportViaBioBuild:
    """The dial is reachable through the Bio.build entry point too."""

    def test_bio_build_threads_transport_complexity(self):
        from alienbio import bio

        registry = _build_registry()
        spec = _make_spec()
        s_sparse = bio.build(
            spec, seed=2, registry=registry, transport_complexity="sparse"
        )
        s_dense = bio.build(
            spec, seed=2, registry=registry, transport_complexity="dense"
        )
        assert _n_regions(s_dense) > _n_regions(s_sparse)
