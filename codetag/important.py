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
    """Load detection rules from *rules.yaml* located next to this file."""

    rules_path = Path(__file__).with_name("rules.yaml")
    try:
        with rules_path.open("r", encoding="utf-8") as fp:
            data = yaml.safe_load(fp) or {}
            # Normalise all rule lists to lower-cased strings for case-insensitive
            # comparison later.
            for key in ("important_filenames", "important_suffixes", "important_substrings"):
                if key in data and isinstance(data[key], list):
                    data[key] = [str(item).lower() for item in data[key]]
            return data
    except (OSError, yaml.YAMLError):
        # Fallback to empty rule-set when file missing/corrupt.
        return {}


# ---------------------------------------------------------------------------
# Core helper
# ---------------------------------------------------------------------------

def find_key_files(
    file_paths: List[Path],
    *,
    top_n: int = 5,
    root_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Return the *top_n* largest files and a list of important files.

    Parameters
    ----------
    file_paths
        All files within the repository.
    top_n
        Number of largest files to include.
    root_dir
        Base directory for relative paths.  Defaults to the common path of
        *file_paths* or the current working directory if indeterminable.
    """

    if root_dir is None:
        try:
            root_dir = Path(os.path.commonpath([str(p) for p in file_paths]))
        except ValueError:
            root_dir = Path.cwd()

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
            rel_path = str(path.relative_to(root_dir))
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
            rel = str(p.relative_to(root_dir))
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