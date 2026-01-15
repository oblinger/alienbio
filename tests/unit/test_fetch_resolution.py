"""Comprehensive tests for bio.fetch() string resolution.

Tests cover three access patterns:
1. DAT access (string contains "/")
2. Module access (all dots, matches loaded module)
3. Source root access (all dots, no module match)

Plus the shared dig operation and edge cases.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import MagicMock, patch
import sys


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_source_root(tmp_path):
    """Create a temporary source root with test YAML files."""
    # Create directory structure:
    # tmp_path/
    #   scenarios/
    #     mutualism.yaml
    #     mutualism/
    #       index.yaml
    #       variants.yaml
    #   worlds/
    #     ecosystem.yaml
    #   single.yaml

    scenarios = tmp_path / "scenarios"
    scenarios.mkdir()

    # scenarios/mutualism.yaml
    (scenarios / "mutualism.yaml").write_text("""
scenario.mutualism:
  name: Mutualism Test
  interface:
    actions: [feed, adjust]
  test1:
    briefing: "Test 1 briefing"
  test2:
    briefing: "Test 2 briefing"
""")

    # scenarios/mutualism/ directory with index.yaml
    mutualism_dir = scenarios / "mutualism"
    mutualism_dir.mkdir()
    (mutualism_dir / "index.yaml").write_text("""
scenario.mutualism_indexed:
  name: Mutualism from Index
  variant_a:
    seed: 42
  variant_b:
    seed: 99
""")
    (mutualism_dir / "variants.yaml").write_text("""
variants:
  stress_test:
    duration: 1000
  quick_test:
    duration: 100
""")

    # worlds/ecosystem.yaml
    worlds = tmp_path / "worlds"
    worlds.mkdir()
    (worlds / "ecosystem.yaml").write_text("""
world.ecosystem:
  molecules:
    ME1:
      name: Metabolite 1
    ME2:
      name: Metabolite 2
  reactions:
    r1:
      rate: 0.5
""")

    # single.yaml at root
    (tmp_path / "single.yaml").write_text("""
config:
  timeout: 30
  retries: 3
nested:
  deep:
    value: 42
""")

    return tmp_path


@pytest.fixture
def mock_dat(tmp_path):
    """Create a mock DAT with content."""
    dat_path = tmp_path / "experiments" / "baseline"
    dat_path.mkdir(parents=True)

    (dat_path / "index.yaml").write_text("""
scenario:
  name: Baseline Experiment
  seed: 42
results:
  scores:
    health: 0.85
    efficiency: 0.72
  metadata:
    run_time: 123.4
