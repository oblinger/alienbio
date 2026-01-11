"""Tests for Generator Phase G3: Distribution Sampling.

These tests define expected behavior for distribution evaluation during
template expansion. Note: Basic distribution functions (normal, uniform, etc.)
are already tested in test_spec_eval.py. These tests focus on distributions
in the context of generator templates.

Test categories:
- G3.1: Distribution Evaluation (covered by test_spec_eval.py)
- G3.2: Distribution in Templates (params, molecules, loop ranges)
"""

from __future__ import annotations

import pytest
import yaml


# =============================================================================
# G3.1 - Distribution Evaluation (additional generator-specific tests)
# =============================================================================


class TestDistributionEvaluation:
    """Additional distribution tests in generator context."""

    @pytest.mark.skip(reason="Generator context not yet implemented")
    def test_discrete_choice_with_labels(self):
        """discrete() works with labeled choices."""
        from alienbio.build import GeneratorContext, eval_expr

        ctx = GeneratorContext(seed=42)
        result = eval_expr("discrete(['a', 'b', 'c'], [0.5, 0.3, 0.2])", ctx)
        assert result in ["a", "b", "c"]

    @pytest.mark.skip(reason="Generator context not yet implemented")
    def test_choice_uniform(self):
        """choice() picks uniformly from options."""
        from alienbio.build import GeneratorContext, eval_expr

        ctx = GeneratorContext(seed=42)
        result = eval_expr("choice('red', 'green', 'blue')", ctx)
        assert result in ["red", "green", "blue"]

    @pytest.mark.skip(reason="Generator context not yet implemented")
    def test_range_expression(self):
        """range() expressions work in generator context."""
        from alienbio.build import GeneratorContext, eval_expr

        ctx = GeneratorContext(seed=42)
        result = eval_expr("list(range(1, 4))", ctx)
        assert result == [1, 2, 3]


# =============================================================================
# G3.2 - Distribution in Templates
# =============================================================================


class TestDistributionInParams:
    """Tests for distributions in template parameters."""

    @pytest.fixture
    def registry(self):
        """Registry with templates for distribution tests."""
        from alienbio.build import parse_template, TemplateRegistry

        registry = TemplateRegistry()
        registry.register("simple", parse_template({
            "molecules": {"M1": {"value": "!ref rate"}}
        }))
        return registry


    def test_param_with_distribution(self, registry):
        """Template param with !ev distribution is sampled."""
        from alienbio.build import parse_template, apply_template

        template = parse_template({
            "_params_": {"rate": "!ev lognormal(0.1, 0.3)"},
            "reactions": {"r1": {"rate": "!ref rate"}}
        })

        exp1 = apply_template(template, namespace="x", seed=42)
        exp2 = apply_template(template, namespace="x", seed=43)

        # Different seeds = different sampled values
        rate1 = exp1["reactions"]["r.x.r1"]["rate"]
        rate2 = exp2["reactions"]["r.x.r1"]["rate"]
        assert rate1 != rate2
        assert rate1 > 0  # lognormal is always positive
        assert rate2 > 0


    def test_same_seed_same_result(self):
        """Same seed produces identical sampled values."""
        from alienbio.build import parse_template, apply_template

        template = parse_template({
            "_params_": {"rate": "!ev lognormal(0.1, 0.3)"},
            "reactions": {"r1": {"rate": "!ref rate"}}
        })

        exp1 = apply_template(template, namespace="x", seed=42)
        exp2 = apply_template(template, namespace="x", seed=42)

        rate1 = exp1["reactions"]["r.x.r1"]["rate"]
        rate2 = exp2["reactions"]["r.x.r1"]["rate"]
        assert rate1 == rate2


    def test_multiple_distributions_same_template(self):
        """Multiple distribution params are independently sampled."""
        from alienbio.build import parse_template, apply_template

        template = parse_template({
            "_params_": {
                "rate1": "!ev normal(1.0, 0.1)",
                "rate2": "!ev normal(2.0, 0.1)"
            },
            "reactions": {
                "r1": {"rate": "!ref rate1"},
                "r2": {"rate": "!ref rate2"}
            }
        })

        expanded = apply_template(template, namespace="x", seed=42)
        r1 = expanded["reactions"]["r.x.r1"]["rate"]
        r2 = expanded["reactions"]["r.x.r2"]["rate"]

        # Should be around 1.0 and 2.0 respectively
        assert 0.5 < r1 < 1.5
        assert 1.5 < r2 < 2.5


class TestDistributionInMolecules:
    """Tests for distributions in molecule definitions."""


    def test_ev_in_molecule_field(self):
        """Molecule field with !ev is evaluated."""
        from alienbio.build import parse_template, apply_template

        template = parse_template({
            "molecules": {
                "M1": {
                    "role": "energy",
                    "initial_conc": "!ev uniform(0.1, 1.0)"
                }
            }
        })

        expanded = apply_template(template, namespace="x", seed=42)
        conc = expanded["molecules"]["m.x.M1"]["initial_conc"]
        assert 0.1 <= conc <= 1.0

    @pytest.mark.skip(reason="Molecule name expansion with {i in range} syntax not yet implemented")
    def test_ev_with_index(self):
        """!ev can use loop index variable."""
        from alienbio.build import parse_template, apply_template

        template = parse_template({
            "molecules": {
                "M{i in 1..3}": {
                    "role": "structural",
                    "description": "!ev f'Molecule {i}'"
                }
            }
        })

        expanded = apply_template(template, namespace="x", seed=42)
        assert expanded["molecules"]["m.x.M1"]["description"] == "Molecule 1"
        assert expanded["molecules"]["m.x.M2"]["description"] == "Molecule 2"
        assert expanded["molecules"]["m.x.M3"]["description"] == "Molecule 3"

    @pytest.mark.skip(reason="Molecule name expansion with {i in range} syntax not yet implemented")
    def test_ev_computed_from_index(self):
        """!ev can compute values from index."""
        from alienbio.build import parse_template, apply_template

        template = parse_template({
            "molecules": {
                "M{i in 1..3}": {
                    "depth": "!ev i * 10"
                }
            }
        })

        expanded = apply_template(template, namespace="x", seed=42)
        assert expanded["molecules"]["m.x.M1"]["depth"] == 10
        assert expanded["molecules"]["m.x.M2"]["depth"] == 20
        assert expanded["molecules"]["m.x.M3"]["depth"] == 30


