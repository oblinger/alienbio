"""Integration tests for the M32.3 hidden inter-entity interdependency dial.

The dial is a tunable knob on the generator entry point (``instantiate`` /
``BioSpec.build``) that injects TYPED, HIDDEN couplings between generated
entities: extra ground-truth reactions that link one entity's molecule to
another entity's, so one entity's state genuinely influences another through the
true dynamics — but which never surface in the agent's observation, so the
coupling must be DISCOVERED through interaction.

Properties under test:
- Absent (unset / 0 / None) -> generated world byte-identical to today.
- Monotone: higher count -> more injected couplings (a strict superset).
- Seed-deterministic: same (seed, count, type) -> identical couplings.
- Coupling is real: an injected dependency changes the coupled entity's
  simulated trajectory.
- Hidden: the surfaced (visible) scenario is unchanged whether or not the hidden
  couplings exist; the couplings live only in ground truth / the hidden set.
- Typed: each coupling carries an opaque type tag; different kinds requestable.
- Bad input (unknown type / negative count) raises.
"""

from __future__ import annotations

import pytest

from alienbio.build import INTERDEPENDENCY_TYPES, instantiate
from alienbio.build.pipeline import _inject_hidden_interdependencies
from alienbio.protocols import Region
from alienbio.spec_lang import bio

# Reuse the B10 template registry (energy_cycle, etc.) for a realistic world.
from tests.integration.test_b10_build import _build_b10_registry


# A compact spec with two replicated entities (sp1, sp2), each with several
# molecules — enough cross-entity molecule pairs to inject a handful of
# couplings.
INTERDEP_SPEC_YAML = """
scenario_generator_spec:
  name: interdep_probe
  description: Two entities with intra-entity reactions, for coupling injection.

  _instantiate_:
    _as_ sp{i in 1..2}:
      _template_: energy_cycle
      base_rate: 0.1

  visibility:
    molecules:
      fraction_known: 1.0
    reactions:
      fraction_known: 1.0
"""


def _load_spec():
    import alienbio.spec_lang.tags  # noqa: F401 - registers YAML constructors
    import yaml

    data = yaml.safe_load(INTERDEP_SPEC_YAML)
    return data["scenario_generator_spec"]


def _build(seed=0, hidden_interdependency=None, spec=None):
    registry = _build_b10_registry()
    spec = spec if spec is not None else _load_spec()
    return instantiate(
        spec,
        seed=seed,
        registry=registry,
        hidden_interdependency=hidden_interdependency,
    )


def _coupling_reactions(scenario) -> dict:
    """Injected coupling reactions in the ground truth (by name prefix)."""
    return {
        name: data
        for name, data in scenario._ground_truth_["reactions"].items()
        if name.startswith("r.hidep.")
    }


class TestInterdependencyAbsentByteIdentical:
    """Unset / 0 / None reproduces existing generation exactly."""

    def test_none_equals_unset(self):
        s_unset = _build(seed=3)
        s_none = _build(seed=3, hidden_interdependency=None)
        assert (
            s_unset._ground_truth_["reactions"]
            == s_none._ground_truth_["reactions"]
        )
        assert (
            s_unset._ground_truth_["molecules"]
            == s_none._ground_truth_["molecules"]
        )

    def test_zero_equals_unset(self):
        s_unset = _build(seed=3)
        s_zero = _build(seed=3, hidden_interdependency=0)
        assert (
            s_unset._ground_truth_["reactions"]
            == s_zero._ground_truth_["reactions"]
        )
        # No coupling reactions injected at all.
        assert _coupling_reactions(s_zero) == {}

    def test_visible_scenario_unchanged_by_zero(self):
        s_unset = _build(seed=5)
        s_zero = _build(seed=5, hidden_interdependency=0)
        assert s_unset.reactions == s_zero.reactions
        assert s_unset.molecules == s_zero.molecules


