from pathlib import Path

import pytest

from codetag.fs_tree import build_fs_tree


def test_build_fs_tree_basic(tmp_path: Path):
    """The tree should list files and directories at the root level."""
    # Arrange
    (tmp_path / "dir").mkdir()
    (tmp_path / "dir" / "file.txt").write_text("hello")
    (tmp_path / "root_file.py").write_text("print('hi')")

    # Act
    tree = build_fs_tree(tmp_path)

    # Assert – tree is now a list of top-level entries
    names = {node["name"] for node in tree}
    assert names == {"dir", "root_file.py"}

    dir_node = next(n for n in tree if n["name"] == "dir")
    assert dir_node["type"] == "directory"
    assert len(dir_node["children"]) == 1
    child = dir_node["children"][0]
    assert child["name"] == "file.txt"
    assert child["type"] == "file"


def test_hidden_files_are_skipped(tmp_path: Path):
    """Hidden files should be excluded unless *include_hidden* is True."""
    # Arrange
    (tmp_path / ".hidden").write_text("secret")

    # Act & Assert
    tree_default = build_fs_tree(tmp_path)
    names_default = {node["name"] for node in tree_default}
    assert ".hidden" not in names_default

    tree_include = build_fs_tree(tmp_path, include_hidden=True)
    names_include = {node["name"] for node in tree_include}
    assert ".hidden" in names_include 