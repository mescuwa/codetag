from pathlib import Path

from codetag.todos import scan_for_todos


def test_scan_for_todos(tmp_path: Path) -> None:
    """scan_for_todos should count TODO and FIXME markers correctly."""
    file1 = tmp_path / "file1.py"
    file1.write_text(("# TODO implement feature\nprint('hello')\n# FIXME fix issue\n"))

    counts = scan_for_todos([file1])
    assert counts["todo_count"] == 1
    assert counts["fixme_count"] == 1
