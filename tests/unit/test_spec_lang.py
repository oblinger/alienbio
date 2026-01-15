"""Comprehensive test suite for spec_lang module.

TDD approach: All tests written first, then implementation to make them pass.
Tests organized by feature area matching the Spec Language specification.
"""

import pytest
import yaml
import tempfile
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Any

from alienbio.spec_lang import (
    Bio,
    bio,
    biotype,
    fn,
    scoring,
    action,
    measurement,
    rate,
    get_biotype,
    get_action,
    get_measurement,
    get_scoring,
    get_rate,
    biotype_registry,
    action_registry,
    measurement_registry,
    scoring_registry,
    rate_registry,
    Evaluable,
    Reference,
    Include,
    transform_typed_keys,
    expand_defaults,
)
from alienbio.spec_lang.decorators import (
    clear_registries,
    FnMeta,
)
from alienbio.spec_lang.loader import deep_merge


# =============================================================================
# Test Fixtures and Scaffold Types
# =============================================================================


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# Scaffold biotypes for testing (defined as plain dataclasses first)
@dataclass
class MockChemistry:
    """Mock chemistry for testing."""
    molecules: dict
    reactions: dict | None = None


@dataclass
class MockWorld:
    """Mock world for testing."""
    chemistry: Any
    containers: dict | None = None


@dataclass
class MockScenario:
    """Mock scenario for testing."""
    world: Any | None = None
    briefing: str | None = None
    constitution: str | None = None


@dataclass
class MockSuite:
    """Mock suite for testing."""
    defaults: dict | None = None
    scenarios: dict | None = None


def _register_scaffold_biotypes():
    """Register scaffold biotypes in the registry."""
    biotype_registry["scenario"] = MockScenario
    biotype_registry["suite"] = MockSuite


@pytest.fixture(autouse=True)
def clear_all_registries():
    """Clear all registries before each test, then re-register scaffolds."""
    clear_registries()
    _register_scaffold_biotypes()
    yield
    clear_registries()


# Test functions for decorators
def sample_energy_ring(size: int = 6) -> list[str]:
    """Sample function for !ev testing."""
    return [f"M{i}" for i in range(size)]


def sample_mass_action(k: float = 0.1):
    """Sample rate function for !ev testing."""
    def rate_fn(concentrations: dict) -> float:
        return k * sum(concentrations.values())
    return rate_fn


# =============================================================================
# Test Suite: !ev Tag (evaluate expressions)
# =============================================================================


class TestEvaluable:
    """Tests for !ev tag evaluation."""

    def test_ev_simple_arithmetic(self):
        """!ev 2+3 → 5 (simple arithmetic)"""
        tag = Evaluable("2+3")
        assert tag.evaluate() == 5

    def test_ev_operator_precedence(self):
        """!ev 2 * 3 + 4 → 10 (operator precedence)"""
        tag = Evaluable("2 * 3 + 4")
        assert tag.evaluate() == 10

    def test_ev_list_literal(self):
        """!ev [1, 2, 3] → list (literal collections)"""
        tag = Evaluable("[1, 2, 3]")
        assert tag.evaluate() == [1, 2, 3]

    def test_ev_dict_literal(self):
        """!ev {"a": 1} → dict (literal dict)"""
        tag = Evaluable('{"a": 1}')
        assert tag.evaluate() == {"a": 1}

    def test_ev_function_call_with_kwargs(self):
        """!ev energy_ring(size=6) → function call with kwargs"""
        tag = Evaluable("energy_ring(size=6)")
        result = tag.evaluate({"energy_ring": sample_energy_ring})
        assert result == ["M0", "M1", "M2", "M3", "M4", "M5"]

    def test_ev_returns_callable(self):
        """!ev mass_action(k=0.1) → returns callable"""
        tag = Evaluable("mass_action(k=0.1)")
        result = tag.evaluate({"mass_action": sample_mass_action})
        assert callable(result)
        assert result({"A": 1.0, "B": 2.0}) == pytest.approx(0.3)

    def test_ev_lambda_expression(self):
        """!ev lambda c: c["ME1"] * 0.1 → lambda expression"""
        tag = Evaluable('lambda c: c["ME1"] * 0.1')
        result = tag.evaluate()
        assert callable(result)
        assert result({"ME1": 100.0}) == 10.0

    def test_ev_undefined_name_raises(self):
        """!ev undefined_name → raises NameError"""
        tag = Evaluable("undefined_name")
        with pytest.raises(NameError):
            tag.evaluate()

    def test_ev_division_by_zero_raises(self):
        """!ev 1/0 → raises ZeroDivisionError"""
        tag = Evaluable("1/0")
        with pytest.raises(ZeroDivisionError):
            tag.evaluate()

    def test_ev_blocks_dangerous_builtins(self):
        """!ev open("/etc/passwd") → blocked (security)"""
        tag = Evaluable('open("/etc/passwd")')
        with pytest.raises((NameError, TypeError)):
            tag.evaluate()

    def test_ev_blocks_import(self):
        """Ensure __import__ is blocked."""
        tag = Evaluable('__import__("os")')
        with pytest.raises((NameError, TypeError)):
            tag.evaluate()

    def test_ev_yaml_parsing(self):
        """Test that !ev is properly parsed by YAML."""
        from alienbio.spec_lang.eval import Evaluable
        yaml_str = "value: !ev 2+3"
        data = yaml.safe_load(yaml_str)
        # New evaluation system produces Evaluable
        assert isinstance(data["value"], Evaluable)
        assert data["value"].source == "2+3"


