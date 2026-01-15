"""Tests for globals module - M3.7.

Tests cover:
- Built-in defaults
- Dotted name access
- Scenario-level overrides
- Per-action overrides (via local)
- !ref resolution
"""

import pytest
import yaml

from alienbio.globals import (
    BUILTIN_DEFAULTS,
    Globals,
    create_globals_from_scenario,
    resolve_ref,
    resolve_refs_in_dict,
)


class TestBuiltinDefaults:
    """Tests for built-in default values."""

    def test_timing_defaults_exist(self):
        """Timing defaults are defined."""
        assert "action.timing.default_wait" in BUILTIN_DEFAULTS
        assert "action.timing.initiation_time" in BUILTIN_DEFAULTS
        assert "action.timing.default_duration" in BUILTIN_DEFAULTS

    def test_cost_defaults_exist(self):
        """Cost defaults are defined."""
        assert "action.cost.default_action" in BUILTIN_DEFAULTS
        assert "action.cost.default_measurement" in BUILTIN_DEFAULTS
        assert "action.cost.error" in BUILTIN_DEFAULTS

    def test_limits_defaults_exist(self):
        """Limit defaults are defined."""
        assert "action.limits.max_steps" in BUILTIN_DEFAULTS
        assert "action.limits.budget" in BUILTIN_DEFAULTS
        assert "action.limits.wall_clock_timeout" in BUILTIN_DEFAULTS

    def test_visibility_defaults_exist(self):
        """Visibility defaults are defined."""
        assert "action.visibility.molecules.fraction_known" in BUILTIN_DEFAULTS
        assert "action.visibility.reactions.fraction_known" in BUILTIN_DEFAULTS

    def test_default_wait_is_true(self):
        """Default wait is True (blocking behavior)."""
        assert BUILTIN_DEFAULTS["action.timing.default_wait"] is True

    def test_default_measurement_cost_is_zero(self):
        """Default measurement cost is 0."""
        assert BUILTIN_DEFAULTS["action.cost.default_measurement"] == 0.0


class TestGlobalsBasics:
    """Basic Globals functionality."""

    def test_creates_with_defaults(self):
        """Globals instance created with built-in defaults."""
        g = Globals()
        assert g.get("action.timing.default_wait") is True

    def test_get_nonexistent_returns_none(self):
        """get() returns None for unknown keys."""
        g = Globals()
        assert g.get("nonexistent.key") is None

    def test_get_nonexistent_with_default(self):
        """get() returns provided default for unknown keys."""
        g = Globals()
        assert g.get("nonexistent.key", "fallback") == "fallback"

    def test_has_for_existing_key(self):
        """has() returns True for existing keys."""
        g = Globals()
        assert g.has("action.timing.default_wait") is True

    def test_has_for_nonexistent_key(self):
        """has() returns False for unknown keys."""
        g = Globals()
        assert g.has("nonexistent.key") is False


class TestGlobalsOverrides:
    """Tests for override hierarchy."""

    def test_scenario_override_takes_precedence(self):
        """Scenario override beats built-in default."""
        g = Globals(scenario_overrides={"action.timing.default_wait": False})
        assert g.get("action.timing.default_wait") is False

    def test_local_override_takes_precedence_over_scenario(self):
        """Local override beats scenario override."""
        g = Globals(scenario_overrides={"action.cost.default_action": 5.0})
        g.set("action.cost.default_action", 10.0)
        assert g.get("action.cost.default_action") == 10.0

    def test_local_override_takes_precedence_over_default(self):
        """Local override beats built-in default."""
        g = Globals()
        g.set("action.timing.default_wait", False)
        assert g.get("action.timing.default_wait") is False

    def test_set_scenario_override(self):
        """set_scenario_override() adds scenario-level override."""
        g = Globals()
        g.set_scenario_override("action.cost.default_action", 3.0)
        assert g.get("action.cost.default_action") == 3.0

    def test_clear_local_removes_local_overrides(self):
        """clear_local() removes local overrides but keeps scenario."""
        g = Globals(scenario_overrides={"action.cost.default_action": 5.0})
        g.set("action.cost.default_action", 10.0)
        assert g.get("action.cost.default_action") == 10.0

        g.clear_local()
        assert g.get("action.cost.default_action") == 5.0


class TestGlobalsKeys:
    """Tests for key enumeration."""

    def test_all_keys_includes_defaults(self):
        """all_keys() includes built-in defaults."""
        g = Globals()
        keys = g.all_keys()
        assert "action.timing.default_wait" in keys

    def test_all_keys_includes_scenario(self):
        """all_keys() includes scenario overrides."""
        g = Globals(scenario_overrides={"custom.key": "value"})
        keys = g.all_keys()
        assert "custom.key" in keys

    def test_all_keys_includes_local(self):
        """all_keys() includes local overrides."""
        g = Globals()
        g.set("local.key", "value")
        keys = g.all_keys()
        assert "local.key" in keys

    def test_to_dict_merges_all_layers(self):
        """to_dict() returns merged dict with all values."""
        g = Globals(
            defaults={"a": 1, "b": 2},
            scenario_overrides={"b": 20, "c": 30}
        )
        g.set("c", 300)

        d = g.to_dict()
        assert d["a"] == 1
        assert d["b"] == 20
        assert d["c"] == 300


