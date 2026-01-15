"""Comprehensive test suite for spec evaluation system.

Tests for the evaluation pipeline: hydrate → eval → dehydrate.
See [[Spec Evaluation]] for the specification.

Tag semantics:
- !_     : preserve expression (Quoted) - for rate equations, lambdas
- !quote : alias for !_ (preserve expression)
- !ev    : evaluate expression at instantiation time (Evaluable)
- !ref   : lookup named value from bindings (Reference)
- !include: read file contents (resolved during hydration)

Design rationale:
    Most expressions in specs are "code" - rate equations, scoring functions -
    that shouldn't run at hydration. So !_ (the short form) preserves them.
    The rarer case - "actually compute this now" - uses the explicit !ev.

Key concepts tested:
- Hydration: tag→placeholder conversion
- Context: rng, bindings, functions, path
- Evaluation: Evaluable executed, Quoted preserved, Reference resolved
- Multiple instantiations: same spec, different seeds → different results
"""

import pytest
import yaml
import tempfile
import copy
from pathlib import Path
from dataclasses import dataclass
from typing import Any

import numpy as np

# Import implemented classes
from alienbio.spec_lang.eval import (
    Evaluable,
    Quoted,
    Reference,
    hydrate,
    dehydrate,
    EvalContext,
    eval_node,
    EvalError,
    SAFE_BUILTINS,
    DEFAULT_FUNCTIONS,
    make_context,
    normal,
    uniform,
    lognormal,
    poisson,
    exponential,
    choice,
    discrete,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def ctx():
    """Basic evaluation context with default functions."""
    return make_context(
        seed=42,
        bindings={'pi': 3.14159, 'radius': 10, 'factor': 2},
    )


@pytest.fixture
def seeded_ctx():
    """Context factory with configurable seed."""
    def _make_ctx(seed):
        return make_context(seed=seed)
    return _make_ctx


# =============================================================================
# HYDRATION TESTS
# =============================================================================

class TestHydrateConstants:
    """Test that constant values pass through hydration unchanged."""

    def test_hydrate_constant_int(self):
        """Integer constants pass through unchanged."""
        assert hydrate(42) == 42

    def test_hydrate_constant_float(self):
        """Float constants pass through unchanged."""
        assert hydrate(3.14159) == 3.14159

    def test_hydrate_constant_string(self):
        """String constants pass through unchanged."""
        assert hydrate("hello world") == "hello world"

    def test_hydrate_constant_bool_true(self):
        """True passes through unchanged."""
        assert hydrate(True) is True

    def test_hydrate_constant_bool_false(self):
        """False passes through unchanged."""
        assert hydrate(False) is False

    def test_hydrate_constant_none(self):
        """None passes through unchanged."""
        assert hydrate(None) is None

    def test_hydrate_constant_empty_dict(self):
        """Empty dict passes through unchanged."""
        assert hydrate({}) == {}

    def test_hydrate_constant_empty_list(self):
        """Empty list passes through unchanged."""
        assert hydrate([]) == []


class TestHydrateRecursive:
    """Test recursive hydration into dicts and lists."""

    def test_hydrate_nested_dicts(self):
        """Hydration descends into nested dicts."""
        data = {"outer": {"inner": {"value": 42}}}
        result = hydrate(data)
        assert result["outer"]["inner"]["value"] == 42

    def test_hydrate_nested_lists(self):
        """Hydration descends into nested lists."""
        data = [[1, 2], [3, 4], [5, 6]]
        result = hydrate(data)
        assert result == [[1, 2], [3, 4], [5, 6]]

    def test_hydrate_mixed_structure(self):
        """Hydration handles mixed dicts and lists."""
        data = {
            "items": [{"name": "a"}, {"name": "b"}],
            "config": {"values": [1, 2, 3]},
        }
        result = hydrate(data)
        assert result["items"][0]["name"] == "a"
        assert result["config"]["values"] == [1, 2, 3]

    def test_hydrate_deeply_nested(self):
        """Hydration handles deep nesting (10 levels)."""
        data = {"l1": {"l2": {"l3": {"l4": {"l5": {"l6": {"l7": {"l8": {"l9": {"l10": "deep"}}}}}}}}}}
        result = hydrate(data)
        assert result["l1"]["l2"]["l3"]["l4"]["l5"]["l6"]["l7"]["l8"]["l9"]["l10"] == "deep"


class TestHydrateUnderscoreTag:
    """Test !_ tag converts to Quoted placeholder (preserves expression)."""

    def test_hydrate_underscore_simple(self):
        """!_ tag becomes Quoted placeholder (preserved for later)."""
        # Simulating what YAML parser would produce for: value: !_ k * S
        data = {"value": {"!_": "k * S"}}
        result = hydrate(data)
        assert isinstance(result["value"], Quoted)
        assert result["value"].source == "k * S"

    def test_hydrate_underscore_rate_expression(self):
        """!_ with rate expression becomes Quoted."""
        data = {"rate": {"!_": "Vmax * S / (Km + S)"}}
        result = hydrate(data)
        assert isinstance(result["rate"], Quoted)
        assert result["rate"].source == "Vmax * S / (Km + S)"

    def test_hydrate_underscore_complex_expression(self):
        """!_ with complex expression becomes Quoted."""
        data = {"rate": {"!_": "k1 * S1 * S2 - k2 * P"}}
        result = hydrate(data)
        assert isinstance(result["rate"], Quoted)
        assert result["rate"].source == "k1 * S1 * S2 - k2 * P"

    def test_hydrate_underscore_nested_in_dict(self):
        """!_ nested inside dict structure."""
        data = {
            "reactions": {
                "r1": {
                    "rate": {"!_": "k * S"}
                }
            }
        }
        result = hydrate(data)
        assert isinstance(result["reactions"]["r1"]["rate"], Quoted)

    def test_hydrate_underscore_in_list(self):
        """!_ inside a list."""
        data = {"rates": [{"!_": "k1 * S"}, {"!_": "k2 * S"}]}
        result = hydrate(data)
        assert isinstance(result["rates"][0], Quoted)
        assert isinstance(result["rates"][1], Quoted)


class TestHydrateEvTag:
    """Test !ev tag converts to Evaluable placeholder (evaluated at instantiation)."""

    def test_hydrate_ev_simple(self):
        """!ev tag becomes Evaluable placeholder."""
        data = {"value": {"!ev": "2 + 3"}}
        result = hydrate(data)
        assert isinstance(result["value"], Evaluable)
        assert result["value"].source == "2 + 3"

    def test_hydrate_ev_function_call(self):
        """!ev with function call becomes Evaluable."""
        data = {"count": {"!ev": "normal(50, 10)"}}
        result = hydrate(data)
        assert isinstance(result["count"], Evaluable)
        assert result["count"].source == "normal(50, 10)"

    def test_hydrate_ev_complex_expression(self):
        """!ev with complex expression becomes Evaluable."""
        data = {"area": {"!ev": "pi * radius * radius"}}
        result = hydrate(data)
        assert isinstance(result["area"], Evaluable)
        assert result["area"].source == "pi * radius * radius"

    def test_hydrate_ev_nested_in_dict(self):
        """!ev nested inside dict structure."""
        data = {
            "scenario": {
                "params": {
                    "count": {"!ev": "normal(50, 10)"}
                }
            }
        }
        result = hydrate(data)
        assert isinstance(result["scenario"]["params"]["count"], Evaluable)

    def test_hydrate_ev_in_list(self):
        """!ev inside a list."""
        data = {"values": [{"!ev": "normal(1, 0.1)"}, {"!ev": "normal(2, 0.2)"}]}
        result = hydrate(data)
        assert isinstance(result["values"][0], Evaluable)
        assert isinstance(result["values"][1], Evaluable)


class TestHydrateQuoteTag:
    """Test !quote tag converts to Quoted placeholder."""

    def test_hydrate_quote_simple(self):
        """!quote tag becomes Quoted placeholder."""
        data = {"rate": {"!quote": "k * S"}}
        result = hydrate(data)
        assert isinstance(result["rate"], Quoted)
        assert result["rate"].source == "k * S"

    def test_hydrate_quote_michaelis_menten(self):
        """!quote with Michaelis-Menten rate."""
        data = {"rate": {"!quote": "Vmax * S / (Km + S)"}}
        result = hydrate(data)
        assert isinstance(result["rate"], Quoted)
        assert result["rate"].source == "Vmax * S / (Km + S)"

    def test_hydrate_quote_mass_action(self):
        """!quote with mass action rate."""
        data = {"rate": {"!quote": "k * S1 * S2"}}
        result = hydrate(data)
        assert isinstance(result["rate"], Quoted)
        assert result["rate"].source == "k * S1 * S2"

    def test_hydrate_quote_hill_equation(self):
        """!quote with Hill equation."""
        data = {"rate": {"!quote": "Vmax * S**n / (K**n + S**n)"}}
        result = hydrate(data)
        assert isinstance(result["rate"], Quoted)

    def test_hydrate_quote_preserves_whitespace(self):
        """!quote preserves expression exactly including whitespace."""
        expr = "  k  *  S  "
        data = {"rate": {"!quote": expr}}
        result = hydrate(data)
        assert result["rate"].source == expr


class TestHydrateRefTag:
    """Test !ref tag converts to Reference placeholder."""

    def test_hydrate_ref_simple(self):
        """!ref tag becomes Reference placeholder."""
        data = {"permeability": {"!ref": "high_permeability"}}
        result = hydrate(data)
        assert isinstance(result["permeability"], Reference)
        assert result["permeability"].name == "high_permeability"

    def test_hydrate_ref_dotted_name(self):
        """!ref with dotted name."""
        data = {"config": {"!ref": "defaults.config.timeout"}}
        result = hydrate(data)
        assert isinstance(result["config"], Reference)
        assert result["config"].name == "defaults.config.timeout"

    def test_hydrate_ref_underscore_name(self):
        """!ref with underscores in name."""
        data = {"value": {"!ref": "my_const_123"}}
        result = hydrate(data)
        assert result["value"].name == "my_const_123"


class TestHydrateIncludeTag:
    """Test !include tag resolves files during hydration."""

    def test_hydrate_include_markdown(self, temp_dir):
        """!include reads markdown file as string."""
        md_file = temp_dir / "safety.md"
        md_file.write_text("# Safety Rules\n\nBe careful.")

        data = {"constitution": {"!include": "safety.md"}}
        result = hydrate(data, base_path=str(temp_dir))

        assert result["constitution"] == "# Safety Rules\n\nBe careful."

    def test_hydrate_include_yaml(self, temp_dir):
        """!include reads and parses YAML file."""
        yaml_file = temp_dir / "config.yaml"
        yaml_file.write_text("timeout: 30\nretries: 3")

        data = {"config": {"!include": "config.yaml"}}
        result = hydrate(data, base_path=str(temp_dir))

        assert result["config"] == {"timeout": 30, "retries": 3}

    def test_hydrate_include_missing_file(self, temp_dir):
        """!include with missing file raises FileNotFoundError."""
        data = {"content": {"!include": "nonexistent.md"}}

        with pytest.raises(FileNotFoundError):
            hydrate(data, base_path=str(temp_dir))

    @pytest.mark.skip(reason="Nested YAML includes need IncludeTag registered")
    def test_hydrate_include_nested(self, temp_dir):
        """!include resolves nested includes."""
        inner_file = temp_dir / "inner.md"
        inner_file.write_text("Inner content")

        outer_file = temp_dir / "outer.yaml"
        outer_file.write_text("inner: !include inner.md")

        data = {"outer": {"!include": "outer.yaml"}}
        result = hydrate(data, base_path=str(temp_dir))

        assert result["outer"]["inner"] == "Inner content"


class TestHydrateTypeInstantiation:
    """Test type instantiation from _type field."""

    @pytest.mark.skip(reason="Implementation pending")
    def test_hydrate_type_simple(self):
        """Dict with _type becomes class instance."""
        # Would need biotype registry setup
        data = {"_type": "scenario", "name": "test", "briefing": "Test briefing"}
        result = hydrate(data)
        # Should be a Scenario instance, not a dict
        assert hasattr(result, 'name')
        assert result.name == "test"

    @pytest.mark.skip(reason="Implementation pending")
    def test_hydrate_typed_key_syntax(self):
        """scenario.name: syntax transforms to _type."""
        # Input uses typed key syntax
        data = {"scenario.test": {"briefing": "Test briefing"}}
        result = hydrate(data)
        # Should become instance with name="test"
        assert "test" in result or hasattr(result.get("test", {}), 'briefing')

    @pytest.mark.skip(reason="Implementation pending")
    def test_hydrate_nested_types(self):
        """Nested typed objects hydrate recursively."""
        data = {
            "_type": "scenario",
            "chemistry": {
                "_type": "chemistry",
                "molecules": {"A": {}, "B": {}},
            }
        }
        result = hydrate(data)
        # Both scenario and chemistry should be instances
        assert hasattr(result, 'chemistry')


class TestHydrateMixed:
    """Test hydration with mixed tags, types, and constants."""

    def test_hydrate_mixed_all_tags(self):
        """Structure with all tag types together."""
        data = {
            "rate": {"!_": "k * S"},          # !_ → Quoted (preserved)
            "count": {"!ev": "normal(50, 10)"},  # !ev → Evaluable (computed)
            "permeability": {"!ref": "high_perm"},
            "timeout": 30,
            "name": "test",
        }
        result = hydrate(data)

        assert isinstance(result["rate"], Quoted)
        assert isinstance(result["count"], Evaluable)
        assert isinstance(result["permeability"], Reference)
        assert result["timeout"] == 30
        assert result["name"] == "test"

    def test_hydrate_realistic_scenario(self, temp_dir):
        """Realistic scenario structure."""
        constitution_file = temp_dir / "constitution.md"
        constitution_file.write_text("Protect all species.")

        data = {
            "scenario.mutualism": {
                "params": {
                    "count": {"!ev": "normal(50, 10)"},  # !ev for computed values
                },
                "reactions": {
                    "r1": {
                        "rate": {"!_": "k * S1 * S2"},  # !_ for rate expressions
                    }
                },
                "constitution": {"!include": "constitution.md"},
                "permeability": {"!ref": "high_permeability"},
            }
        }
        result = hydrate(data, base_path=str(temp_dir))

        # All parts should be properly hydrated
        assert "mutualism" in result or "scenario.mutualism" in result


# =============================================================================
# DEHYDRATION TESTS
# =============================================================================

class TestDehydrate:
    """Test dehydration converts back to serializable form."""

    def test_dehydrate_evaluable(self):
        """Evaluable becomes {"!ev": source}."""
        data = {"count": Evaluable(source="normal(50, 10)")}
        result = dehydrate(data)
        assert result == {"count": {"!ev": "normal(50, 10)"}}

    def test_dehydrate_quoted(self):
        """Quoted becomes {"!_": source}."""
        data = {"rate": Quoted(source="k * S")}
        result = dehydrate(data)
        assert result == {"rate": {"!_": "k * S"}}

    def test_dehydrate_reference(self):
        """Reference becomes {"!ref": name}."""
        data = {"perm": Reference(name="high_permeability")}
        result = dehydrate(data)
        assert result == {"perm": {"!ref": "high_permeability"}}

    def test_dehydrate_nested(self):
        """Dehydration handles nested structures."""
        data = {
            "outer": {
                "count": Evaluable(source="42"),
                "rate": Quoted(source="k * S"),
            }
        }
        result = dehydrate(data)
        assert result["outer"]["count"] == {"!ev": "42"}
        assert result["outer"]["rate"] == {"!_": "k * S"}

    def test_dehydrate_constants_unchanged(self):
        """Constants pass through dehydration unchanged."""
        data = {"x": 42, "y": "hello", "z": [1, 2, 3]}
        result = dehydrate(data)
        assert result == data


class TestDehydrateRoundTrip:
    """Test round-trip: dehydrate(hydrate(x)) ≈ x.

    Note: !quote normalizes to !_ on roundtrip (both are Quoted).
    Use canonical forms (!_ for preserved, !ev for evaluated) for exact roundtrip.
    """

    def test_roundtrip_simple(self):
        """Simple round-trip preserves structure."""
        original = {
            "count": {"!ev": "normal(50, 10)"},  # Evaluable
            "rate": {"!_": "k * S"},              # Quoted (canonical form)
            "perm": {"!ref": "high_perm"},
            "timeout": 30,
        }
        hydrated = hydrate(original)
        dehydrated = dehydrate(hydrated)
        assert dehydrated == original

    def test_roundtrip_nested(self):
        """Nested round-trip preserves structure."""
        original = {
            "scenario": {
                "params": {"count": {"!ev": "normal(50, 10)"}},
                "reactions": {"rate": {"!_": "k * S"}},
            }
        }
        hydrated = hydrate(original)
        dehydrated = dehydrate(hydrated)
        assert dehydrated == original

    def test_roundtrip_complex(self):
        """Complex realistic structure round-trips."""
        original = {
            "constants": {"high_perm": 0.8, "low_perm": 0.1},
            "scenario.test": {
                "params": {
                    "A_count": {"!ev": "normal(100, 10)"},
                    "B_count": {"!ev": "uniform(50, 150)"},
                },
                "reactions": {
                    "r1": {"rate": {"!_": "k1 * S1 * S2"}},
                    "r2": {"rate": {"!_": "Vmax * S / (Km + S)"}},
                },
                "permeability": {"!ref": "high_perm"},
            }
        }
        hydrated = hydrate(original)
        dehydrated = dehydrate(hydrated)
        # Note: typed keys might transform, so compare semantically
        assert "scenario.test" in dehydrated or "test" in dehydrated


# =============================================================================
# EVAL BASIC TESTS
# =============================================================================

class TestEvalConstants:
    """Test that constants evaluate to themselves."""

    def test_eval_constant_int(self, ctx):
        """Integer evaluates to itself."""
        assert eval_node(42, ctx) == 42

    def test_eval_constant_float(self, ctx):
        """Float evaluates to itself."""
        assert eval_node(3.14159, ctx) == 3.14159

    def test_eval_constant_string(self, ctx):
        """String evaluates to itself."""
        assert eval_node("hello", ctx) == "hello"

    def test_eval_constant_bool(self, ctx):
        """Booleans evaluate to themselves."""
        assert eval_node(True, ctx) is True
        assert eval_node(False, ctx) is False

    def test_eval_constant_none(self, ctx):
        """None evaluates to itself."""
        assert eval_node(None, ctx) is None

    def test_eval_constant_dict(self, ctx):
        """Plain dict evaluates to itself."""
        data = {"a": 1, "b": 2}
        result = eval_node(data, ctx)
        assert result == {"a": 1, "b": 2}

    def test_eval_constant_list(self, ctx):
        """Plain list evaluates to itself."""
        data = [1, 2, 3]
        result = eval_node(data, ctx)
        assert result == [1, 2, 3]

    def test_eval_nested_constants(self, ctx):
        """Nested constant structure evaluates to itself."""
        data = {"outer": {"inner": [1, 2, {"deep": "value"}]}}
        result = eval_node(data, ctx)
        assert result == data


# =============================================================================
# EVAL EXPRESSION TESTS
# =============================================================================

class TestEvalExpressions:
    """Test Evaluable expressions are evaluated correctly."""

    def test_eval_expr_addition(self, ctx):
        """!_ 2 + 3 evaluates to 5."""
        node = Evaluable(source="2 + 3")
        assert eval_node(node, ctx) == 5

    def test_eval_expr_multiplication(self, ctx):
        """!_ 6 * 7 evaluates to 42."""
        node = Evaluable(source="6 * 7")
        assert eval_node(node, ctx) == 42

    def test_eval_expr_division(self, ctx):
        """!_ 10 / 4 evaluates to 2.5."""
        node = Evaluable(source="10 / 4")
        assert eval_node(node, ctx) == 2.5

    def test_eval_expr_complex(self, ctx):
        """Complex expression with bindings."""
        # ctx has pi=3.14159, radius=10
        node = Evaluable(source="pi * radius * radius")
        result = eval_node(node, ctx)
        assert result == pytest.approx(314.159, rel=1e-3)

    def test_eval_expr_builtin_min(self, ctx):
        """!_ min(3, 1, 2) evaluates to 1."""
        node = Evaluable(source="min(3, 1, 2)")
        assert eval_node(node, ctx) == 1

    def test_eval_expr_builtin_max(self, ctx):
        """!_ max(3, 1, 2) evaluates to 3."""
        node = Evaluable(source="max(3, 1, 2)")
        assert eval_node(node, ctx) == 3

    def test_eval_expr_builtin_abs(self, ctx):
        """!_ abs(-5) evaluates to 5."""
        node = Evaluable(source="abs(-5)")
        assert eval_node(node, ctx) == 5

    def test_eval_expr_builtin_round(self, ctx):
        """!_ round(3.7) evaluates to 4."""
        node = Evaluable(source="round(3.7)")
        assert eval_node(node, ctx) == 4

    def test_eval_expr_builtin_sum(self, ctx):
        """!_ sum([1, 2, 3, 4]) evaluates to 10."""
        node = Evaluable(source="sum([1, 2, 3, 4])")
        assert eval_node(node, ctx) == 10

    def test_eval_expr_builtin_len(self, ctx):
        """!_ len([1, 2, 3]) evaluates to 3."""
        node = Evaluable(source="len([1, 2, 3])")
        assert eval_node(node, ctx) == 3

    def test_eval_expr_conditional(self, ctx):
        """!_ x if cond else y evaluates conditionally."""
        ctx.bindings['x'] = 10
        ctx.bindings['y'] = 20
        ctx.bindings['cond'] = True
        node = Evaluable(source="x if cond else y")
        assert eval_node(node, ctx) == 10

        ctx.bindings['cond'] = False
        assert eval_node(node, ctx) == 20

    def test_eval_expr_list_comprehension(self, ctx):
        """!_ [x*2 for x in items] evaluates comprehension."""
        ctx.bindings['items'] = [1, 2, 3]
        node = Evaluable(source="[x*2 for x in items]")
        assert eval_node(node, ctx) == [2, 4, 6]

    def test_eval_expr_uses_bindings(self, ctx):
        """Expression uses variables from ctx.bindings."""
        ctx.bindings['a'] = 10
        ctx.bindings['b'] = 20
        node = Evaluable(source="a + b")
        assert eval_node(node, ctx) == 30

    def test_eval_expr_returns_dict(self, ctx):
        """Expression can return a dict."""
        node = Evaluable(source='{"a": 1, "b": 2}')
        result = eval_node(node, ctx)
        assert result == {"a": 1, "b": 2}

    def test_eval_expr_returns_list(self, ctx):
        """Expression can return a list."""
        node = Evaluable(source="[1, 2, 3]")
        result = eval_node(node, ctx)
        assert result == [1, 2, 3]


# =============================================================================
# EVAL QUOTE TESTS
# =============================================================================

class TestEvalQuote:
    """Test Quoted expressions are preserved unchanged."""

    def test_eval_quote_simple(self, ctx):
        """!quote k * S returns string "k * S"."""
        node = Quoted(source="k * S")
        result = eval_node(node, ctx)
        assert result == "k * S"

    def test_eval_quote_michaelis_menten(self, ctx):
        """!quote Vmax * S / (Km + S) preserved."""
        node = Quoted(source="Vmax * S / (Km + S)")
        result = eval_node(node, ctx)
        assert result == "Vmax * S / (Km + S)"

    def test_eval_quote_not_evaluated(self, ctx):
        """Variables in quote are NOT resolved."""
        ctx.bindings['k'] = 0.5
        ctx.bindings['S'] = 100
        node = Quoted(source="k * S")
        result = eval_node(node, ctx)
        # Should be the string, not 50
        assert result == "k * S"
        assert result != 50

    def test_eval_quote_in_dict(self, ctx):
        """Quote inside dict structure."""
        data = {"rate": Quoted(source="k * S"), "name": "reaction1"}
        result = eval_node(data, ctx)
        assert result["rate"] == "k * S"
        assert result["name"] == "reaction1"

    def test_eval_quote_in_list(self, ctx):
        """Quote inside list."""
        data = [Quoted(source="k1 * S"), Quoted(source="k2 * S")]
        result = eval_node(data, ctx)
        assert result == ["k1 * S", "k2 * S"]

    def test_eval_quote_preserves_whitespace(self, ctx):
        """Quote preserves exact whitespace."""
        node = Quoted(source="  k  *  S  ")
        result = eval_node(node, ctx)
        assert result == "  k  *  S  "


# =============================================================================
# EVAL REFERENCE TESTS
# =============================================================================

class TestEvalReference:
    """Test Reference resolution from bindings."""

    def test_eval_ref_simple(self, ctx):
        """!ref foo resolves to ctx.bindings["foo"]."""
        ctx.bindings["foo"] = 42
        node = Reference(name="foo")
        assert eval_node(node, ctx) == 42

    def test_eval_ref_nested_value(self, ctx):
        """Reference to dict returns whole dict."""
        ctx.bindings["config"] = {"timeout": 30, "retries": 3}
        node = Reference(name="config")
        result = eval_node(node, ctx)
        assert result == {"timeout": 30, "retries": 3}

    def test_eval_ref_missing_strict(self, ctx):
        """Missing reference raises EvalError."""
        node = Reference(name="nonexistent")
        with pytest.raises(EvalError):
            eval_node(node, ctx)

    @pytest.mark.skip(reason="Non-strict mode not implemented")
    def test_eval_ref_missing_nonstrict(self, ctx):
        """Missing reference in non-strict mode returns Reference."""
        node = Reference(name="nonexistent")
        result = eval_node(node, ctx, strict=False)
        assert isinstance(result, Reference)
        assert result.name == "nonexistent"

    def test_eval_ref_string_value(self, ctx):
        """Reference to string value."""
        ctx.bindings["message"] = "hello world"
        node = Reference(name="message")
        assert eval_node(node, ctx) == "hello world"


# =============================================================================
# FUNCTION TESTS
# =============================================================================

class TestFunctionDecorator:
    """Test @function decorator and ctx injection."""

    @pytest.mark.skip(reason="Function decorator registry not implemented")
    def test_function_decorator_registers(self):
        """@function adds function to registry."""
        # Would need function registry
        pass

    def test_function_ctx_injection(self, ctx):
        """ctx is auto-injected as keyword parameter."""
        # ctx already has normal from DEFAULT_FUNCTIONS
        node = Evaluable(source="normal(50, 10)")
        result = eval_node(node, ctx)
        # Should be a float near 50
        assert isinstance(result, (int, float))

    def test_function_normal_distribution(self, ctx):
        """normal(50, 10) returns float from normal distribution."""
        node = Evaluable(source="normal(50, 10)")

        # Sample multiple times to verify distribution
        results = [eval_node(node, make_context(seed=i)) for i in range(100)]

        mean_val = sum(results) / len(results)
        assert 40 < mean_val < 60  # Should be near 50

    def test_function_uniform_distribution(self, ctx):
        """uniform(0, 1) returns float in [0, 1]."""
        node = Evaluable(source="uniform(0, 1)")

        for seed in range(20):
            result = eval_node(node, make_context(seed=seed))
            assert 0 <= result <= 1

    def test_function_discrete_weights(self, ctx):
        """discrete([0.5, 0.5]) returns index 0 or 1."""
        node = Evaluable(source="discrete([0.5, 0.5])")
        result = eval_node(node, ctx)
        assert result in (0, 1)

    def test_function_choice(self, ctx):
        """choice(["a", "b", "c"]) picks one uniformly."""
        node = Evaluable(source='choice(["a", "b", "c"])')
        result = eval_node(node, ctx)
        assert result in ("a", "b", "c")

    def test_function_uses_ctx_rng(self, ctx):
        """Functions use ctx.rng for reproducibility."""
        # Same seed should give same result
        ctx1 = make_context(seed=42)
        ctx2 = make_context(seed=42)

        node = Evaluable(source="normal(50, 10)")
        result1 = eval_node(node, ctx1)
        result2 = eval_node(node, ctx2)

        assert result1 == result2

    def test_function_with_bindings(self, ctx):
        """!_ normal(mu, sigma) with bound variables."""
        ctx.bindings['mu'] = 100
        ctx.bindings['sigma'] = 5

        node = Evaluable(source="normal(mu, sigma)")
        result = eval_node(node, ctx)
        assert isinstance(result, (int, float))


# =============================================================================
# CONTEXT TESTS
# =============================================================================

class TestContext:
    """Test Context object behavior."""

    def test_context_rng_seeded(self):
        """Same seed produces same results."""
        ctx1 = make_context(seed=42)
        ctx2 = make_context(seed=42)

        assert ctx1.rng.random() == ctx2.rng.random()

    def test_context_rng_different_seeds(self):
        """Different seeds produce different results."""
        ctx1 = make_context(seed=42)
        ctx2 = make_context(seed=99)

        assert ctx1.rng.random() != ctx2.rng.random()

    def test_context_bindings_lookup(self):
        """Bindings are accessible."""
        ctx = make_context(bindings={"x": 10, "y": 20})
        assert ctx.bindings["x"] == 10
        assert ctx.bindings["y"] == 20

    def test_context_bindings_missing(self):
        """Missing binding raises KeyError."""
        ctx = make_context(bindings={"x": 10})
        with pytest.raises(KeyError):
            _ = ctx.bindings["z"]

    def test_context_functions_available(self):
        """Registered functions are accessible."""
        def my_func():
            return 42

        ctx = EvalContext(functions={"my_func": my_func})
        assert ctx.functions["my_func"]() == 42

    def test_context_child_extends_path(self):
        """Child context extends the path."""
        parent = EvalContext(path="scenario")
        child = parent.child("molecules")

        assert child.path == "scenario.molecules"

    def test_context_child_inherits_bindings(self):
        """Child sees parent bindings."""
        parent = EvalContext(bindings={"x": 10, "y": 20})
        child = parent.child("key")

        # Child shares same bindings dict reference
        assert child.bindings["x"] == 10
        assert child.bindings["y"] == 20

    def test_context_path_tracking(self):
        """Path builds up through nested child calls."""
        ctx = EvalContext(path="")
        child1 = ctx.child("scenario")
        child2 = child1.child("molecules")
        child3 = child2.child("A")

        assert child3.path == "scenario.molecules.A"


# =============================================================================
# MULTIPLE INSTANTIATION TESTS
# =============================================================================

class TestMultipleInstantiations:
    """Test multiple evaluations with different seeds."""

    def test_instantiation_same_seed_same_result(self, seeded_ctx):
        """Same seed produces identical results."""
        data = {"count": Evaluable(source="normal(50, 10)")}

        ctx1 = seeded_ctx(42)
        ctx2 = seeded_ctx(42)

        result1 = eval_node(data, ctx1)
        result2 = eval_node(data, ctx2)

        assert result1["count"] == result2["count"]

    def test_instantiation_different_seeds(self, seeded_ctx):
        """Different seeds produce different random values."""
        data = {"count": Evaluable(source="normal(50, 10)")}

        results = []
        for seed in range(10):
            ctx = seeded_ctx(seed)
            result = eval_node(data, ctx)
            results.append(result["count"])

        # Not all results should be the same
        assert len(set(results)) > 1

    def test_instantiation_spec_unchanged(self):
        """Original spec not mutated by evaluation."""
        original_data = {"count": Evaluable(source="normal(50, 10)")}
        data_copy = copy.deepcopy(original_data)

        ctx = make_context(seed=42)
        _ = eval_node(original_data, ctx)

        # Original should still have Evaluable, not the result
        assert isinstance(original_data["count"], Evaluable)
        assert original_data == data_copy

    def test_instantiation_10_seeds(self):
        """Loop with 10 different seeds all produce valid results."""
        data = {
            "a": Evaluable(source="normal(50, 10)"),
            "b": Evaluable(source="normal(100, 20)"),
        }

        for seed in range(10):
            ctx = make_context(seed=seed)
            result = eval_node(data, ctx)

            assert isinstance(result["a"], (int, float))
            assert isinstance(result["b"], (int, float))
            # Rough sanity check on ranges
            assert 0 < result["a"] < 100
            assert 0 < result["b"] < 200

    def test_instantiation_quotes_preserved(self):
        """!quote expressions survive all evaluations unchanged."""
        data = {
            "rate": Quoted(source="k * S"),
            "count": Evaluable(source="42"),
        }

        for seed in range(5):
            ctx = make_context(seed=seed)
            result = eval_node(data, ctx)

            # Quote should always be the string, not evaluated
            assert result["rate"] == "k * S"
            # Evaluable should be evaluated
            assert result["count"] == 42


# =============================================================================
# LEXICAL SCOPING TESTS
# =============================================================================

class TestLexicalScoping:
    """Test lexical scoping and inheritance."""

    def test_scope_top_level_constants(self, ctx):
        """Constants at module level are accessible."""
        ctx.bindings['pi'] = 3.14159
        ctx.bindings['e'] = 2.71828

        node = Evaluable(source="pi + e")
        result = eval_node(node, ctx)
        assert result == pytest.approx(5.85987)

    def test_scope_scenario_inherits_module(self, ctx):
        """Scenario sees module-level constants."""
        ctx.bindings['global_const'] = 100

        # Evaluate expression in scenario context
        node = Evaluable(source="global_const * 2")
        result = eval_node(node, ctx)
        assert result == 200

    def test_scope_bindings_shared(self, ctx):
        """Child context shares parent bindings."""
        parent = make_context(bindings={'x': 10})
        child = parent.child("key")

        node = Evaluable(source="x")
        # Child sees parent's bindings (shared reference)
        assert eval_node(node, child) == 10

    def test_scope_accumulative_bindings(self):
        """Bindings can be added to shared dict."""
        ctx = make_context(bindings={'a': 1})
        ctx.bindings['b'] = 2
        ctx.bindings['c'] = 3
        ctx.bindings['d'] = 4

        node = Evaluable(source="a + b + c + d")
        result = eval_node(node, ctx)
        assert result == 10


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

class TestErrorHandling:
    """Test error cases."""

    def test_error_undefined_variable(self, ctx):
        """Clear error for undefined variable."""
        node = Evaluable(source="undefined_var")
        with pytest.raises(EvalError) as exc_info:
            eval_node(node, ctx)
        assert "undefined_var" in str(exc_info.value)

    def test_error_syntax_in_expression(self, ctx):
        """Invalid Python syntax raises error."""
        # Note: "2 + + 3" is valid Python (unary +), so use actual syntax error
        node = Evaluable(source="2 + ")
        with pytest.raises(EvalError):
            eval_node(node, ctx)

    def test_error_division_by_zero(self, ctx):
        """Division by zero raises error."""
        node = Evaluable(source="1 / 0")
        with pytest.raises(EvalError):
            eval_node(node, ctx)

    def test_error_unknown_function(self, ctx):
        """Unknown function raises EvalError."""
        node = Evaluable(source="unknown_func(42)")
        with pytest.raises(EvalError) as exc_info:
            eval_node(node, ctx)
        assert "unknown_func" in str(exc_info.value)

    def test_error_include_file_not_found(self, temp_dir):
        """Missing include file raises FileNotFoundError."""
        data = {"content": {"!include": "missing.md"}}
        with pytest.raises(FileNotFoundError):
            hydrate(data, base_path=str(temp_dir))

    def test_error_blocked_builtins(self, ctx):
        """Dangerous builtins are blocked."""
        # These should all fail with EvalError
        dangerous = [
            'open("/etc/passwd")',
            '__import__("os")',
            'eval("1+1")',
            'exec("print(1)")',
        ]
        for expr in dangerous:
            node = Evaluable(source=expr)
            with pytest.raises(EvalError):
                eval_node(node, ctx)


# =============================================================================
# EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Edge cases and unusual inputs."""

    def test_edge_empty_dict(self, ctx):
        """Empty dict evaluates to empty dict."""
        assert eval_node({}, ctx) == {}

    def test_edge_empty_list(self, ctx):
        """Empty list evaluates to empty list."""
        assert eval_node([], ctx) == []

    def test_edge_deeply_nested(self, ctx):
        """10 levels of nesting."""
        data = {"l1": {"l2": {"l3": {"l4": {"l5": {"l6": {"l7": {"l8": {"l9": {"l10": 42}}}}}}}}}}
        result = eval_node(data, ctx)
        assert result["l1"]["l2"]["l3"]["l4"]["l5"]["l6"]["l7"]["l8"]["l9"]["l10"] == 42

    def test_edge_large_structure(self, ctx):
        """Structure with 1000 keys."""
        data = {f"key_{i}": i for i in range(1000)}
        result = eval_node(data, ctx)
        assert len(result) == 1000
        assert result["key_500"] == 500

    def test_edge_unicode_in_expression(self, ctx):
        """Unicode in expression."""
        node = Evaluable(source='"héllo" * 2')
        result = eval_node(node, ctx)
        assert result == "héllohéllo"

    def test_edge_expression_with_newlines(self, ctx):
        """Expression with embedded newlines (from multiline YAML)."""
        # YAML might produce this from a folded scalar
        node = Evaluable(source="sum([\n  1,\n  2,\n  3\n])")
        result = eval_node(node, ctx)
        assert result == 6

    def test_edge_very_long_expression(self, ctx):
        """Very long expression."""
        # 100 terms
        terms = " + ".join(str(i) for i in range(100))
        node = Evaluable(source=terms)
        result = eval_node(node, ctx)
        assert result == sum(range(100))


# =============================================================================
# SAFE BUILTINS TESTS
# =============================================================================

class TestSafeBuiltins:
    """Test that safe builtins are available and dangerous ones blocked."""

    def test_safe_min(self, ctx):
        assert eval_node(Evaluable("min(3, 1, 2)"), ctx) == 1

    def test_safe_max(self, ctx):
        assert eval_node(Evaluable("max(3, 1, 2)"), ctx) == 3

    def test_safe_abs(self, ctx):
        assert eval_node(Evaluable("abs(-5)"), ctx) == 5

    def test_safe_round(self, ctx):
        assert eval_node(Evaluable("round(3.7)"), ctx) == 4

    def test_safe_sum(self, ctx):
        assert eval_node(Evaluable("sum([1,2,3])"), ctx) == 6

    def test_safe_len(self, ctx):
        assert eval_node(Evaluable("len([1,2,3])"), ctx) == 3

    def test_safe_int(self, ctx):
        assert eval_node(Evaluable("int(3.9)"), ctx) == 3

    def test_safe_float(self, ctx):
        assert eval_node(Evaluable("float(3)"), ctx) == 3.0

    def test_safe_str(self, ctx):
        assert eval_node(Evaluable("str(42)"), ctx) == "42"

    def test_safe_bool(self, ctx):
        assert eval_node(Evaluable("bool(1)"), ctx) is True

    def test_safe_list(self, ctx):
        assert eval_node(Evaluable("list(range(3))"), ctx) == [0, 1, 2]

    def test_safe_dict(self, ctx):
        assert eval_node(Evaluable("dict(a=1, b=2)"), ctx) == {"a": 1, "b": 2}

    @pytest.mark.skip(reason="sorted not in SAFE_BUILTINS")
    def test_safe_sorted(self, ctx):
        assert eval_node(Evaluable("sorted([3,1,2])"), ctx) == [1, 2, 3]

    @pytest.mark.skip(reason="reversed not in SAFE_BUILTINS")
    def test_safe_reversed(self, ctx):
        assert eval_node(Evaluable("list(reversed([1,2,3]))"), ctx) == [3, 2, 1]

    def test_blocked_open(self, ctx):
        with pytest.raises(EvalError):
            eval_node(Evaluable('open("/etc/passwd")'), ctx)

    def test_blocked_import(self, ctx):
        with pytest.raises(EvalError):
            eval_node(Evaluable('__import__("os")'), ctx)

    def test_blocked_eval(self, ctx):
        with pytest.raises(EvalError):
            eval_node(Evaluable('eval("1+1")'), ctx)

    def test_blocked_exec(self, ctx):
        with pytest.raises(EvalError):
            eval_node(Evaluable('exec("x=1")'), ctx)

    def test_blocked_compile(self, ctx):
        with pytest.raises(EvalError):
            eval_node(Evaluable('compile("1+1", "", "eval")'), ctx)

    def test_blocked_globals(self, ctx):
        with pytest.raises(EvalError):
            eval_node(Evaluable("globals()"), ctx)

    def test_blocked_locals(self, ctx):
        with pytest.raises(EvalError):
            eval_node(Evaluable("locals()"), ctx)


# =============================================================================
# BIO INTEGRATION TESTS (M1.8j)
# =============================================================================

class TestBioIntegration:
    """Test bio.load_spec() and bio.eval_spec() integration."""

    def test_load_spec_from_file(self, temp_dir):
        """bio.load_spec() loads and hydrates a YAML file."""
        from alienbio.spec_lang import bio

        spec_file = temp_dir / "index.yaml"
        spec_file.write_text("""
name: test
count: !ev normal(50, 10)
rate: !_ k * S
threshold: !ref high_threshold
""")

        spec = bio.load_spec(str(spec_file))

        # Should have placeholders, not evaluated values
        assert spec["name"] == "test"
        assert isinstance(spec["count"], Evaluable)
        assert spec["count"].source == "normal(50, 10)"
        assert isinstance(spec["rate"], Quoted)
        assert spec["rate"].source == "k * S"
        assert isinstance(spec["threshold"], Reference)
        assert spec["threshold"].name == "high_threshold"

    def test_eval_spec_evaluates_placeholders(self, temp_dir):
        """bio.eval_spec() evaluates all placeholders."""
        from alienbio.spec_lang import bio

        spec_file = temp_dir / "index.yaml"
        spec_file.write_text("""
name: test
count: !ev normal(50, 10)
rate: !_ k * S
value: !ev 2 + 3
""")

        spec = bio.load_spec(str(spec_file))
        result = bio.eval_spec(spec, seed=42)

        assert result["name"] == "test"
        assert isinstance(result["count"], (int, float))  # evaluated to number
        assert result["rate"] == "k * S"  # !_ preserved as string
        assert result["value"] == 5  # evaluated

    def test_eval_spec_with_bindings(self, temp_dir):
        """bio.eval_spec() resolves references from bindings."""
        from alienbio.spec_lang import bio

        spec_file = temp_dir / "index.yaml"
        spec_file.write_text("""
threshold: !ref high_value
computed: !ev base * 2
""")

        spec = bio.load_spec(str(spec_file))
        result = bio.eval_spec(spec, bindings={"high_value": 100, "base": 10})

        assert result["threshold"] == 100
        assert result["computed"] == 20

    def test_eval_spec_reproducible_with_seed(self, temp_dir):
        """Same seed produces same random results."""
        from alienbio.spec_lang import bio

        spec_file = temp_dir / "index.yaml"
        spec_file.write_text("""
count: !ev normal(50, 10)
value: !ev uniform(0, 1)
""")

        spec = bio.load_spec(str(spec_file))

        result1 = bio.eval_spec(spec, seed=42)
        result2 = bio.eval_spec(spec, seed=42)

        assert result1["count"] == result2["count"]
        assert result1["value"] == result2["value"]

    def test_eval_spec_different_seeds_different_results(self, temp_dir):
        """Different seeds produce different random results."""
        from alienbio.spec_lang import bio

        spec_file = temp_dir / "index.yaml"
        spec_file.write_text("""
count: !ev normal(50, 10)
""")

        spec = bio.load_spec(str(spec_file))

        results = [bio.eval_spec(spec, seed=i)["count"] for i in range(10)]

        # Not all results should be the same
        assert len(set(results)) > 1

    def test_load_spec_with_include(self, temp_dir):
        """bio.load_spec() resolves includes."""
        from alienbio.spec_lang import bio

        # Create included file
        included_file = temp_dir / "config.yaml"
        included_file.write_text("""
timeout: 30
retries: 3
""")

        # Create main spec
        spec_file = temp_dir / "index.yaml"
        spec_file.write_text("""
name: test
config: !include config.yaml
""")

        spec = bio.load_spec(str(spec_file))

        assert spec["name"] == "test"
        assert spec["config"]["timeout"] == 30
        assert spec["config"]["retries"] == 3

    def test_load_spec_directory(self, temp_dir):
        """bio.load_spec() loads index.yaml from directory."""
        from alienbio.spec_lang import bio

        spec_file = temp_dir / "index.yaml"
        spec_file.write_text("""
name: test
value: 42
""")

        spec = bio.load_spec(str(temp_dir))

        assert spec["name"] == "test"
        assert spec["value"] == 42

    def test_load_spec_file_not_found(self, temp_dir):
        """bio.load_spec() raises FileNotFoundError for missing file."""
        from alienbio.spec_lang import bio

        with pytest.raises(FileNotFoundError):
            bio.load_spec(str(temp_dir / "nonexistent"))

    def test_multiple_instantiations_from_same_spec(self, temp_dir):
        """Same spec can be evaluated multiple times with different seeds."""
        from alienbio.spec_lang import bio

        spec_file = temp_dir / "index.yaml"
        spec_file.write_text("""
count: !ev normal(50, 10)
""")

        spec = bio.load_spec(str(spec_file))

        # Spec should still have placeholders after evaluation
        results = []
        for seed in range(5):
            result = bio.eval_spec(spec, seed=seed)
            results.append(result["count"])
            # Original spec unchanged
            assert isinstance(spec["count"], Evaluable)

        # Different seeds give different results
        assert len(set(results)) > 1
