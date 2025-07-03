# file: tests/test_cli.py

from unittest.mock import patch
from pathlib import Path

from typer.testing import CliRunner

from codetag.cli import app

# ---------------------------------------------------------------------------
# CLI test harness
# ---------------------------------------------------------------------------

runner = CliRunner()


def test_scan_command_runs_successfully(tmp_path: Path):
    """Smoke test: ensure `scan` runs and produces JSON on stdout."""

    # Create a dummy file so the directory is not empty
    (tmp_path / "test.txt").write_text("hello")

    result = runner.invoke(app, ["scan", str(tmp_path)])

    assert result.exit_code == 0, result.stderr
    # Should contain JSON keys from the report
    assert "repository_summary" in result.output
    # Community mode banner expected because no license is present
    assert "Running in community mode" in result.output


def test_pack_command_fails_without_license(tmp_path: Path):
    """`pack` must be gated – expect failure when no license is present."""

    with patch("codetag.cli.validate_license", return_value=None):
        result = runner.invoke(app, [
            "pack",
            str(tmp_path),
            "-o",
            str(tmp_path / "out.txt"),
        ])

    assert result.exit_code == 1
    assert "ERROR: The 'pack' command is a Pro feature." in result.output
    assert "Please activate a license" in result.output


def test_pack_command_succeeds_with_license(tmp_path: Path):
    """`pack` should succeed when a valid license is detected."""

    # Prepare minimal project with a single source file
    source = tmp_path / "code.py"
    source.write_text("# My awesome code\n")
    output_file = tmp_path / "context.txt"

    with patch("codetag.cli.validate_license", return_value={"mock": "license"}):
        result = runner.invoke(app, [
            "pack",
            str(tmp_path),
            "-o",
            str(output_file),
        ])

    assert result.exit_code == 0, result.stderr
    assert "Pro license active" in result.output
    assert output_file.exists()
    packed_text = output_file.read_text()
    assert "--- FILE: code.py ---" in packed_text 