class TestDistributionInLoopRanges:
    """Tests for distributions that determine loop iteration counts."""

    @pytest.fixture
    def registry(self):
        """Registry with simple template."""
        from alienbio.build import parse_template, TemplateRegistry

        registry = TemplateRegistry()
        registry.register("simple", parse_template({
            "molecules": {"M1": {}}
        }))
        return registry


    def test_distribution_in_loop_range(self, registry):
        """Loop count can come from sampled distribution."""
        from alienbio.build import parse_template, apply_template

        template = parse_template({
            "_params_": {"count": "!ev round(normal(3, 0.5))"},
            "_instantiate_": {
                "_as_ p{i in 1..count}": {"_template_": "simple"}
            }
        })

        expanded = apply_template(template, namespace="x", seed=42, registry=registry)
        mol_count = len([k for k in expanded["molecules"] if k.startswith("m.x.p")])
        # Should be approximately 3 (±1 or 2)
        assert 1 <= mol_count <= 5


    def test_distribution_loop_reproducible(self, registry):
        """Sampled loop count is reproducible with same seed."""
        from alienbio.build import parse_template, apply_template

        template = parse_template({
            "_params_": {"count": "!ev round(normal(3, 0.5))"},
            "_instantiate_": {
                "_as_ p{i in 1..count}": {"_template_": "simple"}
            }
        })

        exp1 = apply_template(template, namespace="x", seed=42, registry=registry)
        exp2 = apply_template(template, namespace="x", seed=42, registry=registry)

        count1 = len([k for k in exp1["molecules"] if k.startswith("m.x.p")])
        count2 = len([k for k in exp2["molecules"] if k.startswith("m.x.p")])
        assert count1 == count2


    def test_poisson_loop_count(self, registry):
        """Poisson distribution for count (always non-negative integer)."""
        from alienbio.build import parse_template, apply_template

        template = parse_template({
            "_params_": {"count": "!ev poisson(3)"},
            "_instantiate_": {
                "_as_ p{i in 1..count}": {"_template_": "simple"}
            }
        })

        expanded = apply_template(template, namespace="x", seed=42, registry=registry)
        mol_count = len([k for k in expanded["molecules"] if k.startswith("m.x.p")])
        assert mol_count >= 0  # Poisson can be 0
        assert isinstance(mol_count, int)


    def test_nested_distribution_dependencies(self, registry):
        """Distributions can depend on previously sampled values."""
        from alienbio.build import parse_template, apply_template

        template = parse_template({
            "_params_": {
                "base": "!ev round(uniform(2, 4))",
                "extra": "!ev round(base * uniform(0.5, 1.5))"
            },
            "_instantiate_": {
                "_as_ base{i in 1..base}": {"_template_": "simple"},
                "_as_ extra{i in 1..extra}": {"_template_": "simple"}
            }
        })

        expanded = apply_template(template, namespace="x", seed=42, registry=registry)
        base_count = len([k for k in expanded["molecules"] if ".base" in k])
        extra_count = len([k for k in expanded["molecules"] if ".extra" in k])

        assert 2 <= base_count <= 4
        # extra depends on base, so roughly 1-6
        assert extra_count >= 1


class TestDistributionEdgeCases:
    """Edge cases for distribution handling."""


    def test_zero_variance_normal(self):
        """Normal with std=0 returns mean exactly."""
        from alienbio.build import parse_template, apply_template

        template = parse_template({
            "_params_": {"rate": "!ev normal(0.5, 0)"},
            "reactions": {"r1": {"rate": "!ref rate"}}
        })

        expanded = apply_template(template, namespace="x", seed=42)
        assert expanded["reactions"]["r.x.r1"]["rate"] == 0.5


    def test_uniform_single_value(self):
        """Uniform with low==high returns that value."""
        from alienbio.build import parse_template, apply_template

        template = parse_template({
            "_params_": {"rate": "!ev uniform(0.5, 0.5)"},
            "reactions": {"r1": {"rate": "!ref rate"}}
        })

        expanded = apply_template(template, namespace="x", seed=42)
        assert expanded["reactions"]["r.x.r1"]["rate"] == 0.5

    def test_choice_single_option(self):
        """choice() with one option returns that option."""
        from alienbio.build import parse_template, apply_template

        template = parse_template({
            "_params_": {"color": "!ev choice(['red'])"},
            "molecules": {"M1": {"color": "!ref color"}}
        })

        expanded = apply_template(template, namespace="x", seed=42)
        assert expanded["molecules"]["m.x.M1"]["color"] == "red"
