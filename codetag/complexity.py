# codetag/complexity.py
"""Compute cyclomatic complexity metrics using *radon*.

The helper purposely focuses on Python files; support for other languages can
be layered later by calling external tools.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from radon.visitors import ComplexityVisitor
except ImportError:  # pragma: no cover – radon not installed
    ComplexityVisitor = None  # type: ignore

__all__ = [
    "analyze_complexity",
]


def analyze_complexity(file_path: Path) -> Optional[List[Dict[str, Any]]]:
    """Return per-function complexity for a *Python* file.

    Each dict contains: name, lineno, complexity.
    Returns *None* if the file is not Python or if radon is unavailable.
    """

    if file_path.suffix.lower() != ".py" or ComplexityVisitor is None:
        return None

    try:
        source = file_path.read_text("utf-8", errors="ignore")
    except (OSError, UnicodeDecodeError):
        return None

    try:
        visitor = ComplexityVisitor.from_code(source)
    except Exception:
        return None

    results: List[Dict[str, Any]] = []
    for func in visitor.functions:
        results.append(
            {
                "name": func.name,
                "lineno": func.lineno,
                "complexity": func.complexity,
            }
        )
    return results or None