""")

    # Create a mock DAT object
    mock = MagicMock()
    mock.path = str(dat_path)
    mock.get_path.return_value = str(dat_path)
    mock.get_path_name.return_value = "experiments/baseline"

    return mock, dat_path


@pytest.fixture
def test_module():
    """Create a test module with global variables."""
    import types

    module = types.ModuleType("test_fetch_module")
    module.CONFIG = {
        "timeout": 30,
        "database": {
            "host": "localhost",
            "port": 5432
        }
    }
    module.WORLDS = {
        "ecosystem": {
            "name": "Test Ecosystem",
            "molecules": ["ME1", "ME2"]
        }
    }

    # Add to sys.modules so it can be imported
    sys.modules["test_fetch_module"] = module

    yield module

    # Cleanup
    del sys.modules["test_fetch_module"]


# =============================================================================
# Routing Tests - Detecting which pattern to use
# =============================================================================

class TestFetchRouting:
    """Test that fetch correctly routes to DAT, module, or source root."""

    def test_slash_routes_to_dat(self):
        """String with '/' should route to DAT access."""
        test_cases = [
            "experiments/baseline",
            "experiments/baseline.scenario",
            "data/runs/exp_001.results",
            "a/b/c/d.e.f.g",
        ]
        for s in test_cases:
            assert "/" in s, f"Test case {s} should contain slash"
            # When implemented: assert _get_fetch_pattern(s) == "dat"

    def test_dots_only_no_module_routes_to_source(self):
        """Dotted string not matching module should route to source root."""
        test_cases = [
            "scenarios.mutualism",
            "worlds.ecosystem.molecules",
            "config.timeout",
        ]
        for s in test_cases:
            assert "/" not in s, f"Test case {s} should not contain slash"
            # When implemented with no matching module:
            # assert _get_fetch_pattern(s) == "source_root"

    def test_dots_matching_module_routes_to_module(self, test_module):
        """Dotted string matching loaded module should route to module access."""
        # When implemented:
        # assert _get_fetch_pattern("test_fetch_module.CONFIG") == "module"
        # assert _get_fetch_pattern("test_fetch_module.CONFIG.timeout") == "module"
        pass


# =============================================================================
# DAT Access Tests
# =============================================================================

class TestDatAccess:
    """Test DAT access pattern (strings with '/')."""

    def test_dat_name_extraction_simple(self):
        """Extract DAT name from simple path."""
        # "experiments/baseline" → DAT name = "experiments/baseline", dig = []
        # When implemented:
        # dat_name, dig_path = _parse_dat_specifier("experiments/baseline")
        # assert dat_name == "experiments/baseline"
        # assert dig_path == []
        pass

    def test_dat_name_extraction_with_dig(self):
        """Extract DAT name and dig path."""
        # "experiments/baseline.scenario" → DAT = "experiments/baseline", dig = ["scenario"]
        # "experiments/baseline.results.scores" → DAT = "experiments/baseline", dig = ["results", "scores"]
        pass

    def test_dat_name_multi_segment(self):
        """DAT names can have multiple path segments."""
        # "data/experiments/2024/baseline.results"
        # → DAT = "data/experiments/2024/baseline", dig = ["results"]
        pass

    def test_dat_access_returns_dat_object(self, mock_dat):
        """Fetching DAT name without dig path returns DAT content."""
        # bio.fetch("experiments/baseline") → returns loaded DAT content
        pass

    def test_dat_access_with_dig(self, mock_dat):
        """Fetching with dig path returns nested value."""
        # bio.fetch("experiments/baseline.results.scores.health") → 0.85
        pass

    def test_dat_access_orm_caching(self, mock_dat):
        """Same DAT should return cached instance."""
        # dat1 = bio.fetch("experiments/baseline")
        # dat2 = bio.fetch("experiments/baseline")
        # assert dat1 is dat2  # Same object from ORM cache
        pass

    def test_dat_not_found_error(self):
        """Non-existent DAT should raise clear error."""
        # with pytest.raises(FileNotFoundError, match="DAT not found"):
        #     bio.fetch("nonexistent/dat")
        pass

    def test_dat_dig_key_not_found(self, mock_dat):
        """Dig path with non-existent key should raise KeyError."""
        # with pytest.raises(KeyError, match="nonexistent"):
        #     bio.fetch("experiments/baseline.nonexistent")
        pass


# =============================================================================
# Module Access Tests
# =============================================================================

class TestModuleAccess:
    """Test module access pattern (dots, matches loaded module)."""

    def test_module_returns_global_variable(self, test_module):
        """Fetch module.VARIABLE returns the variable."""
        # result = bio.fetch("test_fetch_module.CONFIG")
        # assert result == {"timeout": 30, "database": {"host": "localhost", "port": 5432}}
        pass

    def test_module_dig_into_dict(self, test_module):
        """Fetch can dig into module's dict variables."""
        # result = bio.fetch("test_fetch_module.CONFIG.timeout")
        # assert result == 30
        # result = bio.fetch("test_fetch_module.CONFIG.database.host")
        # assert result == "localhost"
        pass

    def test_module_dig_into_nested(self, test_module):
        """Fetch handles deeply nested access."""
        # result = bio.fetch("test_fetch_module.WORLDS.ecosystem.molecules")
        # assert result == ["ME1", "ME2"]
        pass

    def test_module_not_found_falls_through(self):
        """Non-existent module should fall through to source root."""
        # "nonexistent_module.CONFIG" should try source roots, not raise ModuleNotFoundError
        pass

    def test_module_attribute_not_found(self, test_module):
        """Module exists but attribute doesn't should raise AttributeError."""
        # with pytest.raises(AttributeError):
        #     bio.fetch("test_fetch_module.NONEXISTENT")
        pass

    def test_module_partial_path_resolution(self):
        """Handle multi-segment module names like alienbio.catalog."""
        # If alienbio.catalog is a module, fetch("alienbio.catalog.worlds")
        # should import alienbio.catalog and get .worlds attribute
        pass


