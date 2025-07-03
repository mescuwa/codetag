from pathlib import Path

from codetag.language_stats import analyze_file_stats


def test_analyze_python_file(tmp_path: Path):
    """Analyze a small Python file and verify counts."""
    py_content = """
# This is a full-line comment.
import os

class MyClass:  # This is an inline comment, we count it as code.
    def method(self):
        print("Hello, World!") # Another code line

# Another comment.

"""
    test_file = tmp_path / "test_script.py"
    test_file.write_text(py_content)

    stats = analyze_file_stats(test_file)

    assert stats is not None
    assert stats.language == "Python"
    assert stats.code == 4  # import, class, def, print
    assert stats.blank == 4  # first blank, two mids, and final blank
    assert stats.comment == 2  # two full-line comments


def test_unrecognized_file_type(tmp_path: Path):
    """Files with unknown extensions should return *None*."""
    test_file = tmp_path / "document.custom"
    test_file.write_text("some data")

    stats = analyze_file_stats(test_file)
    assert stats is None 