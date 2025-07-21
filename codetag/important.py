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

from pathlib import Path
from typing import Any, Dict, List, Set, Optional

import yaml

# Type hints for FsNode
from .fs_tree import FsNode, flatten_fs_tree

# --- NEW: Non-source extensions to exclude when selecting largest files ---
NON_SOURCE_EXTENSIONS = {
    # Data & models
    ".pt",
    ".pth",
    ".bin",
    ".onnx",
    ".safetensors",
    ".npz",
    ".npy",
    ".csv",
    ".json",
    ".parquet",
    ".pkl",
    ".joblib",
    # Logs & dumps
    ".log",
    ".txt",
    # Media
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".mp4",
    ".mp3",
    # Archives & docs
    ".zip",
    ".gz",
    ".tar",
    ".pdf",
}

__all__ = ["find_key_files"]


# ---------------------------------------------------------------------------
# Rules loading
# ---------------------------------------------------------------------------


def load_rules(custom_path: Optional[Path] = None) -> Dict[str, List[str]]:
    """Load detection rules.

    If *custom_path* is provided and points to a YAML file, rules from that file
    are **merged** with the built-in defaults (custom entries extend the
    corresponding lists).  Lists are lower-cased for case-insensitive matching.
    """

    def _normalise(rules_dict: Dict[str, List[str]]) -> None:
        for key in (
            "important_filenames",
            "important_suffixes",
            "important_substrings",
        ):
            if key in rules_dict and isinstance(rules_dict[key], list):
                rules_dict[key] = [str(item).lower() for item in rules_dict[key]]

    # 1. Bundled defaults -----------------------------------------------------
    # Importlib compatibility: Python <3.9 lacks `importlib.resources.files`.
    import importlib

    _files = None  # function reference placeholder

    # Try stdlib first (Python ≥3.9) without triggering static linters
    try:
        _files = importlib.import_module("importlib.resources").files  # type: ignore[attr-defined]
    except (ModuleNotFoundError, AttributeError):
        # Fallback to back-port for 3.8 / 3.7, if installed.
        try:
            _files = importlib.import_module("importlib_resources").files  # type: ignore[attr-defined]
        except (ModuleNotFoundError, AttributeError):
            _files = None  # type: ignore

    data: Dict[str, List[str]]
    if _files is not None:
        try:
            default_text = _files(__package__).joinpath("rules.yaml").read_text("utf-8")
            data = yaml.safe_load(default_text) or {}
        except (FileNotFoundError, yaml.YAMLError, AttributeError):
            # AttributeError catches the case where the back-port exists but the
            # function does not behave as expected.
            data = {}
    else:
        data = {}

    _normalise(data)

    # 2. User-supplied overrides ---------------------------------------------
    if custom_path and Path(custom_path).is_file():
        try:
            user_text = Path(custom_path).read_text("utf-8")
            user_rules: Dict[str, List[str]] = yaml.safe_load(user_text) or {}
            _normalise(user_rules)

            # Merge – extend defaults with user values (duplicates OK; set later)
            for key, lst in user_rules.items():
                if key in data:
                    data[key].extend(lst)
                else:
                    data[key] = lst
        except Exception:
            # If user file can't be parsed, fall back silently to defaults.
            pass

    return data


# Backwards-compat alias ------------------------------------------------------
_load_rules = load_rules


# ---------------------------------------------------------------------------
# Core helper
# ---------------------------------------------------------------------------


def find_key_files(
    tree: List[FsNode],
    root_path: Path,
    *,
    top_n: int = 5,
    rules_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Return a report of *top_n* largest files plus important files.

    The function now works directly with the rich *FsNode* tree so it can
    surface Git-LFS metadata without having to re-stat every path.
    """

    rules = load_rules(custom_path=rules_path)
    important_filenames: Set[str] = set(rules.get("important_filenames", []))
    important_suffixes: Set[str] = set(rules.get("important_suffixes", []))
    important_substrings: List[str] = list(rules.get("important_substrings", []))

    # Flatten the tree once for efficient processing
    all_files_with_meta = flatten_fs_tree(tree, with_meta=True)

    # ---------------- largest files (filtered to likely source code) ----------------
    source_files_only = [
        f
        for f in all_files_with_meta
        if Path(f["path"]).suffix.lower() not in NON_SOURCE_EXTENSIONS
    ]
    source_files_only.sort(key=lambda f: f["size_bytes"], reverse=True)
    largest_files_report: List[Dict[str, Any]] = []
    for file_info in source_files_only[: max(0, top_n)]:
        report_item = {
            "path": file_info["path"],
            "size_bytes": file_info["size_bytes"],
        }
        if file_info.get("is_lfs_pointer"):
            report_item["is_lfs"] = True
        largest_files_report.append(report_item)

    # --------------- important heuristic --------------
    detected: Set[str] = set()
    for file_info in all_files_with_meta:
        path_obj = Path(file_info["path"])
        name_lower = path_obj.name.lower()
        suffix_lower = path_obj.suffix.lower()

        # Exact filename rule
        if name_lower in important_filenames:
            detected.add(file_info["path"])
            continue
        # Extension rule
        if suffix_lower in important_suffixes:
            detected.add(file_info["path"])
            continue
        # Substring rule

        for sub in important_substrings:
            if sub in name_lower:
                detected.add(file_info["path"])
                break

    return {
        "largest_files": largest_files_report,
        "important_files_detected": sorted(detected),
    }