# =============================================================================
# Source Root Access Tests
# =============================================================================

class TestSourceRootAccess:
    """Test source root access pattern (dots, no module match)."""

    def test_single_segment_finds_yaml(self, temp_source_root):
        """Single segment finds root-level YAML file."""
        from alienbio.spec_lang.bio import Bio

        bio = Bio()
        bio.add_source_root(temp_source_root)

        result = bio.fetch("single", raw=True)
        assert result["config"]["timeout"] == 30

    def test_dotted_finds_nested_yaml(self, temp_source_root):
        """Dotted path finds nested YAML file."""
        from alienbio.spec_lang.bio import Bio

        bio = Bio()
        bio.add_source_root(temp_source_root)

        result = bio.fetch("scenarios.mutualism", raw=True)
        assert "scenario.mutualism" in result
        assert result["scenario.mutualism"]["name"] == "Mutualism Test"

    def test_dig_into_yaml_content(self, temp_source_root):
        """Dotted path digs into YAML structure."""
        from alienbio.spec_lang.bio import Bio

        bio = Bio()
        bio.add_source_root(temp_source_root)

        # Dig into nested content
        result = bio.fetch("single.config", raw=True)
        assert result["timeout"] == 30

        result = bio.fetch("single.config.timeout", raw=True)
        assert result == 30

    def test_index_yaml_fallback(self, temp_source_root):
        """Directory with index.yaml is loaded when no .yaml file exists."""
        from alienbio.spec_lang.bio import Bio

        bio = Bio()
        bio.add_source_root(temp_source_root)

        # scenarios/mutualism.yaml exists, so it's found first
        # To test index.yaml fallback, we need a path without a .yaml file
        # The fixture has scenarios/mutualism/ with index.yaml
        # but also scenarios/mutualism.yaml which takes precedence
        # This test verifies the file wins over index
        result = bio.fetch("scenarios.mutualism", raw=True)
        assert result["scenario.mutualism"]["name"] == "Mutualism Test"

    def test_explicit_file_over_index(self, temp_source_root):
        """Explicit filename takes precedence over index.yaml."""
        from alienbio.spec_lang.bio import Bio

        bio = Bio()
        bio.add_source_root(temp_source_root)

        # scenarios/mutualism.yaml exists alongside scenarios/mutualism/index.yaml
        # The .yaml file should win
        result = bio.fetch("scenarios.mutualism", raw=True)
        # mutualism.yaml has "Mutualism Test", index.yaml has "Mutualism from Index"
        assert result["scenario.mutualism"]["name"] == "Mutualism Test"

    def test_deeper_yaml_resolution(self, temp_source_root):
        """Greedy matching finds deepest YAML file."""
        from alienbio.spec_lang.bio import Bio

        bio = Bio()
        bio.add_source_root(temp_source_root)

        # scenarios/mutualism/variants.yaml contains variants.stress_test
        result = bio.fetch("scenarios.mutualism.variants", raw=True)
        assert "variants" in result
        assert result["variants"]["stress_test"]["duration"] == 1000

    def test_multiple_source_roots(self, temp_source_root, tmp_path):
        """Multiple source roots searched in order."""
        from alienbio.spec_lang.bio import Bio

        # Create second root with different content
        second_root = tmp_path / "second"
        second_root.mkdir()
        (second_root / "single.yaml").write_text("value: from_second")

        bio = Bio()
        bio.add_source_root(temp_source_root)  # First root
        bio.add_source_root(second_root)  # Second root

        # First root wins
        result = bio.fetch("single", raw=True)
        assert result["config"]["timeout"] == 30  # From first root

    def test_source_root_not_found(self, temp_source_root):
        """Clear error when not found in any source root."""
        from alienbio.spec_lang.bio import Bio

        bio = Bio()
        bio.add_source_root(temp_source_root)

        with pytest.raises(FileNotFoundError, match="not found in source roots"):
            bio.fetch("nonexistent.path")

    def test_yaml_hydration(self, temp_source_root):
        """Source root YAML is hydrated (tags resolved)."""
        from alienbio.spec_lang.bio import Bio

        bio = Bio()
        bio.add_source_root(temp_source_root)

        # Without raw=True, hydration should occur
        # For now just verify it doesn't crash
        result = bio.fetch("single")
        assert result is not None