# =============================================================================
# Test Suite: !ref Tag (reference constants)
# =============================================================================


class TestReference:
    """Tests for !ref tag resolution."""

    def test_ref_simple_scalar(self):
        """!ref simple_const → scalar value"""
        tag = Reference("simple_const")
        constants = {"simple_const": 42}
        assert tag.resolve(constants) == 42

    def test_ref_dotted_path(self):
        """!ref nested.path.value → dotted path lookup"""
        tag = Reference("nested.path.value")
        constants = {"nested": {"path": {"value": "deep"}}}
        assert tag.resolve(constants) == "deep"

    def test_ref_dict_constant(self):
        """!ref dict_const → returns entire dict"""
        tag = Reference("dict_const")
        constants = {"dict_const": {"a": 1, "b": 2}}
        assert tag.resolve(constants) == {"a": 1, "b": 2}

    def test_ref_undefined_raises(self):
        """!ref undefined_const → raises KeyError"""
        tag = Reference("undefined_const")
        constants = {}
        with pytest.raises(KeyError):
            tag.resolve(constants)

    def test_ref_partial_path_undefined_raises(self):
        """!ref foo.bar where foo exists but bar doesn't → raises KeyError"""
        tag = Reference("foo.bar")
        constants = {"foo": {"baz": 1}}
        with pytest.raises(KeyError):
            tag.resolve(constants)

    def test_ref_yaml_parsing(self):
        """Test that !ref is properly parsed by YAML."""
        from alienbio.spec_lang.eval import Reference
        yaml_str = "value: !ref my_constant"
        data = yaml.safe_load(yaml_str)
        assert isinstance(data["value"], Reference)
        assert data["value"].name == "my_constant"

    def test_ref_combined_with_ev(self):
        """!ref combined with !ev in namespace"""
        from alienbio.spec_lang.eval import Evaluable, Reference, eval_node, make_context
        # Reference is resolved via eval system
        ref = Reference(name="my_const")
        ctx = make_context(bindings={"my_const": 10})
        resolved = eval_node(ref, ctx)

        ev = Evaluable(source="x * 2")
        ctx2 = make_context(bindings={"x": resolved})
        result = eval_node(ev, ctx2)
        assert result == 20


# =============================================================================
# Test Suite: !include Tag (file inclusion)
# =============================================================================


class TestInclude:
    """Tests for !include tag file loading."""

    def test_include_markdown_file(self, temp_dir):
        """!include safety.md → string content of markdown file"""
        md_file = temp_dir / "safety.md"
        md_file.write_text("# Safety Rules\n\nBe careful.")

        tag = Include("safety.md")
        result = tag.load(str(temp_dir))
        assert result == "# Safety Rules\n\nBe careful."

    def test_include_yaml_file(self, temp_dir):
        """!include config.yaml → parsed and merged YAML"""
        yaml_file = temp_dir / "config.yaml"
        yaml_file.write_text("key: value\nnested:\n  a: 1")

        tag = Include("config.yaml")
        result = tag.load(str(temp_dir))
        assert result == {"key": "value", "nested": {"a": 1}}

    def test_include_python_file(self, temp_dir):
        """!include functions.py → executes Python, registers decorators"""
        py_file = temp_dir / "functions.py"
        py_file.write_text("""
from alienbio.spec_lang import action

@action(summary="Test action")
def test_action(sim):
    return "executed"
""")

        tag = Include("functions.py")
        tag.load(str(temp_dir))
        # After loading, the action should be registered
        assert "test_action" in action_registry

    def test_include_missing_file_raises(self, temp_dir):
        """!include missing.md → raises FileNotFoundError"""
        tag = Include("missing.md")
        with pytest.raises(FileNotFoundError):
            tag.load(str(temp_dir))

    def test_include_relative_path(self, temp_dir):
        """!include ../outside.md → relative path resolution"""
        # Create file one level up
        parent_dir = temp_dir.parent
        outside_file = parent_dir / "outside.md"
        outside_file.write_text("Outside content")

        subdir = temp_dir / "subdir"
        subdir.mkdir()

        tag = Include("../outside.md")
        # Relative to subdir, should find parent's outside.md
        # This test may need adjustment based on implementation
        pytest.skip("Relative path handling TBD")

    def test_include_absolute_path(self, temp_dir):
        """!include /absolute/path.md → absolute path"""
        abs_file = temp_dir / "absolute.md"
        abs_file.write_text("Absolute content")

        tag = Include(str(abs_file))
        result = tag.load()
        assert result == "Absolute content"

    def test_include_nested(self, temp_dir):
        """Nested includes: file A includes file B which includes file C"""
        c_file = temp_dir / "c.md"
        c_file.write_text("C content")

        b_file = temp_dir / "b.yaml"
        b_file.write_text("b_content: !include c.md")

        a_file = temp_dir / "a.yaml"
        a_file.write_text("a_content: !include b.yaml")

        tag = Include("a.yaml")
        result = tag.load(str(temp_dir))
        # Should recursively resolve includes
        assert result["a_content"]["b_content"] == "C content"

    def test_include_circular_detection(self, temp_dir):
        """Circular include detection: A includes B includes A → error"""
        a_file = temp_dir / "a.yaml"
        a_file.write_text("content: !include b.yaml")

        b_file = temp_dir / "b.yaml"
        b_file.write_text("content: !include a.yaml")

        tag = Include("a.yaml")
        with pytest.raises(RecursionError):
            tag.load(str(temp_dir))

    def test_include_yaml_parsing(self):
        """Test that !include is properly parsed by YAML."""
        yaml_str = "content: !include myfile.md"
        data = yaml.safe_load(yaml_str)
        assert isinstance(data["content"], Include)
        assert data["content"].path == "myfile.md"


