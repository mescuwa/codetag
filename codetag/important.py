"""Identify "important" files in a repository based on simple heuristics.

The rules are defined in *rules.yaml* bundled alongside this module.  They are
split into three categories:

* **important_filenames**     – exact (case-insensitive) filename matches.
* **important_suffixes**      – file extensions (including leading dot).
* **important_substrings**    – substrings that appear anywhere in the filename.

The public helper :func:`find_key_files` additionally reports the *N* largest
files in the repository.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple, Optional

import yaml

__all__ = ["find_key_files"]


# ---------------------------------------------------------------------------
# Rules loading
# ---------------------------------------------------------------------------

def _load_rules() -> Dict[str, List[str]]:
    """Load detection rules from *rules.yaml* bundled with this module.

    When running as normal Python code, the file sits next to *important.py* 🐍.
    Inside a PyInstaller-built executable the module is extracted into a
    temporary directory and `__file__` points there – but the data file may be
    located inside the application bundle.  Using ``importlib.resources`` takes
    care of both scenarios.
    """

    try:
        # Python ≥3.9 – *files* returns a Traversable object we can navigate.
        from importlib import resources as importlib_resources  # type: ignore

        if hasattr(importlib_resources, "files"):
            rules_text = (importlib_resources.files(__package__)  # type: ignore[arg-type]
                          / "rules.yaml").read_text("utf-8")
        else:  # pragma: no cover – fallback for Python <3.9 (unlikely here)
            with importlib_resources.open_text(__package__, "rules.yaml", encoding="utf-8") as fp:  # type: ignore[arg-type]
                rules_text = fp.read()

        data = yaml.safe_load(rules_text) or {}
    except (FileNotFoundError, OSError, ImportError, yaml.YAMLError):
        # Fall back to classic path-based loading – may still work in non-frozen
        # environments or when importlib.resources is unavailable.
        try:
            rules_path = Path(__file__).with_name("rules.yaml")
            with rules_path.open("r", encoding="utf-8") as fp:
                data = yaml.safe_load(fp) or {}
        except (OSError, yaml.YAMLError):
            return {}

    # ---------------------------------------------------------------------
    # Normalise all rule lists to lower-cased strings for case-insensitive
    # comparison later on.
    # ---------------------------------------------------------------------
    for key in ("important_filenames", "important_suffixes", "important_substrings"):
        if key in data and isinstance(data[key], list):
            data[key] = [str(item).lower() for item in data[key]]

    return data


# ---------------------------------------------------------------------------
# Core helper
# ---------------------------------------------------------------------------

def find_key_files(
    file_paths: List[Path],
    root_path: Path,
    *,
    top_n: int = 5,
) -> Dict[str, Any]:
    """Return the *top_n* largest files and a list of important files.

    *root_path* is used to produce relative paths for reporting.
    """

    rules = _load_rules()
    important_filenames: Set[str] = set(rules.get("important_filenames", []))
    important_suffixes: Set[str] = set(rules.get("important_suffixes", []))
    important_substrings: List[str] = list(rules.get("important_substrings", []))

    # --------------------------------- largest files ---------------------------------
    file_size_pairs: List[Tuple[int, Path]] = []
    for p in file_paths:
        try:
            file_size_pairs.append((p.stat().st_size, p))
        except OSError:
            continue

    file_size_pairs.sort(key=lambda t: t[0], reverse=True)
    largest_files_report: List[Dict[str, Any]] = []
    for size, path in file_size_pairs[:max(0, top_n)]:
        try:
            rel_path = str(path.relative_to(root_path))
        except ValueError:
            rel_path = str(path)
        largest_files_report.append({"path": rel_path, "size_bytes": size})

    # -------------------------------- important heuristic ----------------------------
    detected: Set[str] = set()
    for p in file_paths:
        name_lower = p.name.lower()
        suffix_lower = p.suffix.lower()

        rel: str
        try:
            rel = str(p.relative_to(root_path))
        except ValueError:
            rel = str(p)

        # Exact filename rule
        if name_lower in important_filenames:
            detected.add(rel)
            continue
        # Extension rule
        if suffix_lower in important_suffixes:
            detected.add(rel)
            continue
        # Substring rule
        for sub in important_substrings:
            if sub in name_lower:
                detected.add(rel)
                break

    return {
        "largest_files": largest_files_report,
        "important_files_detected": sorted(detected),
    } 