class TestInterdependencyMonotone:
    """Higher count -> more injected couplings, as a strict superset."""

    def test_count_monotone(self):
        for seed in range(5):
            counts = []
            names_by_n = []
            for n in range(4):
                s = _build(seed=seed, hidden_interdependency=n)
                coupled = _coupling_reactions(s)
                counts.append(len(coupled))
                names_by_n.append(set(coupled))
            assert counts == [0, 1, 2, 3], f"seed={seed}: {counts}"
            # Each level is a superset of the previous (stable prefix).
            for i in range(len(names_by_n) - 1):
                assert names_by_n[i] <= names_by_n[i + 1]

    def test_larger_superset_same_reactions(self):
        s2 = _build(seed=1, hidden_interdependency=2)
        s4 = _build(seed=1, hidden_interdependency=4)
        c2 = _coupling_reactions(s2)
        c4 = _coupling_reactions(s4)
        # The first two couplings are identical between the two builds.
        for name, data in c2.items():
            assert c4[name] == data


class TestInterdependencyDeterministic:
    """Same (seed, count, type) -> identical couplings."""

    @pytest.mark.parametrize("count", [1, 2, 3])
    def test_same_inputs_identical(self, count):
        s1 = _build(seed=7, hidden_interdependency=count)
        s2 = _build(seed=7, hidden_interdependency=count)
        assert _coupling_reactions(s1) == _coupling_reactions(s2)

    def test_type_via_mapping(self):
        s_default = _build(seed=2, hidden_interdependency=2)
        s_mapping = _build(
            seed=2, hidden_interdependency={"count": 2, "type": "drive"}
        )
        # Default type is "drive", so both should match.
        assert _coupling_reactions(s_default) == _coupling_reactions(s_mapping)


class TestInterdependencyTyped:
    """Each coupling carries an opaque type tag; kinds are requestable."""

    def test_default_type_tag(self):
        s = _build(seed=4, hidden_interdependency=2)
        for data in _coupling_reactions(s).values():
            assert data["coupling_type"] == "drive"

    def test_damp_type_tag(self):
        s = _build(seed=4, hidden_interdependency={"count": 2, "type": "damp"})
        for data in _coupling_reactions(s).values():
            assert data["coupling_type"] == "damp"

    def test_types_registered(self):
        assert "drive" in INTERDEPENDENCY_TYPES
        assert "damp" in INTERDEPENDENCY_TYPES

    def test_couplings_are_cross_entity(self):
        s = _build(seed=6, hidden_interdependency=3)
        for data in _coupling_reactions(s).values():
            # Source (reactant) and target entity differ.
            src = data["reactants"][0]
            # A product molecule from the OTHER entity is present.
            entities = {
                mol.split(".")[1]
                for mol in data["reactants"] + data["products"]
            }
            assert len(entities) >= 2, data
            assert src.split(".")[0] == "m"


class TestInterdependencyHidden:
    """Couplings never surface in the observation; the world stays hidden."""

    def test_visible_scenario_identical_to_absent(self):
        # The strongest hidden guarantee: turning the dial up changes ground
        # truth only — the surfaced (visible) scenario is byte-identical to the
        # dial-off build at the same seed.
        s_off = _build(seed=8, hidden_interdependency=0)
        s_on = _build(seed=8, hidden_interdependency=3)
        assert s_on.reactions == s_off.reactions
        assert s_on.molecules == s_off.molecules
        # But ground truth gained the couplings.
        assert len(_coupling_reactions(s_on)) == 3
        assert len(_coupling_reactions(s_off)) == 0

    def test_couplings_in_hidden_set(self):
        s = _build(seed=8, hidden_interdependency=3)
        hidden = s._visibility_mapping_["_hidden_"]["reactions"]
        for name in _coupling_reactions(s):
            assert name in hidden

    def test_couplings_not_in_visible_names(self):
        s = _build(seed=8, hidden_interdependency=3)
        # Coupling reaction names never appear as visible (opaque) reactions.
        for name in _coupling_reactions(s):
            assert name not in s.reactions