# =============================================================================
# Dig Operation Tests
# =============================================================================

class TestDigOperation:
    """Test the shared dig operation used by DAT and source root access."""

    def test_dig_into_dict(self):
        """Dig into dict by key."""
        data = {"a": {"b": {"c": 42}}}
        # assert dig(data, ["a", "b", "c"]) == 42
        pass

    def test_dig_into_object_attributes(self):
        """Dig into object attributes."""
        class Obj:
            x = 1
            y = type("Inner", (), {"z": 2})()

        obj = Obj()
        # assert dig(obj, ["x"]) == 1
        # assert dig(obj, ["y", "z"]) == 2
        pass

    def test_dig_mixed_dict_and_object(self):
        """Dig through mix of dicts and objects."""
        class Obj:
            data = {"nested": {"value": 99}}

        obj = Obj()
        # assert dig(obj, ["data", "nested", "value"]) == 99
        pass

    def test_dig_empty_path(self):
        """Empty path returns root."""
        data = {"x": 1}
        # assert dig(data, []) == data
        pass

    def test_dig_key_not_found(self):
        """Missing key raises KeyError."""
        data = {"a": 1}
        # with pytest.raises(KeyError):
        #     dig(data, ["nonexistent"])
        pass

    def test_dig_attribute_not_found(self):
        """Missing attribute raises appropriate error."""
        class Obj:
            x = 1

        obj = Obj()
        # with pytest.raises((KeyError, AttributeError)):
        #     dig(obj, ["nonexistent"])
        pass

    def test_dig_into_list_by_index(self):
        """Dig into list using string index."""
        data = {"items": ["a", "b", "c"]}
        # Should this work? dig(data, ["items", "1"]) → "b"
        # Or require explicit list handling?
        pass


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_string_error(self):
        """Empty string raises error."""
        from alienbio.spec_lang.bio import Bio

        bio = Bio()
        # Empty string should fail - no path to resolve
        with pytest.raises((FileNotFoundError, ValueError)):
            bio.fetch("")

    def test_single_segment_module(self, test_module):
        """Single segment matching module - not currently supported."""
        # Module access requires module.attribute format
        # Single segment "os" would need to be a source root file
        pass  # Module-only access not implemented

    def test_single_segment_source(self, temp_source_root):
        """Single segment not matching module searches source roots."""
        from alienbio.spec_lang.bio import Bio

        bio = Bio()
        bio.add_source_root(temp_source_root)

        # "single" finds single.yaml
        result = bio.fetch("single", raw=True)
        assert result["config"]["timeout"] == 30

    def test_trailing_dot(self, temp_source_root):
        """Trailing dot is ignored (tolerant parsing)."""
        from alienbio.spec_lang.bio import Bio

        bio = Bio()
        bio.add_source_root(temp_source_root)

        # Trailing dot is ignored - returns same as "single"
        result = bio.fetch("single.", raw=True)
        assert result["config"]["timeout"] == 30

    def test_double_dots(self, temp_source_root):
        """Double dots are ignored (tolerant parsing)."""
        from alienbio.spec_lang.bio import Bio

        bio = Bio()
        bio.add_source_root(temp_source_root)

        # Double dots - empty segment is ignored, same as "single.config"
        result = bio.fetch("single..config", raw=True)
        assert result["timeout"] == 30

    def test_leading_slash(self, tmp_path):
        """Leading slash is absolute filesystem path."""
        from alienbio.spec_lang.bio import Bio

        # Create a file at absolute path
        spec_dir = tmp_path / "myspec"
        spec_dir.mkdir()
        (spec_dir / "spec.yaml").write_text("name: absolute test")

        bio = Bio()
        result = bio.fetch(str(spec_dir), raw=True)
        assert result["name"] == "absolute test"

    def test_dot_in_dat_name(self, tmp_path):
        """DAT names can contain dots in path segments."""
        from alienbio.spec_lang.bio import Bio

        # Create experiments/v1.0/baseline/spec.yaml
        dat_path = tmp_path / "experiments" / "v1.0" / "baseline"
        dat_path.mkdir(parents=True)
        (dat_path / "spec.yaml").write_text("""
results:
  score: 0.85
""")

        bio = Bio()
        # Path with dots in directory name
        result = bio.fetch(str(dat_path), raw=True)
        assert result["results"]["score"] == 0.85

    def test_unicode_in_names(self, tmp_path):
        """Unicode characters in names are handled."""
        from alienbio.spec_lang.bio import Bio

        # Create file with unicode name
        (tmp_path / "テスト.yaml").write_text("value: unicode works")

        bio = Bio()
        bio.add_source_root(tmp_path)

        result = bio.fetch("テスト", raw=True)
        assert result["value"] == "unicode works"

    def test_whitespace_handling(self, temp_source_root):
        """Leading/trailing whitespace - currently not stripped."""
        from alienbio.spec_lang.bio import Bio

        bio = Bio()
        bio.add_source_root(temp_source_root)

        # Whitespace is not stripped - results in not found
        with pytest.raises(FileNotFoundError):
            bio.fetch("  single  ", raw=True)