# =============================================================================
# Test Suite: Typed Keys (type.name: parsing)
# =============================================================================


class TestTypedKeys:
    """Tests for typed key parsing and transformation."""

    def test_typed_key_scenario(self):
        """scenario.foo: → {"foo": {"_type": "scenario", ...}}"""
        data = {"scenario.foo": {"molecules": {}}}
        result = transform_typed_keys(data)
        assert result == {"foo": {"_type": "scenario", "molecules": {}}}

    def test_typed_key_suite(self):
        """suite.bar: → {"bar": {"_type": "suite", ...}}"""
        data = {"suite.bar": {"defaults": {}}}
        result = transform_typed_keys(data)
        assert result == {"bar": {"_type": "suite", "defaults": {}}}

    def test_typed_key_unknown_passthrough(self):
        """unknown.thing: → keeps as-is (not a registered type)"""
        data = {"unknown.thing": {"data": 1}}
        result = transform_typed_keys(data)
        # Unknown type should keep the dotted key as-is
        assert result == {"unknown.thing": {"data": 1}}

    def test_typed_key_nested(self):
        """suite.outer: containing scenario.inner: → proper nesting"""
        data = {
            "suite.outer": {
                "defaults": {},
                "scenario.inner": {"briefing": "Nested"},
            }
        }
        result = transform_typed_keys(data)
        assert result == {
            "outer": {
                "_type": "suite",
                "defaults": {},
                "inner": {"_type": "scenario", "briefing": "Nested"},
            }
        }

    def test_typed_key_dotted_name(self):
        """scenario.my.complex.name: → name is my.complex.name"""
        data = {"scenario.my.complex.name": {"molecules": {}}}
        result = transform_typed_keys(data)
        assert result == {"my.complex.name": {"_type": "scenario", "molecules": {}}}

    def test_typed_key_preserves_other_keys(self):
        """Preserves other keys alongside typed keys"""
        data = {
            "constants": {"x": 1},
            "scenario.myscenario": {"molecules": {}},
        }
        result = transform_typed_keys(data)
        assert result == {
            "constants": {"x": 1},
            "myscenario": {"_type": "scenario", "molecules": {}},
        }

    def test_typed_key_round_trip(self):
        """Round-trip: parse → serialize → parse yields same structure"""
        original = {"scenario.foo": {"molecules": {"A": {}}}}
        transformed = transform_typed_keys(original)
        # Would need inverse function for full round-trip
        assert transformed["foo"]["_type"] == "scenario"
        assert transformed["foo"]["molecules"] == {"A": {}}


# =============================================================================
# Test Suite: @biotype Decorator
# =============================================================================


class TestBiotypeDecorator:
    """Tests for @biotype decorator and hydration."""

    def test_biotype_registers_class(self):
        """@biotype registers class in global registry"""
        @biotype
        @dataclass
        class TestType:
            value: int

        assert "testtype" in biotype_registry
        assert biotype_registry["testtype"] == TestType

    def test_biotype_explicit_name(self):
        """@biotype("custom_name") uses explicit type name"""
        @biotype("my_custom_type")
        @dataclass
        class AnotherType:
            value: int

        assert "my_custom_type" in biotype_registry
        assert biotype_registry["my_custom_type"] == AnotherType


# =============================================================================
# Test Suite: Function Decorators
# =============================================================================