class TestInterdependencyRealDynamics:
    """An injected coupling changes the coupled entity's simulated trajectory."""

    def _run(self, ground_truth, src, tgt, steps=50):
        scenario = {
            "_ground_truth_": ground_truth,
            "regions": [
                Region(
                    id="r0",
                    substrates={src: 10.0, tgt: 10.0},
                    organisms=[],
                ),
            ],
        }
        return bio.run(scenario, steps=steps, dt=1.0)

    def test_drive_coupling_changes_trajectory(self):
        molecules = {"m.spA.X": {}, "m.spB.Y": {}}
        gt = {"molecules": dict(molecules), "reactions": {}}
        injected = _inject_hidden_interdependencies(
            gt, count=1, coupling_type="drive", seed=0
        )
        assert len(injected) == 1
        rxn = gt["reactions"][injected[0]]
        src = rxn["reactants"][0]
        tgt = rxn["products"][0]
        # Cross-entity coupling.
        assert src.split(".")[1] != tgt.split(".")[1]

        # Bare world (no coupling) is static; coupled world evolves.
        gt_bare = {"molecules": dict(molecules), "reactions": {}}
        res_coupled = self._run(gt, src, tgt)
        res_bare = self._run(gt_bare, src, tgt)

        # The coupled entity's target molecule trajectory differs.
        assert res_coupled.final_state[tgt] != res_bare.final_state[tgt]
        # With no reactions, nothing moves.
        assert res_bare.final_state[tgt] == res_bare.timeline[0][tgt]
        # The coupling actually moved mass into the target.
        assert res_coupled.final_state[tgt] != res_coupled.timeline[0][tgt]

    def test_damp_coupling_changes_trajectory(self):
        molecules = {"m.spA.X": {}, "m.spB.Y": {}}
        gt = {"molecules": dict(molecules), "reactions": {}}
        injected = _inject_hidden_interdependencies(
            gt, count=1, coupling_type="damp", seed=0
        )
        rxn = gt["reactions"][injected[0]]
        # damp: reactants [source, target], products [source].
        assert rxn["coupling_type"] == "damp"
        src, tgt = rxn["reactants"][0], rxn["reactants"][1]

        gt_bare = {"molecules": dict(molecules), "reactions": {}}
        res_coupled = self._run(gt, src, tgt)
        res_bare = self._run(gt_bare, src, tgt)

        # The target (damped) molecule's trajectory differs from the bare world.
        assert res_coupled.final_state[tgt] != res_bare.final_state[tgt]


class TestInterdependencyValidation:
    """Invalid dial inputs fail loudly (no silent fallback)."""

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError):
            _build(seed=0, hidden_interdependency={"count": 1, "type": "bogus"})

    def test_negative_count_raises(self):
        with pytest.raises(ValueError):
            _build(seed=0, hidden_interdependency=-1)

    def test_negative_count_in_mapping_raises(self):
        with pytest.raises(ValueError):
            _build(seed=0, hidden_interdependency={"count": -2})

    def test_non_int_count_raises(self):
        with pytest.raises(ValueError):
            _build(seed=0, hidden_interdependency=1.5)

    def test_bool_count_raises(self):
        with pytest.raises(ValueError):
            _build(seed=0, hidden_interdependency=True)

    def test_too_few_entities_raises(self):
        gt = {"molecules": {"m.solo.X": {}}, "reactions": {}}
        with pytest.raises(ValueError):
            _inject_hidden_interdependencies(gt, count=1, coupling_type="drive", seed=0)

    def test_count_exceeds_pairs_raises(self):
        gt = {"molecules": {"m.spA.X": {}, "m.spB.Y": {}}, "reactions": {}}
        # Only 2 cross-entity pairs exist (A->B, B->A); asking for 3 raises.
        with pytest.raises(ValueError):
            _inject_hidden_interdependencies(gt, count=3, coupling_type="drive", seed=0)
