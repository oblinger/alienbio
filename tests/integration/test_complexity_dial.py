"""Integration tests for the M28.1 network size / complexity dial.

The complexity dial is a single, seed-deterministic parameter on the generator
entry point (``instantiate`` / ``BioSpec.build``) that monotonically scales the
SIZE of a generated world — roughly species x reactions x molecules — so worlds
can be dialed from small -> large for a difficulty curriculum.

Properties under test:
- Determinism: same (complexity, seed) -> identical world.
- Monotonicity: larger complexity -> >= species and >= reactions, over seeds.
- Default identity: complexity 1.0 / None reproduces existing generation.
- Named levels + spec-level default + input validation.
"""

from __future__ import annotations

import pytest

from alienbio.build import COMPLEXITY_LEVELS, instantiate

# Reuse the B10 template registry (energy_cycle, etc.) for a realistic world.
from tests.integration.test_b10_build import _build_b10_registry


# A compact spec that exercises BOTH size levers the dial scales:
#   - species replication (`_as_ sp{i in 1..2}`) -> species count
#   - background filler (molecules + reactions)  -> molecule/reaction count
COMPLEXITY_SPEC_YAML = """
scenario_generator_spec:
  name: complexity_probe
  description: Replicated species plus background filler, for dial scaling.

  _instantiate_:
    _as_ sp{i in 1..2}:
      _template_: energy_cycle
      base_rate: 0.1

  background:
    molecules:
      count: !ev normal(6, 2)
    reactions:
      count: !ev normal(6, 2)

  visibility:
    molecules:
      fraction_known: 1.0
    reactions:
      fraction_known: 1.0
"""


def _load_spec():
    import alienbio.spec_lang.tags  # noqa: F401 - registers YAML constructors
    import yaml

    data = yaml.safe_load(COMPLEXITY_SPEC_YAML)
    return data["scenario_generator_spec"]


def _build(seed=0, complexity=None, spec=None):
    registry = _build_b10_registry()
    spec = spec if spec is not None else _load_spec()
    return instantiate(spec, seed=seed, registry=registry, complexity=complexity)


def _species(scenario) -> set[str]:
    """Distinct (non-background) species namespaces in the ground truth."""
    species = set()
    for mol_name in scenario._ground_truth_["molecules"]:
        parts = mol_name.split(".")
        if len(parts) >= 2 and parts[0] == "m" and parts[1] != "bg":
            species.add(parts[1])
    return species


def _n_reactions(scenario) -> int:
    return len(scenario._ground_truth_["reactions"])


def _n_molecules(scenario) -> int:
    return len(scenario._ground_truth_["molecules"])


class TestComplexityDeterminism:
    """Same (complexity, seed) -> byte-identical world."""

    @pytest.mark.parametrize("complexity", [0.5, 1.0, 2.0, "large"])
    def test_same_complexity_seed_identical(self, complexity):
        s1 = _build(seed=7, complexity=complexity)
        s2 = _build(seed=7, complexity=complexity)
        assert s1._ground_truth_["molecules"] == s2._ground_truth_["molecules"]
        assert s1._ground_truth_["reactions"] == s2._ground_truth_["reactions"]


class TestComplexityDefaultIdentity:
    """complexity == 1.0 (and None) leaves existing generation unchanged."""

    def test_none_equals_one(self):
        s_none = _build(seed=3, complexity=None)
        s_one = _build(seed=3, complexity=1.0)
        assert s_none._ground_truth_["molecules"] == s_one._ground_truth_["molecules"]
        assert s_none._ground_truth_["reactions"] == s_one._ground_truth_["reactions"]

    def test_medium_named_equals_one(self):
        s_medium = _build(seed=3, complexity="medium")
        s_one = _build(seed=3, complexity=1.0)
        assert s_medium._ground_truth_["reactions"] == s_one._ground_truth_["reactions"]

    def test_default_build_nonempty(self):
        s = _build(seed=3)
        assert _n_molecules(s) > 0
        assert _n_reactions(s) > 0
        # The replicated species (sp1, sp2) are present at default complexity.
        assert _species(s) == {"sp1", "sp2"}


class TestComplexityMonotonicity:
    """Larger complexity -> >= species and >= reactions, across seeds."""

    def test_species_and_reactions_monotone(self):
        levels = [0.5, 1.0, 2.0, 4.0]
        for seed in range(6):
            builds = [_build(seed=seed, complexity=c) for c in levels]
            n_species = [len(_species(b)) for b in builds]
            n_reactions = [_n_reactions(b) for b in builds]
            n_molecules = [_n_molecules(b) for b in builds]
            for i in range(len(levels) - 1):
                assert n_species[i] <= n_species[i + 1], (
                    f"species not monotone at seed={seed}: {n_species}"
                )
                assert n_reactions[i] <= n_reactions[i + 1], (
                    f"reactions not monotone at seed={seed}: {n_reactions}"
                )
                assert n_molecules[i] <= n_molecules[i + 1], (
                    f"molecules not monotone at seed={seed}: {n_molecules}"
                )

    def test_large_strictly_bigger_on_average(self):
        # Averaged over seeds, large should produce strictly more than small.
        small = [_build(seed=s, complexity=0.5) for s in range(6)]
        large = [_build(seed=s, complexity=4.0) for s in range(6)]
        avg_small = sum(_n_reactions(b) for b in small) / len(small)
        avg_large = sum(_n_reactions(b) for b in large) / len(large)
        assert avg_large > avg_small


class TestComplexityNamedLevels:
    """Named ordinal levels resolve to their numeric multipliers."""

    def test_levels_defined(self):
        assert COMPLEXITY_LEVELS["small"] < COMPLEXITY_LEVELS["medium"]
        assert COMPLEXITY_LEVELS["medium"] < COMPLEXITY_LEVELS["large"]
        assert COMPLEXITY_LEVELS["large"] < COMPLEXITY_LEVELS["huge"]

    def test_named_matches_numeric(self):
        s_named = _build(seed=5, complexity="large")
        s_numeric = _build(seed=5, complexity=COMPLEXITY_LEVELS["large"])
        assert s_named._ground_truth_["reactions"] == s_numeric._ground_truth_["reactions"]

    def test_spec_level_default_honored(self):
        spec = _load_spec()
        spec["complexity"] = "large"
        s_spec_default = _build(seed=5, complexity=None, spec=spec)
        s_explicit = _build(seed=5, complexity="large")
        assert (
            s_spec_default._ground_truth_["reactions"]
            == s_explicit._ground_truth_["reactions"]
        )


class TestComplexityValidation:
    """Invalid dial inputs fail loudly."""

    def test_unknown_named_level_raises(self):
        with pytest.raises(ValueError):
            _build(seed=0, complexity="ginormous")

    def test_negative_raises(self):
        with pytest.raises(ValueError):
            _build(seed=0, complexity=-1.0)
