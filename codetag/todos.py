"""Parallel scanner for TODO / FIXME comments.

The helper :func:`scan_for_todos` accepts an iterable of :class:`pathlib.Path`
objects and returns a dictionary with the total number of *TODO* and *FIXME*
occurrences across all readable files.

A :pyclass:`concurrent.futures.ProcessPoolExecutor` is used so the scan can
scale with CPU cores.  For small file sets the overhead is minimal, and for
larger code-bases the parallelism provides a meaningful speed-up.
"""

from __future__ import annotations

import re
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Counter as CounterType, Dict, Iterable, List

# ---------------------------------------------------------------------------
# Regex pre-compiled once so each worker process just re-imports the module.
# ---------------------------------------------------------------------------

# Matches the whole words TODO or FIXME, case-insensitive.
TODO_REGEX = re.compile(r"\b(TODO|FIXME)\b", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Worker helper (must be top-level to be picklable by multiprocessing).
# ---------------------------------------------------------------------------

def _scan_single_file(file_path: Path) -> CounterType[str]:
    """Return a ``Counter`` of TODO / FIXME occurrences in *file_path*."""
    counts: CounterType[str] = Counter()

    try:
        with file_path.open("r", encoding="utf-8", errors="ignore") as fp:
            matches = TODO_REGEX.findall(fp.read())
            counts.update(match.upper() for match in matches)
    except OSError:
        # File could not be read – ignore silently.
        pass

    return counts


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scan_for_todos(file_paths: Iterable[Path]) -> Dict[str, int]:
    """Scan *file_paths* in parallel and return TODO / FIXME totals.

    The result dict has keys ``todo_count`` and ``fixme_count``.
    """

    paths: List[Path] = list(file_paths)

    # Fast-path: no files.
    if not paths:
        return {"todo_count": 0, "fixme_count": 0}

    total_counts: CounterType[str] = Counter()

    # Using a context-manager ensures the pool shuts down cleanly in tests.
    with ProcessPoolExecutor() as executor:
        future_to_path = {executor.submit(_scan_single_file, p): p for p in paths}

        for future in as_completed(future_to_path):
            try:
                total_counts.update(future.result())
            except Exception:
                # Ignore worker failures; they are unlikely but shouldn't abort
                # the entire scan.  A real implementation could log these.
                pass

    return {
        "todo_count": total_counts.get("TODO", 0),
        "fixme_count": total_counts.get("FIXME", 0),
    }


__all__ = ["scan_for_todos"] 