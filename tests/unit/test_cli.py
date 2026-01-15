"""Tests for the bio CLI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_cli_report_hardcoded_test():
    """Test that bio report runs hardcoded_test and produces correct output."""
    # Run the CLI
    result = subprocess.run(
        [sys.executable, "-m", "alienbio.cli", "src/alienbio/catalog/jobs/hardcoded_test"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent.parent,  # alienbio root
    )

    # Should succeed
    assert result.returncode == 0, f"CLI failed: {result.stderr}"

    output = result.stdout

    # Verify concentrations changed as expected
    assert "A': 0.0" in output or "A': 0" in output, "A should be depleted"
    assert "B': 0.0" in output or "B': 0" in output, "B should be depleted"
    assert "D':" in output and "9.9" in output, "D should have accumulated"

    # Verify scoring
    assert "Score:" in output, "Should show score"
    assert "PASSED" in output, "Should show PASSED"

    # Verify assertions passed
    assert "✓" in output, "Should show checkmarks for passing assertions"


def test_cli_run_hardcoded_test():
    """Test that bio run prints result dict."""
    result = subprocess.run(
        [sys.executable, "-m", "alienbio.cli", "run", "src/alienbio/catalog/jobs/hardcoded_test"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent.parent,
    )

    assert result.returncode == 0, f"CLI failed: {result.stderr}"

    output = result.stdout

    # Should show YAML-formatted result dict
    assert "--- Result ---" in output, "Should show result header"
    assert "final_state:" in output, "Should show final_state"
    assert "scores:" in output, "Should show scores"
    assert "Success: True" in output, "Should show success"


def test_cli_help():
    """Test that bio --help works."""
    result = subprocess.run(
        [sys.executable, "-m", "alienbio.cli", "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "bio" in result.stdout.lower()
    assert "report" in result.stdout.lower()


# -----------------------------------------------------------------------------
# cd command tests
# -----------------------------------------------------------------------------


class TestCdCommand:
    """Tests for the bio cd CLI command."""

    def test_cd_no_current_dat(self, monkeypatch, tmp_path, capsys):
        """Test cd with no current DAT set."""
        from alienbio.commands import cd

        state_file = tmp_path / "state" / "current_dat"       # non-existent
        monkeypatch.setattr(cd, "STATE_FILE", state_file)

        result = cd.cd_command([])

        assert result == 0
        captured = capsys.readouterr()
        assert "no current DAT" in captured.err

    def test_cd_prints_current_dat(self, monkeypatch, tmp_path, capsys):
        """Test cd prints current DAT when set."""
        from alienbio.commands import cd

        state_file = tmp_path / "current_dat"
        state_file.write_text("/some/path/to/dat")
        monkeypatch.setattr(cd, "STATE_FILE", state_file)

        result = cd.cd_command([])

        assert result == 0
        captured = capsys.readouterr()
        assert "/some/path/to/dat" in captured.out

    def test_cd_sets_current_dat(self, monkeypatch, tmp_path, capsys):
        """Test cd <path> sets current DAT."""
        from alienbio.commands import cd

        state_file = tmp_path / "state" / "current_dat"       # will be created
        monkeypatch.setattr(cd, "STATE_FILE", state_file)

        dat_dir = tmp_path / "mydat"
        dat_dir.mkdir()

        result = cd.cd_command([str(dat_dir)])

        assert result == 0
        assert state_file.exists()
        assert str(dat_dir) in state_file.read_text()
        captured = capsys.readouterr()
        assert str(dat_dir) in captured.out

    def test_cd_rejects_nonexistent_path(self, monkeypatch, tmp_path, capsys):
        """Test cd <path> fails for non-existent path."""
        from alienbio.commands import cd

        state_file = tmp_path / "current_dat"
        monkeypatch.setattr(cd, "STATE_FILE", state_file)

        result = cd.cd_command(["/nonexistent/path"])

        assert result == 1
        captured = capsys.readouterr()
        assert "does not exist" in captured.err

    def test_cd_rejects_file_path(self, monkeypatch, tmp_path, capsys):
        """Test cd <path> fails for file (not directory)."""
        from alienbio.commands import cd

        state_file = tmp_path / "current_dat"
        monkeypatch.setattr(cd, "STATE_FILE", state_file)

        file_path = tmp_path / "somefile.txt"
        file_path.write_text("content")

        result = cd.cd_command([str(file_path)])

        assert result == 1
        captured = capsys.readouterr()
        assert "not a directory" in captured.err

    def test_get_current_dat_helper(self, monkeypatch, tmp_path):
        """Test get_current_dat() helper function."""
        from alienbio.commands import cd

        state_file = tmp_path / "current_dat"
        monkeypatch.setattr(cd, "STATE_FILE", state_file)

        assert cd.get_current_dat() is None                   # no state file

        state_file.write_text("/data/experiments/run1")
        path = cd.get_current_dat()
        assert path == Path("/data/experiments/run1")


# -----------------------------------------------------------------------------
# fetch command tests
# -----------------------------------------------------------------------------


class TestFetchCommand:
    """Tests for the bio fetch CLI command."""

    def test_fetch_requires_specifier(self, capsys):
        """Test fetch with no args shows error."""
        from alienbio.commands.fetch import fetch_command

        result = fetch_command([])

        assert result == 1
        captured = capsys.readouterr()
        assert "requires a specifier" in captured.err

    def test_fetch_displays_yaml(self, tmp_path, capsys):
        """Test fetch displays YAML content."""
        from alienbio.commands.fetch import fetch_command
        from alienbio import Bio

        spec_dir = tmp_path / "test_spec"
        spec_dir.mkdir()
        spec_file = spec_dir / "index.yaml"
        spec_file.write_text("name: test\nvalue: 42\n")

        Bio.clear_cache()

        result = fetch_command([str(spec_dir)])

        assert result == 0
        captured = capsys.readouterr()
        assert "name: test" in captured.out
        assert "value: 42" in captured.out

    def test_fetch_not_found(self, capsys):
        """Test fetch with non-existent path."""
        from alienbio.commands.fetch import fetch_command

        result = fetch_command(["/nonexistent/path"])

        assert result == 1
        captured = capsys.readouterr()
        assert "Error" in captured.err


# -----------------------------------------------------------------------------
# store command tests
# -----------------------------------------------------------------------------


class TestStoreCommand:
    """Tests for the bio store CLI command."""

    def test_store_requires_specifier(self, capsys):
        """Test store with no args shows error."""
        from alienbio.commands.store import store_command

        result = store_command([])

        assert result == 1
        captured = capsys.readouterr()
        assert "requires a specifier" in captured.err


# -----------------------------------------------------------------------------
# Bio.store() dehydration tests
# -----------------------------------------------------------------------------


class TestBioStoreDehydration:
    """Tests for Bio.store() dehydration."""

    def test_store_dehydrates_evaluable(self, tmp_path):
        """Test that store() dehydrates Evaluable placeholders."""
        from alienbio import Bio, Evaluable
        import yaml

        bio = Bio()
        target = tmp_path / "dehydrate_test"

        data = {"value": Evaluable(source="normal(50, 10)")}
        bio.store(str(target), data)

        spec_file = target / "index.yaml"
        content = spec_file.read_text()
        result = yaml.safe_load(content)

        assert result == {"value": {"!ev": "normal(50, 10)"}}

    def test_store_dehydrates_quoted(self, tmp_path):
        """Test that store() dehydrates Quoted placeholders."""
        from alienbio import Bio, Quoted
        import yaml

        bio = Bio()
        target = tmp_path / "dehydrate_quoted"

        data = {"rate": Quoted(source="k * S")}
        bio.store(str(target), data)

        spec_file = target / "index.yaml"
        content = spec_file.read_text()
        result = yaml.safe_load(content)

        assert result == {"rate": {"!_": "k * S"}}

    def test_store_dehydrates_reference(self, tmp_path):
        """Test that store() dehydrates Reference placeholders."""
        from alienbio import Bio, Reference
        import yaml

        bio = Bio()
        target = tmp_path / "dehydrate_ref"

        data = {"config": Reference(name="default_config")}
        bio.store(str(target), data)

        spec_file = target / "index.yaml"
        content = spec_file.read_text()
        result = yaml.safe_load(content)

        assert result == {"config": {"!ref": "default_config"}}

    def test_store_raw_skips_dehydration(self, tmp_path):
        """Test that store(..., raw=True) skips dehydration."""
        from alienbio import Bio
        import yaml

        bio = Bio()
        target = tmp_path / "raw_store"

        data = {"simple": "value"}
        bio.store(str(target), data, raw=True)

        spec_file = target / "index.yaml"
        content = spec_file.read_text()
        result = yaml.safe_load(content)

        assert result == {"simple": "value"}


# -----------------------------------------------------------------------------
# build command tests
# -----------------------------------------------------------------------------


class TestBuildCommand:
    """Tests for the bio build CLI command."""

    def test_build_requires_spec_path(self, capsys):
        """Test build with no args shows error."""
        from alienbio.commands.build import build_command

        result = build_command([])

        assert result == 1
        captured = capsys.readouterr()
        assert "requires a spec path" in captured.err

    def test_build_outputs_yaml(self, tmp_path, capsys):
        """Test build outputs YAML."""
        from alienbio.commands.build import build_command

        spec_dir = tmp_path / "test_spec"
        spec_dir.mkdir()
        spec_file = spec_dir / "index.yaml"
        spec_file.write_text("name: test\nvalue: 42\n")

        result = build_command([str(spec_dir)])

        assert result == 0
        captured = capsys.readouterr()
        assert "name: test" in captured.out
        assert "value: 42" in captured.out

    def test_build_json_output(self, tmp_path, capsys):
        """Test build with --json outputs JSON."""
        from alienbio.commands.build import build_command

        spec_dir = tmp_path / "test_spec"
        spec_dir.mkdir()
        spec_file = spec_dir / "index.yaml"
        spec_file.write_text("name: test\nvalue: 42\n")

        result = build_command([str(spec_dir), "--json"])

        assert result == 0
        captured = capsys.readouterr()
        assert '"name": "test"' in captured.out
        assert '"value": 42' in captured.out


# -----------------------------------------------------------------------------
# hydrate command tests
# -----------------------------------------------------------------------------


class TestHydrateCommand:
    """Tests for the bio hydrate CLI command."""

    def test_hydrate_requires_spec_path(self, capsys):
        """Test hydrate with no args shows error."""
        from alienbio.commands.hydrate import hydrate_command

        result = hydrate_command([])

        assert result == 1
        captured = capsys.readouterr()
        assert "requires a spec path" in captured.err

    def test_hydrate_evaluates_ev_tags(self, tmp_path, capsys):
        """Test hydrate evaluates !ev tags."""
        from alienbio.commands.hydrate import hydrate_command

        spec_dir = tmp_path / "test_spec"
        spec_dir.mkdir()
        spec_file = spec_dir / "index.yaml"
        spec_file.write_text("name: test\nvalue: !ev 2 + 2\n")

        result = hydrate_command([str(spec_dir), "--seed", "42"])

        assert result == 0
        captured = capsys.readouterr()
        assert "name: test" in captured.out
        assert "value: 4" in captured.out                            # evaluated

    def test_hydrate_with_seed(self, tmp_path, capsys):
        """Test hydrate with --seed is reproducible."""
        from alienbio.commands.hydrate import hydrate_command

        spec_dir = tmp_path / "test_spec"
        spec_dir.mkdir()
        spec_file = spec_dir / "index.yaml"
        spec_file.write_text("value: !ev 10 * 10\n")

        hydrate_command([str(spec_dir), "--seed", "42"])
        out1 = capsys.readouterr().out

        hydrate_command([str(spec_dir), "--seed", "42"])
        out2 = capsys.readouterr().out

        assert out1 == out2                                          # reproducible


# -----------------------------------------------------------------------------
# Evaluable and Reference method tests
# -----------------------------------------------------------------------------


class TestEvaluableMethod:
    """Tests for Evaluable.evaluate() method."""

    def test_evaluable_evaluate_simple(self):
        """Test Evaluable.evaluate() with simple expression."""
        from alienbio import Evaluable

        ev = Evaluable(source="2 + 3")
        result = ev.evaluate()
        assert result == 5

    def test_evaluable_evaluate_with_namespace(self):
        """Test Evaluable.evaluate() with namespace."""
        from alienbio import Evaluable

        ev = Evaluable(source="x * y")
        result = ev.evaluate({"x": 3, "y": 4})
        assert result == 12

class TestReferenceMethod:
    """Tests for Reference.resolve() method."""

    def test_reference_resolve_simple(self):
        """Test Reference.resolve() with simple name."""
        from alienbio import Reference

        ref = Reference(name="x")
        result = ref.resolve({"x": 42})
        assert result == 42

    def test_reference_resolve_dotted(self):
        """Test Reference.resolve() with dotted path."""
        from alienbio import Reference

        ref = Reference(name="config.timeout")
        result = ref.resolve({"config": {"timeout": 30}})
        assert result == 30

    def test_reference_resolve_missing_raises(self):
        """Test Reference.resolve() raises KeyError for missing name."""
        from alienbio import Reference
        import pytest

        ref = Reference(name="missing")
        with pytest.raises(KeyError):
            ref.resolve({})

