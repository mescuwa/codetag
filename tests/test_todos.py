# file: tests/test_todos.py

from pathlib import Path
from typing import List
from unittest.mock import patch

from codetag.todos import scan_for_todos


def test_scan_for_todos_with_multiple_files(tmp_path: Path):
    """End-to-end test on 3 files (mixed TODO/FIXME, sequential or parallel)."""

    file1_content = "# TODO: Refactor this entire module.\n# fixme: This is a hack."
    file2_content = "// another todo to fix later\n// TODO: Add more tests."

    (tmp_path / "file1.py").write_text(file1_content)
    (tmp_path / "file2.js").write_text(file2_content)
    (tmp_path / "file3.txt").write_text("no comments here")

    all_files: List[Path] = list(tmp_path.glob("*"))
    results = scan_for_todos(all_files)

    assert results["todo_count"] == 3
    assert results["fixme_count"] == 1


# ---------------------------------------------------------------------------
# Explicitly test both execution paths (sequential vs parallel)
# ---------------------------------------------------------------------------


def test_scan_triggers_sequential_path(tmp_path: Path):
    """Force the sequential branch by setting the threshold very high."""

    with patch("codetag.todos.PARALLEL_THRESHOLD", 100):
        f = tmp_path / "small_project.py"
        f.write_text("# TODO: A simple task.")

        results = scan_for_todos([f])
        assert results["todo_count"] == 1
        assert results["fixme_count"] == 0


def test_scan_triggers_parallel_path(tmp_path: Path):
    """Force the parallel branch by lowering the threshold."""

    with patch("codetag.todos.PARALLEL_THRESHOLD", 2):
        # Three files exceed the patched threshold (2)
        (tmp_path / "f1.py").write_text("# TODO 1")
        (tmp_path / "f2.py").write_text("# TODO 2")
        (tmp_path / "f3.py").write_text("# FIXME 1")

        all_files: List[Path] = list(tmp_path.glob("*"))
        results = scan_for_todos(all_files)

        assert results["todo_count"] == 2
        assert results["fixme_count"] == 1


def test_scan_with_no_matches(tmp_path: Path):
    """Scanner should return zeros when no TODO/FIXME comments found."""

    clean_file = tmp_path / "clean_code.py"
    clean_file.write_text("print('all good')")

    results = scan_for_todos([clean_file])
    assert results["todo_count"] == 0
    assert results["fixme_count"] == 0 