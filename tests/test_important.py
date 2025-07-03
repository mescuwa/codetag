from pathlib import Path

from codetag.important import find_key_files


def test_find_key_files(tmp_path: Path):
    """Verify largest-files and rule-based important file detection."""
    # Directory structure
    (tmp_path / "src").mkdir()
    (tmp_path / "config").mkdir()

    # Create files with controlled sizes
    (tmp_path / "README.md").write_text("a" * 100)  # 100 bytes
    (tmp_path / "src" / "main.py").write_text("b" * 500)  # 500 bytes – should be largest
    (tmp_path / "src" / "utils.py").write_text("c" * 50)  # 50 bytes
    (tmp_path / "Dockerfile").write_text("d" * 200)  # 200 bytes
    (tmp_path / "config" / "settings.ini").write_text("e" * 300)  # 300 bytes

    all_files = [p for p in tmp_path.rglob("*") if p.is_file()]

    results = find_key_files(all_files, tmp_path, top_n=3)

    # Largest files order
    largest = results["largest_files"]
    assert [item["path"] for item in largest] == [
        "src/main.py",
        "config/settings.ini",
        "Dockerfile",
    ]

    # Important file detection
    important = set(results["important_files_detected"])
    expected = {"README.md", "Dockerfile", "src/main.py", "config/settings.ini"}
    assert important == expected 