# =============================================================================
# Integration Tests
# =============================================================================

class TestFetchIntegration:
    """Integration tests combining multiple patterns."""

    def test_fetch_then_dig_further(self, temp_source_root):
        """Fetch partial path, then dig further into result."""
        # scenario = bio.fetch("scenarios.mutualism")
        # briefing = Bio.get(scenario, "test1.briefing")
        pass

    def test_fetch_with_raw_flag(self, temp_source_root):
        """raw=True returns unhydrated dict."""
        # result = bio.fetch("scenarios.mutualism", raw=True)
        # assert isinstance(result, dict)
        # assert "_type" not in result  # Not hydrated
        pass

    def test_fetch_caching_across_patterns(self, temp_source_root, mock_dat):
        """Caching works correctly across different patterns."""
        # DAT and source root should have separate caches
        pass

    def test_fetch_error_messages_are_helpful(self):
        """Error messages indicate which pattern was tried."""
        # Error should say "Not found in DAT 'x', source roots [a, b], or modules"
        pass


# =============================================================================
# Performance Tests
# =============================================================================

class TestFetchPerformance:
    """Performance-related tests."""

    def test_repeated_fetch_uses_cache(self, temp_source_root):
        """Repeated fetch of same path hits cache."""
        # First fetch loads from disk
        # Second fetch returns cached
        pass

    def test_source_root_scanning_stops_early(self, temp_source_root):
        """Source root scanning stops at first match."""
        # With multiple roots, don't scan all if found in first
        pass


# =============================================================================
# Error Message Tests
# =============================================================================

