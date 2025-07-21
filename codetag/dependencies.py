# codetag/dependencies.py
"""Light-weight helpers to discover dependency declarations in a project.

Currently supports:
• requirements.txt       (pip)
• pyproject.toml         (PEP 621 / Poetry)
• package.json           (npm / yarn / pnpm)

The parser purposefully stays lenient – we do *not* resolve versions nor
handle complex marker syntax; we only surface *dependency names* so the
analytics layer can flag what external libraries a repository relies on.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional
import re  # NEW: for robust splitting

try:
    import tomllib as tomli  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover – fallback for <3.11
    import tomli  # type: ignore

__all__ = [
    "scan_for_dependencies",
]

# ---------------------------------------------------------------------------
# Helpers / constants
# ---------------------------------------------------------------------------

# Regex to split a requirement line at the first occurrence of a version
# specifier operator, whitespace, or an inline comment.  This supports the
# majority of PEP 440 specifiers without having to fully parse them.
_REQ_SPLIT_RE = re.compile(r"[=<>!~#\s]")


# ---------------------------------------------------------------------------
# Individual file parsers
# ---------------------------------------------------------------------------


def _strip_comments(lines: List[str]) -> List[str]:
    return [ln for ln in lines if ln and not ln.lstrip().startswith("#")]


def parse_requirements_txt(path: Path) -> Optional[List[str]]:
    if not path.is_file():
        return None
    try:
        lines = _strip_comments(path.read_text("utf-8").splitlines())

        deps: List[str] = []
        for raw in lines:
            line = raw.strip()
            if not line:
                # skip empty lines that may have slipped through
                continue

            # Split once on the first delimiter and take the package part.
            name_part = _REQ_SPLIT_RE.split(line, maxsplit=1)[0].strip()
            if name_part:
                deps.append(name_part)

        return deps or None
    except (OSError, UnicodeDecodeError):
        # File unreadable or encoding issue – treat as no dependencies.
        return None


def parse_pyproject_toml(path: Path) -> Optional[List[str]]:
    if not path.is_file():
        return None
    try:
        data = tomli.loads(path.read_text("utf-8"))
        deps: List[str] = []
        # PEP 621 standard location
        deps.extend(data.get("project", {}).get("dependencies", []) or [])
        # Poetry legacy location
        deps.extend(
            list(
                (
                    data.get("tool", {}).get("poetry", {}).get("dependencies", {}) or {}
                ).keys()
            )
        )
        return deps or None
    except (OSError, tomli.TOMLDecodeError):
        # File missing, permission error, or malformed TOML.
        return None


def parse_package_json(path: Path) -> Optional[List[str]]:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text("utf-8"))
        deps: List[str] = []
        deps.extend(list(data.get("dependencies", {}).keys()))
        deps.extend(list(data.get("devDependencies", {}).keys()))
        return deps or None
    except (OSError, json.JSONDecodeError):
        # File IO error or malformed JSON.
        return None


# ---------------------------------------------------------------------------
# Public orchestrator
# ---------------------------------------------------------------------------


def scan_for_dependencies(root_path: Path) -> Dict[str, List[str]]:
    """Return mapping of dependency-file name → list of packages discovered."""

    found: Dict[str, List[str]] = {}

    req_deps = parse_requirements_txt(root_path / "requirements.txt")
    if req_deps:
        found["requirements.txt"] = req_deps

    pyproject_deps = parse_pyproject_toml(root_path / "pyproject.toml")
    if pyproject_deps:
        found["pyproject.toml"] = pyproject_deps

    packagejson_deps = parse_package_json(root_path / "package.json")
    if packagejson_deps:
        found["package.json"] = packagejson_deps

    return found