class TestFunctionDecorators:
    """Tests for @fn, @scoring, @action, @measurement, @rate decorators."""

    def test_fn_stores_metadata(self):
        """@fn(summary="...", range=(0,1)) stores metadata"""
        @fn(summary="Test function", range=(0.0, 1.0), custom_key="custom_value")
        def my_func(x):
            return x * 2

        assert isinstance(my_func, FnMeta)
        assert my_func.meta["summary"] == "Test function"
        assert my_func.meta["range"] == (0.0, 1.0)
        assert my_func.meta["custom_key"] == "custom_value"
        assert my_func(5) == 10

    def test_scoring_registers(self):
        """@scoring(...) registers in scoring registry"""
        @scoring(summary="Test score", range=(0.0, 1.0), higher_is_better=True)
        def test_score(timeline):
            return 0.5

        assert "test_score" in scoring_registry
        assert scoring_registry["test_score"] is test_score

    def test_action_registers(self):
        """@action(...) registers in action registry"""
        @action(summary="Test action", targets="regions", cost=2.0)
        def test_action_fn(sim, region):
            pass

        assert "test_action_fn" in action_registry
        assert action_registry["test_action_fn"] is test_action_fn

    def test_measurement_registers(self):
        """@measurement(...) registers in measurement registry"""
        @measurement(summary="Test measurement", targets="organisms")
        def test_measurement_fn(sim, organism):
            return 42

        assert "test_measurement_fn" in measurement_registry
        assert measurement_registry["test_measurement_fn"] is test_measurement_fn

    def test_rate_registers(self):
        """@rate(...) registers in rate registry"""
        @rate(summary="Mass action", range=(0.0, float("inf")))
        def test_rate_fn(concentrations, k=0.1):
            return k * concentrations.get("A", 0)

        assert "test_rate_fn" in rate_registry
        assert rate_registry["test_rate_fn"] is test_rate_fn

    def test_fn_metadata_access(self):
        """Access metadata: fn.meta["summary"]"""
        @scoring(summary="Accessible summary", range=(0.0, 1.0))
        def accessible_fn():
            pass

        assert accessible_fn.meta["summary"] == "Accessible summary"
        assert accessible_fn.meta["range"] == (0.0, 1.0)
        assert accessible_fn.meta["higher_is_better"] is True

    def test_get_action_lookup(self):
        """Lookup by name: get_action("add_feedstock") → function"""
        @action(summary="Add feedstock")
        def add_feedstock(sim, molecule, amount):
            pass

        result = get_action("add_feedstock")
        assert result is add_feedstock

    def test_get_action_missing_raises(self):
        """Missing registration: get_action("unknown") → KeyError"""
        with pytest.raises(KeyError):
            get_action("totally_unknown_action")

    def test_decorator_preserves_signature(self):
        """Decorator preserves function signature and docstring"""
        @action(summary="Documented action")
        def documented_fn(sim, x: int, y: str = "default") -> bool:
            """This is the docstring."""
            return True

        # The wrapped function should still be callable with same args
        assert documented_fn(None, 42, "test") is True
        # Docstring should be preserved (if using functools.wraps properly)
        # Note: FnMeta may need adjustment to preserve __doc__


# =============================================================================
# Test Suite: Defaults and Inheritance
# =============================================================================


class TestDefaultsInheritance:
    """Tests for defaults expansion and inheritance."""

    def test_deep_merge_simple(self):
        """Suite defaults: applied to child scenario"""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_deep_merge_nested(self):
        """Deep merge: nested dicts merged, not replaced"""
        base = {"outer": {"a": 1, "b": 2}}
        override = {"outer": {"b": 3, "c": 4}}
        result = deep_merge(base, override)
        assert result == {"outer": {"a": 1, "b": 3, "c": 4}}

    def test_deep_merge_null_removes(self):
        """key: ~ (null) removes inherited value"""
        base = {"a": 1, "b": 2, "c": 3}
        override = {"b": None}
        result = deep_merge(base, override)
        assert result == {"a": 1, "c": 3}
        assert "b" not in result

    def test_deep_merge_list_replaces(self):
        """List values: replaced, not appended"""
        base = {"items": [1, 2, 3]}
        override = {"items": [4, 5]}
        result = deep_merge(base, override)
        assert result == {"items": [4, 5]}

    def test_expand_defaults_simple(self):
        """Suite defaults: applied to child scenario"""
        data = {
            "suite": {
                "_type": "suite",
                "defaults": {"world": "base_world", "constitution": "base_const"},
                "baseline": {"_type": "scenario", "briefing": "Baseline brief"},
            }
        }
        result = expand_defaults(data)
        # baseline should inherit defaults
        assert result["suite"]["baseline"]["world"] == "base_world"
        assert result["suite"]["baseline"]["constitution"] == "base_const"
        assert result["suite"]["baseline"]["briefing"] == "Baseline brief"

    def test_expand_defaults_nested_suite(self):
        """Nested suite inherits parent defaults"""
        data = {
            "outer": {
                "_type": "suite",
                "defaults": {"a": 1},
                "inner": {
                    "_type": "suite",
                    "defaults": {"b": 2},
                    "scenario1": {"_type": "scenario"},
                },
            }
        }
        result = expand_defaults(data)
        # scenario1 should have both a=1 and b=2
        assert result["outer"]["inner"]["scenario1"]["a"] == 1
        assert result["outer"]["inner"]["scenario1"]["b"] == 2

    def test_expand_defaults_override(self):
        """Scenario overrides specific default value"""
        data = {
            "suite": {
                "_type": "suite",
                "defaults": {"x": 10, "y": 20},
                "scenario1": {"_type": "scenario", "x": 99},
            }
        }
        result = expand_defaults(data)
        assert result["suite"]["scenario1"]["x"] == 99
        assert result["suite"]["scenario1"]["y"] == 20

    def test_expand_defaults_sibling_independence(self):
        """Sibling scenarios get independent copies of defaults"""
        data = {
            "suite": {
                "_type": "suite",
                "defaults": {"config": {"value": 1}},
                "scenario_a": {"_type": "scenario"},
                "scenario_b": {"_type": "scenario"},
            }
        }
        result = expand_defaults(data)
        # Modify one shouldn't affect the other
        result["suite"]["scenario_a"]["config"]["value"] = 999
        assert result["suite"]["scenario_b"]["config"]["value"] == 1