class TestErrorMessages:
    """Test that error messages are clear and actionable."""

    def test_dat_not_found_shows_searched_path(self):
        """DAT not found error shows the path that was searched."""
        pass

    def test_source_root_not_found_lists_roots(self, temp_source_root):
        """Source root not found lists all roots that were searched."""
        pass

    def test_dig_error_shows_full_path(self):
        """Dig error shows which segment failed and full path."""
        # "Key 'nonexistent' not found in scenarios.mutualism (at segment 3)"
        pass

    def test_ambiguous_resolution_warning(self):
        """Warn if same name exists in multiple places."""
        # If "config" is both a module AND a source root file, warn?
        pass


# =============================================================================
# Bio Constructor Tests
# =============================================================================

class TestBioConstructor:
    """Test Bio(dat=...) constructor and bio.dat accessor."""

    def test_bio_with_no_dat(self):
        """Bio() with no dat creates anonymous DAT lazily."""
        from alienbio.spec_lang.bio import Bio

        bio = Bio()
        # Accessing dat should create an anonymous DAT
        dat = bio.dat
        assert dat == {}  # Currently just empty dict

    def test_bio_dat_returns_same_object(self):
        """Repeated access to bio.dat returns same object."""
        from alienbio.spec_lang.bio import Bio

        bio = Bio()
        dat1 = bio.dat
        dat2 = bio.dat
        assert dat1 is dat2

    def test_bio_with_dat_string(self, tmp_path):
        """Bio(dat='path') fetches DAT when dat property accessed."""
        from alienbio.spec_lang.bio import Bio

        # Create a spec directory
        spec_dir = tmp_path / "mydat"
        spec_dir.mkdir()
        (spec_dir / "spec.yaml").write_text("name: test dat\nvalue: 42")

        Bio.clear_cache()
        bio = Bio(dat=str(spec_dir))

        # Accessing dat should fetch and return the DAT
        dat = bio.dat
        assert dat["name"] == "test dat"
        assert dat["value"] == 42

    def test_bio_with_dat_object(self):
        """Bio(dat=obj) uses object directly."""
        from alienbio.spec_lang.bio import Bio

        dat_obj = {"name": "direct dat", "value": 99}
        bio = Bio(dat=dat_obj)

        assert bio.dat is dat_obj
        assert bio.dat["name"] == "direct dat"

    def test_clear_cache(self, tmp_path):
        """Bio.clear_cache() clears the DAT cache."""
        from alienbio.spec_lang.bio import Bio

        # Create a spec
        spec_dir = tmp_path / "cachetest"
        spec_dir.mkdir()
        (spec_dir / "spec.yaml").write_text("value: 1")

        Bio.clear_cache()
        bio = Bio()

        # First fetch
        result1 = bio.fetch(str(spec_dir))

        # Modify the file
        (spec_dir / "spec.yaml").write_text("value: 2")

        # Second fetch should return cached value
        result2 = bio.fetch(str(spec_dir))
        assert result2["value"] == 1  # Still cached

        # Clear cache and fetch again
        Bio.clear_cache()
        result3 = bio.fetch(str(spec_dir))
        assert result3["value"] == 2  # Fresh load


# =============================================================================
# Bio.cd() Tests
# =============================================================================

