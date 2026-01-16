"""Tests for the build command DAT folder creation."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest
import yaml

from alienbio.commands.build import (
    _substitute_path_template,
    _is_dat_spec,
    _build_dat_folder,
    build_command,
)


class TestPathTemplateSubstitution:
    """Tests for path template variable substitution."""

    def test_seed_substitution(self):
        """Test {seed} is replaced with the seed value."""
        result = _substitute_path_template("data/test_{seed}", 42)
        assert result == "data/test_42"

    def test_seed_substitution_multiple(self):
        """Test multiple {seed} occurrences."""
        result = _substitute_path_template("data/{seed}/run_{seed}", 123)
        assert result == "data/123/run_123"

    def test_date_substitution(self):
        """Test {YYYY}, {MM}, {DD} are replaced with current date."""
        result = _substitute_path_template("data/{YYYY}/{MM}/{DD}", 0)
        # Just verify format is correct (4 digits, 2 digits, 2 digits)
        parts = result.split("/")
        assert parts[0] == "data"
        assert len(parts[1]) == 4 and parts[1].isdigit()
        assert len(parts[2]) == 2 and parts[2].isdigit()
        assert len(parts[3]) == 2 and parts[3].isdigit()

    def test_unique_substitution(self):
        """Test {unique} is replaced with unique identifier."""
        result1 = _substitute_path_template("data/run_{unique}", 0)
        result2 = _substitute_path_template("data/run_{unique}", 0)
        # Unique values should be different (or very unlikely to be same)
        assert result1.startswith("data/run_")
        assert len(result1) > len("data/run_")

    def test_combined_substitution(self):
        """Test multiple variable types in one template."""
        result = _substitute_path_template("data/{YYYY}/scenario_{seed}", 42)
        assert "/scenario_42" in result
        # Year should be present
        assert "/20" in result  # Works for 2000-2099


class TestIsDatSpec:
    """Tests for DAT spec detection."""

    def test_valid_dat_spec(self):
        """Test detection of valid DAT spec."""
        spec = {
            "dat": {"kind": "Dat", "path": "data/test_{seed}"},
            "build": {"index.yaml": "."},
        }
        assert _is_dat_spec(spec) is True

    def test_missing_dat_section(self):
        """Test spec without dat section is not a DAT spec."""
        spec = {"scenario": {"name": "test"}}
        assert _is_dat_spec(spec) is False

    def test_missing_path(self):
        """Test dat section without path is not a DAT spec."""
        spec = {
            "dat": {"kind": "Dat"},
            "build": {"index.yaml": "."},
        }
        assert _is_dat_spec(spec) is False

    def test_missing_build(self):
        """Test dat section without build is not a DAT spec."""
        spec = {"dat": {"kind": "Dat", "path": "data/test_{seed}"}}
        assert _is_dat_spec(spec) is False

    def test_dat_not_dict(self):
        """Test dat section that's not a dict."""
        spec = {"dat": "not a dict", "build": {"index.yaml": "."}}
        assert _is_dat_spec(spec) is False


class TestBuildDatFolder:
    """Tests for DAT folder creation."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests."""
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        shutil.rmtree(tmpdir)

    def test_creates_folder(self, temp_dir):
        """Test that DAT folder is created."""
        spec = {
            "dat": {"kind": "Dat", "path": str(temp_dir / "output_{seed}")},
            "build": {},
        }
        result = _build_dat_folder(spec, Path("source"), seed=42)
        assert result.exists()
        assert result.is_dir()
        assert result == temp_dir / "output_42"

    def test_creates_spec_yaml(self, temp_dir):
        """Test that _spec_.yaml is created with metadata."""
        spec = {
            "dat": {"kind": "Dat", "path": str(temp_dir / "output_{seed}")},
            "build": {},
        }
        result = _build_dat_folder(spec, Path("source.yaml"), seed=42)

        spec_file = result / "_spec_.yaml"
        assert spec_file.exists()

        with open(spec_file) as f:
            written_spec = yaml.safe_load(f)

        assert "_built_with" in written_spec
        assert written_spec["_built_with"]["seed"] == 42
        assert "timestamp" in written_spec["_built_with"]
        assert written_spec["_built_with"]["source"] == "source.yaml"

    def test_output_path_override(self, temp_dir):
        """Test that --output overrides the path template."""
        spec = {
            "dat": {"kind": "Dat", "path": "data/should_not_use_{seed}"},
            "build": {},
        }
        custom_path = temp_dir / "custom_output"
        result = _build_dat_folder(spec, Path("source"), seed=42, output_path=custom_path)

        assert result == custom_path
        assert result.exists()

    def test_build_section_dot_reference(self, temp_dir):
        """Test build section with '.' reference builds current spec content."""
        spec = {
            "dat": {"kind": "Dat", "path": str(temp_dir / "output_{seed}")},
            "build": {"index.yaml": "."},
            "scenario": {"name": "test", "value": 123},
        }
        result = _build_dat_folder(spec, Path("source"), seed=42)

        index_file = result / "index.yaml"
        assert index_file.exists()

        with open(index_file) as f:
            content = yaml.safe_load(f)

        # The content should be a built object (dict), not contain dat/build metadata
        assert isinstance(content, dict)
        # dat and build sections should NOT be in the built content
        assert "dat" not in content
        assert "build" not in content


class TestBuildCommand:
    """Tests for the build_command function."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests."""
        tmpdir = tempfile.mkdtemp()
        old_cwd = os.getcwd()
        os.chdir(tmpdir)
        yield Path(tmpdir)
        os.chdir(old_cwd)
        shutil.rmtree(tmpdir)

    def test_build_dat_spec(self, temp_dir):
        """Test building a DAT spec creates folder."""
        # Create a source spec file
        source = temp_dir / "source.yaml"
        spec = {
            "dat": {"kind": "Dat", "path": "output_{seed}"},
            "build": {"index.yaml": "."},
            "scenario": {"name": "test"},
        }
        with open(source, "w") as f:
            yaml.dump(spec, f)

        # Run build command
        result = build_command([str(source), "--seed", "42"])
        assert result == 0

        # Check folder was created
        output_dir = temp_dir / "output_42"
        assert output_dir.exists()
        assert (output_dir / "_spec_.yaml").exists()
        assert (output_dir / "index.yaml").exists()

    def test_build_non_dat_spec_prints_yaml(self, temp_dir, capsys):
        """Test building non-DAT spec prints expanded YAML."""
        # Create a simple spec file (no dat section)
        source = temp_dir / "simple.yaml"
        spec = {"scenario": {"name": "test", "value": 42}}
        with open(source, "w") as f:
            yaml.dump(spec, f)

        # Run build command
        result = build_command([str(source)])
        assert result == 0

        # Check output was printed
        captured = capsys.readouterr()
        assert "scenario" in captured.out
        assert "name" in captured.out

    def test_build_with_json_output(self, temp_dir, capsys):
        """Test --json flag outputs JSON format."""
        source = temp_dir / "simple.yaml"
        spec = {"scenario": {"name": "test"}}
        with open(source, "w") as f:
            yaml.dump(spec, f)

        result = build_command([str(source), "--json"])
        assert result == 0

        captured = capsys.readouterr()
        assert '"scenario"' in captured.out  # JSON uses double quotes

    def test_build_missing_file(self, temp_dir):
        """Test error when spec file doesn't exist."""
        result = build_command(["nonexistent.yaml"])
        assert result == 1

    def test_build_no_args(self):
        """Test error when no arguments provided."""
        result = build_command([])
        assert result == 1