class TestCreateFromScenario:
    """Tests for create_globals_from_scenario()."""

    def test_creates_with_empty_scenario(self):
        """Works with scenario without globals section."""
        g = create_globals_from_scenario({})
        assert g.get("action.timing.default_wait") is True

    def test_creates_with_globals_section(self):
        """Applies globals section from scenario."""
        scenario = {
            "globals": {
                "action.timing.default_wait": False,
                "action.cost.default_action": 2.5
            }
        }
        g = create_globals_from_scenario(scenario)
        assert g.get("action.timing.default_wait") is False
        assert g.get("action.cost.default_action") == 2.5


class TestRefResolution:
    """Tests for !ref resolution."""

    def test_resolve_ref_returns_global_value(self):
        """resolve_ref() looks up value from globals."""
        g = Globals()
        ref = {"__ref__": "action.cost.default_action"}
        assert resolve_ref(ref, g) == 1.0

    def test_resolve_ref_returns_non_ref_unchanged(self):
        """resolve_ref() returns non-ref values unchanged."""
        g = Globals()
        assert resolve_ref(42, g) == 42
        assert resolve_ref("string", g) == "string"
        assert resolve_ref({"key": "value"}, g) == {"key": "value"}

    def test_resolve_ref_raises_for_unknown_key(self):
        """resolve_ref() raises ValueError for unknown reference."""
        g = Globals()
        ref = {"__ref__": "nonexistent.key"}
        with pytest.raises(ValueError, match="not found"):
            resolve_ref(ref, g)


class TestResolveRefsInDict:
    """Tests for recursive ref resolution."""

    def test_resolves_nested_refs(self):
        """resolve_refs_in_dict() resolves nested !ref values."""
        g = Globals()
        d = {
            "action": {
                "cost": {"__ref__": "action.cost.default_action"},
                "name": "test"
            }
        }
        resolved = resolve_refs_in_dict(d, g)
        assert resolved["action"]["cost"] == 1.0
        assert resolved["action"]["name"] == "test"

    def test_resolves_refs_in_lists(self):
        """resolve_refs_in_dict() handles refs in lists."""
        g = Globals()
        d = {
            "items": [
                {"cost": {"__ref__": "action.cost.default_action"}},
                {"cost": 5.0}
            ]
        }
        resolved = resolve_refs_in_dict(d, g)
        assert resolved["items"][0]["cost"] == 1.0
        assert resolved["items"][1]["cost"] == 5.0

    def test_preserves_non_ref_values(self):
        """resolve_refs_in_dict() preserves regular values."""
        g = Globals()
        d = {
            "string": "hello",
            "number": 42,
            "bool": True,
            "nested": {"inner": "value"}
        }
        resolved = resolve_refs_in_dict(d, g)
        assert resolved == d


class TestYamlRefTag:
    """Tests for !ref YAML tag support via spec_lang.eval."""

    def test_spec_lang_ref_tag_works(self):
        """spec_lang !ref tag creates Reference objects."""
        from alienbio.spec_lang.eval import Reference, register_eval_tags
        register_eval_tags()

        yaml_str = """
        action:
          cost: !ref action.cost.default_action
          name: test
        """
        data = yaml.safe_load(yaml_str)

        assert isinstance(data["action"]["cost"], Reference)
        assert data["action"]["cost"].name == "action.cost.default_action"
        assert data["action"]["name"] == "test"

    def test_resolve_ref_with_reference_class(self):
        """resolve_ref works with spec_lang Reference class."""
        from alienbio.spec_lang.eval import Reference

        g = Globals()
        ref = Reference(name="action.cost.default_action")
        assert resolve_ref(ref, g) == 1.0

    def test_full_yaml_workflow(self):
        """Full workflow: load YAML with !ref, resolve refs."""
        from alienbio.spec_lang.eval import register_eval_tags
        register_eval_tags()

        yaml_str = """
        globals:
          custom.value: 42

        interface:
          actions:
            test_action:
              cost: !ref action.cost.default_action
              custom: !ref custom.value
        """
        scenario = yaml.safe_load(yaml_str)
        g = create_globals_from_scenario(scenario)

        resolved = resolve_refs_in_dict(scenario["interface"], g)
        assert resolved["actions"]["test_action"]["cost"] == 1.0
        assert resolved["actions"]["test_action"]["custom"] == 42


class TestGlobalsIntegration:
    """Integration tests for globals with scenarios."""

    def test_scenario_with_interface_refs(self):
        """Globals work with interface action definitions."""
        scenario = {
            "globals": {
                "action.cost.default_action": 2.0,
                "myproject.feedstock_cost": 5.0
            },
            "interface": {
                "actions": {
                    "add_feedstock": {
                        "cost": {"__ref__": "myproject.feedstock_cost"},
                        "description": "Add feedstock"
                    }
                }
            }
        }

        g = create_globals_from_scenario(scenario)
        resolved = resolve_refs_in_dict(scenario["interface"], g)

        assert resolved["actions"]["add_feedstock"]["cost"] == 5.0
        assert resolved["actions"]["add_feedstock"]["description"] == "Add feedstock"

    def test_per_action_override_via_local(self):
        """Per-action overrides can be applied via local."""
        g = Globals(scenario_overrides={"action.cost.default_action": 2.0})

        # Simulate per-action override
        g.set("action.cost.default_action", 10.0)

        assert g.get("action.cost.default_action") == 10.0

        # Clear local to restore scenario-level
        g.clear_local()
        assert g.get("action.cost.default_action") == 2.0