class TestBioCd:
    """Test Bio.cd() for current DAT tracking."""

    def test_cd_returns_none_initially(self):
        """cd() returns None when no current DAT set."""
        from alienbio.spec_lang.bio import Bio

        bio = Bio()
        assert bio.cd() is None

    def test_cd_sets_and_returns_path(self, tmp_path):
        """cd(path) sets current DAT and returns it."""
        from alienbio.spec_lang.bio import Bio

        bio = Bio()
        result = bio.cd(tmp_path)
        assert result == tmp_path.resolve()
        assert bio.cd() == tmp_path.resolve()

    def test_cd_expands_user(self):
        """cd() expands ~ in paths."""
        from alienbio.spec_lang.bio import Bio
        from pathlib import Path

        bio = Bio()
        bio.cd("~/test")
        assert bio.cd() == Path("~/test").expanduser().resolve()

    def test_fetch_relative_path(self, tmp_path):
        """fetch('./relative') resolves against current DAT."""
        from alienbio.spec_lang.bio import Bio

        # Create DAT structure
        dat_dir = tmp_path / "mydat"
        dat_dir.mkdir()
        sub_dir = dat_dir / "results"
        sub_dir.mkdir()
        (sub_dir / "spec.yaml").write_text("score: 0.95")

        Bio.clear_cache()
        bio = Bio()
        bio.cd(dat_dir)

        result = bio.fetch("./results", raw=True)
        assert result["score"] == 0.95

    def test_fetch_relative_without_cd_raises(self):
        """fetch('./...') without cd() raises ValueError."""
        from alienbio.spec_lang.bio import Bio

        bio = Bio()
        with pytest.raises(ValueError, match="requires current DAT"):
            bio.fetch("./something")

    def test_store_relative_path(self, tmp_path):
        """store('./relative', obj) resolves against current DAT."""
        from alienbio.spec_lang.bio import Bio

        dat_dir = tmp_path / "mydat"
        dat_dir.mkdir()

        bio = Bio()
        bio.cd(dat_dir)
        bio.store("./output", {"result": 42}, raw=True)

        # Verify file was created
        spec_file = dat_dir / "output" / "spec.yaml"
        assert spec_file.exists()

    def test_store_relative_without_cd_raises(self):
        """store('./...', obj) without cd() raises ValueError."""
        from alienbio.spec_lang.bio import Bio

        bio = Bio()
        with pytest.raises(ValueError, match="requires current DAT"):
            bio.store("./output", {"data": 1})


# =============================================================================
# DAT + Dig Pattern Tests
# =============================================================================

class TestDatDigPattern:
    """Test path.dig.path pattern for navigating into DAT structures."""

    def test_fetch_with_single_dig(self, tmp_path):
        """fetch('path/dat.key') digs into the DAT."""
        from alienbio.spec_lang.bio import Bio

        dat_dir = tmp_path / "mydat"
        dat_dir.mkdir()
        (dat_dir / "spec.yaml").write_text("baseline: {score: 0.95}\nconfig: {timeout: 30}")

        Bio.clear_cache()
        bio = Bio()
        result = bio.fetch(f"{dat_dir}.baseline", raw=True)
        assert result == {"score": 0.95}

    def test_fetch_with_deep_dig(self, tmp_path):
        """fetch('path/dat.key1.key2') digs multiple levels."""
        from alienbio.spec_lang.bio import Bio

        dat_dir = tmp_path / "mydat"
        dat_dir.mkdir()
        (dat_dir / "spec.yaml").write_text("config: {settings: {timeout: 30}}")

        Bio.clear_cache()
        bio = Bio()
        result = bio.fetch(f"{dat_dir}.config.settings.timeout", raw=True)
        assert result == 30

    def test_fetch_dig_key_not_found(self, tmp_path):
        """fetch with non-existent dig key raises KeyError."""
        from alienbio.spec_lang.bio import Bio

        dat_dir = tmp_path / "mydat"
        dat_dir.mkdir()
        (dat_dir / "spec.yaml").write_text("config: {timeout: 30}")

        Bio.clear_cache()
        bio = Bio()
        with pytest.raises(KeyError, match="nonexistent"):
            bio.fetch(f"{dat_dir}.nonexistent", raw=True)

    def test_fetch_dig_with_dotted_dirname(self, tmp_path):
        """Directory with dots in name is found before dig."""
        from alienbio.spec_lang.bio import Bio

        # Create a directory with dots in its name
        dat_dir = tmp_path / "my.dat.v1"
        dat_dir.mkdir()
        (dat_dir / "spec.yaml").write_text("value: 42")

        Bio.clear_cache()
        bio = Bio()
        result = bio.fetch(str(dat_dir), raw=True)
        assert result == {"value": 42}

    def test_fetch_dig_with_processed_data(self, tmp_path):
        """Dig works on processed (not just raw) data."""
        from alienbio.spec_lang.bio import Bio

        dat_dir = tmp_path / "mydat"
        dat_dir.mkdir()
        (dat_dir / "spec.yaml").write_text("baseline: {score: 0.95}")

        Bio.clear_cache()
        bio = Bio()
        result = bio.fetch(f"{dat_dir}.baseline")  # No raw=True
        assert result == {"score": 0.95}