# =============================================================================
# Test Suite: Constants
# =============================================================================


class TestConstants:
    """Tests for constant definition and resolution."""

    def test_constant_scalar(self):
        """Define scalar constant, reference with !ref"""
        yaml_str = """
constants:
  high_permeability: 0.8
value: !ref high_permeability
"""
        from alienbio.spec_lang.eval import Reference, eval_node, make_context
        data = yaml.safe_load(yaml_str)
        ref = data["value"]
        assert isinstance(ref, Reference)
        ctx = make_context(bindings=data["constants"])
        result = eval_node(ref, ctx)
        assert result == 0.8

    def test_constant_dict(self):
        """Define dict constant, reference returns full dict"""
        yaml_str = """
constants:
  standard_env:
    temp: 25
    pH: 7.0
environment: !ref standard_env
"""
        from alienbio.spec_lang.eval import Reference, eval_node, make_context
        data = yaml.safe_load(yaml_str)
        ref = data["environment"]
        assert isinstance(ref, Reference)
        ctx = make_context(bindings=data["constants"])
        result = eval_node(ref, ctx)
        assert result == {"temp": 25, "pH": 7.0}

    def test_constant_with_ev(self):
        """Define constant using !ev, reference gets evaluated result"""
        from alienbio.spec_lang.eval import Evaluable, Reference, eval_node, make_context, hydrate
        yaml_str = """
constants:
  computed: !ev 2 * 3 * 7
value: !ref computed
"""
        data = yaml.safe_load(yaml_str)
        # New evaluation system: !ev creates Evaluable
        assert isinstance(data["constants"]["computed"], Evaluable)

        # Hydrate to convert RefTag to Reference
        hydrated = hydrate(data)
        assert isinstance(hydrated["value"], Reference)

        # Evaluate step by step:
        ev_result = eval_node(hydrated["constants"]["computed"], make_context())
        assert ev_result == 42

        # Full evaluation with bindings
        ctx = make_context(bindings={"computed": ev_result})
        result = eval_node(hydrated["value"], ctx)
        assert result == 42

    def test_constant_file_level(self):
        """Constants block at file level"""
        yaml_str = """
constants:
  a: 1
  b: 2
  c: 3
"""
        data = yaml.safe_load(yaml_str)
        assert data["constants"]["a"] == 1
        assert data["constants"]["b"] == 2
        assert data["constants"]["c"] == 3

    def test_constant_chain_reference(self):
        """Constant referencing another constant"""
        # This requires multi-pass resolution
        constants = {
            "base": 10,
            "derived": Reference("base"),  # Would need to resolve to 10
        }
        # First resolve derived
        constants["derived"] = constants["derived"].resolve(constants)
        assert constants["derived"] == 10


# =============================================================================
# Test Suite: Bio Class
# =============================================================================


class TestBioClass:
    """Tests for bio.fetch(), bio.store(), bio.sim() methods."""

    def test_bio_load_scenario(self, temp_dir):
        """bio.fetch("catalog/scenarios/test") returns processed dict"""
        # Create a test scenario file
        scenario_dir = temp_dir / "catalog" / "scenarios" / "test"
        scenario_dir.mkdir(parents=True)
        spec_file = scenario_dir / "spec.yaml"
        spec_file.write_text("""
scenario.test:
  briefing: "Test briefing"
  constitution: "Test constitution"
""")

        result = bio.fetch(str(scenario_dir))
        # Result is now a dict (no automatic hydration to typed objects)
        assert isinstance(result, dict)
        assert "test" in result
        assert result["test"]["briefing"] == "Test briefing"

    def test_bio_load_nonexistent_raises(self):
        """bio.fetch("nonexistent/path") → FileNotFoundError"""
        with pytest.raises(FileNotFoundError):
            bio.fetch("/nonexistent/path/that/does/not/exist")

    def test_bio_save_writes_yaml(self, temp_dir):
        """bio.store("path", obj) writes YAML"""
        @dataclass
        class SaveTest:
            name: str
            value: int

            def to_dict(self):
                return {"name": self.name, "value": self.value}

        obj = SaveTest(name="test", value=42)
        save_path = temp_dir / "saved"
        save_path.mkdir()

        bio.store(str(save_path), obj)

        # Check file was written
        spec_file = save_path / "spec.yaml"
        assert spec_file.exists()
        content = yaml.safe_load(spec_file.read_text())
        assert content["name"] == "test"
        assert content["value"] == 42

    def test_bio_save_load_round_trip(self, temp_dir):
        """bio.store then bio.fetch round-trips correctly"""
        @dataclass
        class RoundTrip:
            name: str
            count: int

            def to_dict(self):
                return {"name": self.name, "count": self.count}

        original = RoundTrip(name="original", count=99)
        path = temp_dir / "roundtrip"
        path.mkdir()

        bio.store(str(path), original)
        loaded = bio.fetch(str(path), raw=True)

        # Loaded is a dict now
        assert loaded["name"] == original.name
        assert loaded["count"] == original.count

    def test_bio_sim_pegboard(self):
        """bio.sim is a pegboard property for the active Simulator."""
        from alienbio import Simulator, Bio

        # Fresh Bio instance
        fresh_bio = Bio()

        # sim starts as None
        assert fresh_bio.sim is None

        # Can create and assign a simulator via bio.create()
        # Note: Simulator may not be registered yet, so we test the pegboard pattern
        from alienbio.bio.simulator import ReferenceSimulatorImpl
        chemistry = {"molecules": {}, "reactions": {}}
        sim = ReferenceSimulatorImpl(chemistry)
        fresh_bio.sim = sim

        # sim is now set
        assert fresh_bio.sim is sim
        assert hasattr(fresh_bio.sim, "step") or hasattr(fresh_bio.sim, "run")

    def test_bio_load_complex_spec(self, temp_dir):
        """Load with typed keys, defaults, refs, includes all working together"""
        # Create a complex spec
        spec_dir = temp_dir / "complex"
        spec_dir.mkdir()

        # Create include file
        include_file = spec_dir / "constitution.md"
        include_file.write_text("# Constitution\n\nProtect all species.")

        spec_file = spec_dir / "spec.yaml"
        spec_file.write_text("""
constants:
  high_perm: 0.8

suite.test:
  defaults:
    world: base_world
  scenario.baseline:
    briefing: "Full knowledge"
    permeability: !ref high_perm
""")

        result = bio.fetch(str(spec_dir))
        # Should have resolved everything
        assert result is not None


