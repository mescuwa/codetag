from pathlib import Path
from typing import List

from codetag.todos import scan_for_todos


def test_scan_for_todos(tmp_path: Path):
    """Ensure TODO/FIXME detection works across multiple files."""
    file1_content = """
# TODO: Refactor this entire module.
# fixme: This is a bit of a hack.
# another line
"""
    file2_content = """
// another todo to fix later
// TODO: Add more tests.
"""
    file3_content = "no comments here"

    file1 = tmp_path / "file1.py"
    file2 = tmp_path / "file2.js"
    file3 = tmp_path / "file3.txt"

    file1.write_text(file1_content)
    file2.write_text(file2_content)
    file3.write_text(file3_content)

    all_files: List[Path] = [file1, file2, file3]

    results = scan_for_todos(all_files)

    assert results["todo_count"] == 3
    assert results["fixme_count"] == 1


def test_scan_with_no_matches(tmp_path: Path):
    """No TODO/FIXME comments should result in zero counts."""
    file1 = tmp_path / "clean_code.py"
    file1.write_text("print('all good')")

    results = scan_for_todos([file1])

    assert results["todo_count"] == 0
    assert results["fixme_count"] == 0 