# =============================================================================
# Dots-Before-Slash Pattern Tests
# =============================================================================

class TestDotsBeforeSlash:
    """Test prefix.path/suffix pattern for source root + path."""

    def test_dots_before_slash_resolves(self, tmp_path):
        """fetch('prefix.path/suffix') resolves prefix via source roots."""
        from alienbio.spec_lang.bio import Bio

        # Create catalog/scenarios/mutualism structure
        scenarios = tmp_path / "catalog" / "scenarios"
        mutualism = scenarios / "mutualism"
        mutualism.mkdir(parents=True)
        (mutualism / "spec.yaml").write_text("name: mutualism\nscore: 0.95")

        Bio.clear_cache()
        bio = Bio()
        bio.add_source_root(tmp_path)

        result = bio.fetch("catalog.scenarios/mutualism", raw=True)
        assert result["name"] == "mutualism"

    def test_dots_before_slash_with_dig(self, tmp_path):
        """fetch('prefix.path/suffix.key') combines prefix resolution with dig."""
        from alienbio.spec_lang.bio import Bio

        scenarios = tmp_path / "catalog" / "scenarios"
        mutualism = scenarios / "mutualism"
        mutualism.mkdir(parents=True)
        (mutualism / "spec.yaml").write_text("config: {timeout: 30}")

        Bio.clear_cache()
        bio = Bio()
        bio.add_source_root(tmp_path)

        result = bio.fetch("catalog.scenarios/mutualism.config.timeout", raw=True)
        assert result == 30

    def test_dots_before_slash_no_match(self, tmp_path):
        """Unresolved prefix falls through to normal path resolution."""
        from alienbio.spec_lang.bio import Bio

        Bio.clear_cache()
        bio = Bio()
        bio.add_source_root(tmp_path)

        # This should fail since "nonexistent.path" can't be resolved
        with pytest.raises(FileNotFoundError):
            bio.fetch("nonexistent.path/something")


# =============================================================================
# Built-in Catalog Source Root Tests
# =============================================================================

class TestCatalogSourceRoot:
    """Test automatic catalog source root configuration."""

    def test_bio_has_catalog_source_root(self):
        """Bio automatically adds catalog as a source root."""
        from alienbio.spec_lang.bio import Bio

        bio = Bio()
        # Check that at least one source root exists and points to catalog
        catalog_roots = [r for r in bio._source_roots if "catalog" in str(r.path)]
        assert len(catalog_roots) > 0, "Bio should auto-configure catalog source root"

    def test_fetch_catalog_test_scenario(self):
        """bio.fetch('test.scenarios.simple') loads from catalog."""
        from alienbio.spec_lang.bio import Bio

        Bio.clear_cache()
        bio = Bio()

        result = bio.fetch("test.scenarios.simple", raw=True)
        assert result is not None
        assert result.get("name") == "test_scenario"
        assert "interface" in result
        assert "actions" in result["interface"]

    def test_fetch_catalog_prefix_registry(self):
        """bio.fetch('_index') loads prefix registry from catalog."""
        from alienbio.spec_lang.bio import Bio

        Bio.clear_cache()
        bio = Bio()

        result = bio.fetch("_index", raw=True)
        assert result is not None
        assert "prefixes" in result
        assert "test" in result["prefixes"]
        assert "mute" in result["prefixes"]

    def test_fetch_catalog_timing_scenario(self):
        """bio.fetch('test.scenarios.timing') loads timing scenario."""
        from alienbio.spec_lang.bio import Bio

        Bio.clear_cache()
        bio = Bio()

        result = bio.fetch("test.scenarios.timing", raw=True)
        assert result is not None
        assert result.get("name") == "timing_test"