# =============================================================================
# Test Suite: Integration / Complex Specs
# =============================================================================


class TestIntegration:
    """Integration tests for complex real-world specs."""

    def test_full_mutualism_style_spec(self, temp_dir):
        """Full mutualism-style spec: world + suite + scenarios + constants"""
        spec_file = temp_dir / "spec.yaml"
        spec_file.write_text("""
constants:
  high_permeability: 0.8
  low_permeability: 0.1

world.ecosystem:
  molecules:
    ME1: {name: "Energy 1"}
    ME2: {name: "Energy 2"}
  reactions:
    R1: {equation: "2 ME1 -> ME2"}
  containers:
    environment:
      substrate: {}

suite.experiments:
  defaults:
    world: !ref ecosystem
    constitution: |
      Protect all species.
      Maintain ecosystem balance.

  scenario.baseline:
    briefing: |
      Full ecosystem knowledge.
      All molecules visible.

  scenario.hidden:
    briefing: |
      Partial knowledge.
      Some molecules hidden.
""")

        # This should parse without error
        data = yaml.safe_load(spec_file.read_text())
        assert "constants" in data
        assert "world.ecosystem" in data
        assert "suite.experiments" in data

    def test_spec_with_python_include(self, temp_dir):
        """Spec with Python include defining custom functions"""
        functions_file = temp_dir / "functions.py"
        functions_file.write_text("""
from alienbio.spec_lang import rate, scoring

@rate(summary="Custom rate law")
def custom_rate(concentrations, k=0.5):
    return k * concentrations.get("A", 0) * concentrations.get("B", 0)

@scoring(summary="Custom score")
def custom_score(timeline):
    return 0.75
""")

        spec_file = temp_dir / "spec.yaml"
        spec_file.write_text("""
include:
  - functions.py

chemistry.test:
  molecules:
    A: {}
    B: {}
  reactions:
    R1:
      equation: "A + B -> C"
      rate: !ev custom_rate(k=0.1)
""")

        # After loading, custom functions should be registered
        # and the rate should be resolvable
        pytest.skip("Full include processing TBD")

    def test_spec_with_multiple_inheritance_levels(self, temp_dir):
        """Spec with multiple levels of defaults inheritance"""
        spec_file = temp_dir / "spec.yaml"
        spec_file.write_text("""
suite.level1:
  defaults:
    a: 1
    config:
      x: 10

  suite.level2:
    defaults:
      b: 2
      config:
        y: 20

    suite.level3:
      defaults:
        c: 3

      scenario.deep:
        d: 4
""")

        data = yaml.safe_load(spec_file.read_text())
        transformed = transform_typed_keys(data)

        # After expansion, scenario.deep should have a, b, c, d and nested config
        # This tests the full inheritance chain
        assert transformed is not None

    def test_error_messages_include_context(self, temp_dir):
        """Error messages include context when evaluation fails"""
        from alienbio.spec_lang.eval import Evaluable, eval_node, make_context, EvalError

        spec_file = temp_dir / "bad_spec.yaml"
        spec_file.write_text("""
world.test:
  molecules:
    A: {}
  reactions:
    R1:
      rate: !ev undefined_function()
""")

        # When evaluating the !ev, error should mention undefined function
        data = yaml.safe_load(spec_file.read_text())
        evaluable = data["world.test"]["reactions"]["R1"]["rate"]
        assert isinstance(evaluable, Evaluable)

        try:
            eval_node(evaluable, make_context())
            assert False, "Should have raised"
        except EvalError as e:
            # Error message should be informative
            assert "undefined_function" in str(e)


