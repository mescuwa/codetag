# file: codetag/todos.py

import re
from pathlib import Path
from typing import List, Dict
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed

# A case-insensitive regex to find TODO and FIXME markers.
TODO_REGEX = re.compile(r"\b(TODO|FIXME)\b", re.IGNORECASE)

# --- NEW: Define the threshold for switching to parallel processing ---
# If a project has more than this many files, we'll use multiprocessing.
# 50 is a reasonable default.
PARALLEL_THRESHOLD = 50


def _scan_single_file(file_path: Path) -> Counter:
    """
    Scans a single file for TODO/FIXME comments.
    This function is executed by a worker process or in a loop.
    """
    counts = Counter()
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:  # Read line by line to prevent memory exhaustion
                matches = TODO_REGEX.findall(line)
                if matches:
                    normalized_matches = (match.upper() for match in matches)
                    counts.update(normalized_matches)
    except IOError:
        # Silently ignore files that cannot be read.
        pass
    return counts


def scan_for_todos(file_paths: List[Path]) -> Dict[str, int]:
    """
    Scans a list of files for TODO/FIXME comments.

    NEW: Automatically chooses between sequential and parallel execution
    based on the number of files.
    """
    total_counts: Counter = Counter()
    num_files = len(file_paths)

    if num_files == 0:
        return {"todo_count": 0, "fixme_count": 0}

    # --- NEW: Conditional Logic ---
    if num_files < PARALLEL_THRESHOLD:
        # --- Sequential Scan for small projects ---
        # Lower overhead, faster for few files.
        for path in file_paths:
            total_counts.update(_scan_single_file(path))
    else:
        # --- Parallel Scan for large projects ---
        # Higher startup cost, but much faster for many files.
        with ProcessPoolExecutor() as executor:
            future_to_file = {
                executor.submit(_scan_single_file, path): path for path in file_paths
            }

            for future in as_completed(future_to_file):
                try:
                    result_counter = future.result()
                    total_counts.update(result_counter)
                except Exception:
                    # In a real application, we might log this error.
                    pass

    return {
        "todo_count": total_counts.get("TODO", 0),
        "fixme_count": total_counts.get("FIXME", 0),
    }


__all__ = ["scan_for_todos"]
