# codetag/metrics.py
"""Advanced per-file metrics leveraging *radon* (cyclomatic + Halstead)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

try:
    from radon.visitors import ComplexityVisitor  # type: ignore
    from radon.metrics import h_visit  # type: ignore
except ModuleNotFoundError:  # pragma: no cover – allow running without radon
    ComplexityVisitor = None  # type: ignore
    h_visit = None  # type: ignore

__all__ = ["analyze_python_file_metrics"]


def analyze_python_file_metrics(file_path: Path) -> Optional[Dict[str, Any]]:
    """Return complexity / Halstead metrics for a single Python file.

    Keys returned:
        function_count
        average_complexity
        total_complexity
        halstead_volume
        halstead_effort
    Returns ``None`` for non-Python files or on processing error.
    """

    if file_path.suffix.lower() != ".py":
        return None

    try:
        content = file_path.read_text("utf-8", errors="ignore")
    except (OSError, UnicodeDecodeError):
        return None

    if not content.strip():
        return None

    # Skip analysis if *radon* dependency is missing
    if ComplexityVisitor is None or h_visit is None:
        return None

    try:
        visitor = ComplexityVisitor.from_code(content)
        hs_total = h_visit(content).total
    except Exception:  # pragma: no cover – radon parsing errors
        return None

    total_complexity = sum(f.complexity for f in visitor.functions)
    avg_complexity = (
        total_complexity / len(visitor.functions) if visitor.functions else 0.0
    )

    return {
        "function_count": len(visitor.functions),
        "average_complexity": avg_complexity,
        "total_complexity": total_complexity,
        "halstead_volume": hs_total.volume,
        "halstead_effort": hs_total.effort,
    } 