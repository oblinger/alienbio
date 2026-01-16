"""Tests for the build command DAT folder creation."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest
import yaml

from alienbio.commands.build import (
    _is_dat_spec,
    _build_dat_folder,
    build_command,
)


class TestIsDatSpec:
    """Tests for DAT spec detection."""

    def test_valid_dat_spec_with_path(self):
        """Test detection of valid DAT spec with dat.path."""
        spec = {
            "dat": {"kind": "Dat", "path": "data/test_{seed}"},
            "build": {"index.yaml": "."},
        }
        assert _is_dat_spec(spec) is True

    def test_valid_dat_spec_with_name(self):
        """Test detection of valid DAT spec with dat.name (dvc_dat convention)."""
        spec = {
            "dat": {"kind": "Dat", "name": "data/test_{seed}"},
            "build": {"index.yaml": "."},
        }
        assert _is_dat_spec(spec) is True

    def test_missing_dat_section(self):
        """Test spec without dat section is not a DAT spec."""
        spec = {"scenario": {"name": "test"}}
        assert _is_dat_spec(spec) is False

    def test_missing_path_and_name(self):
        """Test dat section without path or name is not a DAT spec."""
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

    def test_build_dat_spec(self, temp_dir, capsys):
        """Test building a DAT spec creates folder."""
        # Create a source spec file with absolute path in temp dir
        source = temp_dir / "source.yaml"
        output_path = temp_dir / "output_42"
        spec = {
            "dat": {"kind": "Dat", "path": str(output_path)},
            "build": {"index.yaml": "."},
            "scenario": {"name": "test"},
        }
        with open(source, "w") as f:
            yaml.dump(spec, f)

        # Run build command
        result = build_command([str(source), "--seed", "42"])
        assert result == 0

        # Check output message
        captured = capsys.readouterr()
        assert "Created:" in captured.out

        # Check folder was created (parse path from output)
        # The path is printed as "Created: <path>"
        created_line = [l for l in captured.out.split("\n") if "Created:" in l][0]
        created_path = Path(created_line.split("Created:")[1].strip())
        assert created_path.exists()
        assert (created_path / "_spec_.yaml").exists()
        assert (created_path / "index.yaml").exists()

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