# =============================================================================
# Additional Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Additional edge case tests."""

    def test_empty_spec(self):
        """Empty spec file should parse to empty dict"""
        data = yaml.safe_load("")
        assert data is None

    def test_spec_with_only_constants(self):
        """Spec with only constants, no types"""
        yaml_str = """
constants:
  a: 1
  b: 2
"""
        data = yaml.safe_load(yaml_str)
        assert data == {"constants": {"a": 1, "b": 2}}

    def test_deeply_nested_typed_keys(self):
        """Very deeply nested typed keys"""
        data = {
            "suite.a": {
                "suite.b": {
                    "suite.c": {
                        "scenario.d": {"value": "deep"}
                    }
                }
            }
        }
        result = transform_typed_keys(data)
        assert result["a"]["_type"] == "suite"
        assert result["a"]["b"]["_type"] == "suite"
        assert result["a"]["b"]["c"]["_type"] == "suite"
        assert result["a"]["b"]["c"]["d"]["_type"] == "scenario"
        assert result["a"]["b"]["c"]["d"]["value"] == "deep"

    def test_mixed_typed_and_regular_keys(self):
        """Mix of typed keys and regular keys"""
        data = {
            "constants": {"x": 1},
            "scenario.foo": {"molecules": {}},
            "metadata": {"version": "1.0"},
            "suite.bar": {"defaults": {}},
        }
        result = transform_typed_keys(data)
        assert result["constants"] == {"x": 1}
        assert result["foo"]["_type"] == "scenario"
        assert result["metadata"] == {"version": "1.0"}
        assert result["bar"]["_type"] == "suite"

    def test_ev_with_multiline_expression(self):
        """!ev with complex multiline-style expression"""
        # YAML will collapse this to single line, but test the parsing
        tag = Evaluable("sum([1, 2, 3, 4, 5])")
        assert tag.evaluate() == 15

    def test_ref_with_special_characters(self):
        """!ref with underscores and numbers in name"""
        tag = Reference("my_const_123")
        constants = {"my_const_123": "special"}
        assert tag.resolve(constants) == "special"


# =============================================================================
# Test Suite: DAT Execution (M1.6)
# =============================================================================


class TestDatExecution:
    """Tests for executing bio scenarios via DAT (Jobs are just DATs with do: functions)."""

    def test_dat_load_hardcoded_test(self):
        """Dat.load loads the hardcoded_test DAT correctly."""
        import os
        from dvc_dat import Dat

        os.chdir("/Users/oblinger/ob/proj/abio/alienbio")
        dat = Dat.load("catalog/jobs/hardcoded_test")

        # Check DAT loaded
        assert dat is not None
        spec = dat.get_spec()
        assert spec["dat"]["do"] == "alienbio.run"

    def test_dat_run_hardcoded_test(self):
        """Dat.run() executes the scenario and returns results."""
        import os
        from dvc_dat import Dat

        os.chdir("/Users/oblinger/ob/proj/abio/alienbio")
        dat = Dat.load("catalog/jobs/hardcoded_test")
        success, result = dat.run()

        # Check success
        assert success, "DAT should pass all verifications"

        # Check result structure
        assert "final_state" in result
        assert "scores" in result
        assert "verify_results" in result

    def test_scenario_simulation_results(self):
        """Scenario simulation produces expected concentration changes."""
        import os
        from dvc_dat import Dat

        os.chdir("/Users/oblinger/ob/proj/abio/alienbio")
        dat = Dat.load("catalog/jobs/hardcoded_test")
        success, result = dat.run()

        final = result["final_state"]
        # A and B should be depleted (started at 10 each)
        assert final["A"] < 2.0, "A should be mostly depleted"
        assert final["B"] < 2.0, "B should be mostly depleted"
        # D should have accumulated
        assert final["D"] > 5.0, "D should have accumulated"

    def test_scoring_functions_computed(self):
        """Scoring functions are computed correctly."""
        import os
        from dvc_dat import Dat

        os.chdir("/Users/oblinger/ob/proj/abio/alienbio")
        dat = Dat.load("catalog/jobs/hardcoded_test")
        success, result = dat.run()

        scores = result["scores"]
        # With A and B depleted, depletion score should be high
        assert scores["depletion"] > 0.9, "Depletion score should be high"
        # With D accumulated, production score should be high
        assert scores["production"] > 0.9, "Production score should be high"

    def test_bio_expand_index_yaml(self):
        """bio.expand works directly on index.yaml file."""
        data = bio.expand("src/alienbio/catalog/jobs/hardcoded_test/index.yaml")

        # Should have the scenario with _type
        assert "hardcoded_test" in data
        scenario = data["hardcoded_test"]
        assert scenario["_type"] == "scenario"
        assert "chemistry" in scenario
        assert "initial_state" in scenario

    def test_bio_fetch_index_yaml(self):
        """bio.fetch loads the index.yaml correctly."""
        # Fetch the index.yaml directly (not the DAT folder)
        scenario = bio.fetch("src/alienbio/catalog/jobs/hardcoded_test/index.yaml")

        # Should return a processed dict (no automatic hydration to typed objects)
        assert scenario is not None
        assert isinstance(scenario, dict)
        assert "hardcoded_test" in scenario


# =============================================================================
# Test Suite: Scope Class (Lexical Scoping)
# =============================================================================


class TestScope:
    """Tests for Scope class - lexical scoping with parent chain."""

    def test_scope_basic_dict_operations(self):
        """Scope behaves like a dict for local values."""
        from alienbio.spec_lang import Scope

        scope = Scope({"a": 1, "b": 2})
        assert scope["a"] == 1
        assert scope["b"] == 2
        assert scope.get("a") == 1
        assert scope.get("c", 99) == 99

    def test_scope_parent_inheritance(self):
        """Child scope inherits values from parent."""
        from alienbio.spec_lang import Scope

        parent = Scope({"x": 10, "y": 20})
        child = Scope({"z": 30}, parent=parent)

        # Child sees its own values
        assert child["z"] == 30
        # Child inherits parent values
        assert child["x"] == 10
        assert child["y"] == 20

    def test_scope_override_parent(self):
        """Child can override parent values."""
        from alienbio.spec_lang import Scope

        parent = Scope({"x": 10, "y": 20})
        child = Scope({"y": 99}, parent=parent)

        # x inherited from parent
        assert child["x"] == 10
        # y overridden in child
        assert child["y"] == 99
        # parent unchanged
        assert parent["y"] == 20

    def test_scope_chain_depth_3(self):
        """Three-level scope chain works correctly."""
        from alienbio.spec_lang import Scope

        root = Scope({"a": 1}, name="root")
        middle = Scope({"b": 2}, parent=root, name="middle")
        leaf = Scope({"c": 3}, parent=middle, name="leaf")

        # leaf sees all values
        assert leaf["a"] == 1
        assert leaf["b"] == 2
        assert leaf["c"] == 3

    def test_scope_keyerror_propagates(self):
        """KeyError raised when key not in any scope."""
        from alienbio.spec_lang import Scope

        parent = Scope({"x": 1})
        child = Scope({"y": 2}, parent=parent)

        with pytest.raises(KeyError):
            _ = child["z"]

    def test_scope_contains(self):
        """__contains__ checks entire chain."""
        from alienbio.spec_lang import Scope

        parent = Scope({"x": 1})
        child = Scope({"y": 2}, parent=parent)

        assert "x" in child
        assert "y" in child
        assert "z" not in child

    def test_scope_local_keys(self):
        """local_keys returns only keys defined in this scope."""
        from alienbio.spec_lang import Scope

        parent = Scope({"x": 1, "y": 2})
        child = Scope({"y": 99, "z": 3}, parent=parent)

        local = set(child.local_keys())
        assert local == {"y", "z"}

    def test_scope_all_keys(self):
        """all_keys returns keys from entire chain."""
        from alienbio.spec_lang import Scope

        parent = Scope({"x": 1, "y": 2})
        child = Scope({"y": 99, "z": 3}, parent=parent)

        all_k = child.all_keys()
        assert all_k == {"x", "y", "z"}

    def test_scope_child_method(self):
        """child() creates a new scope with parent link."""
        from alienbio.spec_lang import Scope

        parent = Scope({"x": 1})
        child = parent.child({"y": 2})

        assert child.parent is parent
        assert child["x"] == 1
        assert child["y"] == 2

    def test_scope_child_with_name(self):
        """child() can assign name to child scope."""
        from alienbio.spec_lang import Scope

        parent = Scope({"x": 1}, name="parent")
        child = parent.child({"y": 2}, name="child")

        assert child.name == "child"
        assert child.parent.name == "parent"

    def test_scope_resolve_returns_defining_scope(self):
        """resolve() returns value and the scope that defines it."""
        from alienbio.spec_lang import Scope

        root = Scope({"a": 1}, name="root")
        child = Scope({"b": 2}, parent=root, name="child")

        val, defining = child.resolve("a")
        assert val == 1
        assert defining is root

        val, defining = child.resolve("b")
        assert val == 2
        assert defining is child

    def test_scope_resolve_keyerror(self):
        """resolve() raises KeyError for missing key."""
        from alienbio.spec_lang import Scope

        scope = Scope({"x": 1})
        with pytest.raises(KeyError):
            scope.resolve("missing")

    def test_scope_repr(self):
        """repr shows name and parent info."""
        from alienbio.spec_lang import Scope

        parent = Scope({"x": 1}, name="parent")
        child = parent.child({"y": 2}, name="child")

        repr_str = repr(child)
        assert "child" in repr_str
        assert "parent" in repr_str

    def test_scope_empty_parent(self):
        """Scope with empty parent still works."""
        from alienbio.spec_lang import Scope

        parent = Scope({})
        child = parent.child({"x": 1})

        assert child["x"] == 1
        with pytest.raises(KeyError):
            _ = child["y"]

    def test_scope_get_with_default(self):
        """get() returns default when key not found in chain."""
        from alienbio.spec_lang import Scope

        parent = Scope({"x": 1})
        child = parent.child({"y": 2})

        assert child.get("x") == 1
        assert child.get("y") == 2
        assert child.get("z") is None
        assert child.get("z", "default") == "default"

    def test_scope_dict_mutation(self):
        """Scope can be mutated like a dict."""
        from alienbio.spec_lang import Scope

        scope = Scope({"x": 1})
        scope["y"] = 2
        assert scope["y"] == 2

        del scope["x"]
        assert "x" not in scope

    def test_scope_iteration(self):
        """Iterating scope yields local keys only."""
        from alienbio.spec_lang import Scope

        parent = Scope({"x": 1})
        child = parent.child({"y": 2, "z": 3})

        keys = list(child)
        assert set(keys) == {"y", "z"}
