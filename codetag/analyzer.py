"""Central analysis engine shared by both the CLI and API layers.

This module encapsulates all heavy-lifting so that we follow the DRY
principle. The public entry-point :func:`run_analysis` performs the
same analysis that used to live in *cli.py* and *main.py*.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, Optional, List, Any, Tuple

import json
import hashlib

# In-package imports
from .fs_tree import build_fs_tree, flatten_fs_tree
from .language_stats import analyze_file_stats, FileStats
from .todos import scan_for_todos
from .important import find_key_files
from .secrets import scan_for_secrets
from .dependencies import scan_for_dependencies
from .complexity import analyze_complexity
from .metrics import analyze_python_file_metrics
from .models import (
    AnalysisReport,
    RepositorySummary,
    KeyFiles,
    CodeInsights,
    FoundSecretModel,
    AnalysisMetadata,
    DependencyInfo,
    ThreatAssessment,
    ComplexFunction,
)

# ---------------------------------------------------------------------------
# Cache helpers (extended)


def _cache_key(file_path: Path, content_hash: str) -> str:
    """Return a cache key based on the absolute path and *content_hash*."""
    # Combining both ensures cache uniqueness per file *version*.
    return hashlib.sha256(f"{file_path}:{content_hash}".encode()).hexdigest()


def _stats_from_cache(
    file_path: Path, cache_dir: Path
) -> Tuple[Optional[FileStats], Optional[Dict[str, Any]]]:
    """Return cached (FileStats, py_metrics) if an entry for *current file content* exists."""

    try:
        # Compute content hash for key
        content = file_path.read_text("utf-8", errors="ignore")
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        cache_file = cache_dir / f"{_cache_key(file_path, content_hash)}.json"

        if not cache_file.exists():
            return None, None

        data = json.loads(cache_file.read_text("utf-8"))

        # Backwards compatibility: older cache stored plain FileStats dict
        if "file_stats" in data:
            file_stats_data = data.get("file_stats")
            py_metrics = data.get("py_metrics")
        else:
            # Legacy format: entire data is FileStats
            file_stats_data = data
            py_metrics = None

        stats = FileStats(**file_stats_data) if file_stats_data else None
        return stats, py_metrics
    except Exception:
        # Treat any error as cache miss
        return None, None


def _write_cache(
    file_path: Path,
    stats: Optional[FileStats],
    py_metrics: Optional[Dict[str, Any]],
    cache_dir: Path,
) -> None:
    """Persist *stats* and *py_metrics* to disk using a key derived from content hash."""

    if not stats or not getattr(stats, "content_hash", None):
        return

    try:
        cache_file = cache_dir / f"{_cache_key(file_path, stats.content_hash)}.json"
        if cache_file.exists():
            return  # avoid redundant writes

        payload = {"file_stats": stats._asdict(), "py_metrics": py_metrics}
        cache_file.write_text(json.dumps(payload), encoding="utf-8")
    except Exception:
        # Best-effort only
        pass


# ----------------------- Analysis sub-routines -----------------------------


def _run_loc_and_metrics_analysis(
    all_files: List[Path],
    *,
    use_cache: bool,
    cache_dir: Path,
) -> Tuple[Dict[str, int], int, float]:
    """Analyzes language stats and calculates aggregate complexity metrics."""
    lang_loc: Dict[str, int] = {}
    total_complexity_sum = 0.0
    total_function_count = 0

    for f in all_files:
        if use_cache and cache_dir.exists():
            cached_stats, cached_py_metrics = _stats_from_cache(f, cache_dir)
        else:
            cached_stats, cached_py_metrics = None, None

        stats = cached_stats or analyze_file_stats(f)

        py_metrics = (
            cached_py_metrics
            if cached_py_metrics is not None
            else analyze_python_file_metrics(f)
        )

        # Update language LOC aggregation
        if stats:
            lang_loc[stats.language] = lang_loc.get(stats.language, 0) + stats.code

        # Aggregate metrics if available
        if py_metrics:
            total_function_count += py_metrics.get("function_count", 0)
            total_complexity_sum += py_metrics.get("total_complexity", 0.0)

        # Write to cache if needed (only when newly computed)
        if (
            use_cache
            and cache_dir.exists()
            and (cached_stats is None or cached_py_metrics is None)
        ):
            _write_cache(f, stats, py_metrics, cache_dir)

    return lang_loc, total_function_count, total_complexity_sum


def _run_complexity_analysis(
    all_files: List[Path],
    root_path: Path,
) -> List[Dict[str, Any]]:
    """Finds all complex functions across all files."""
    # ComplexFunction imported from centralized models
    all_complex: List[ComplexFunction] = []
    for f_path in all_files:
        comp_list = analyze_complexity(f_path)
        if comp_list:
            for c in comp_list:
                all_complex.append(
                    ComplexFunction(
                        file_path=str(f_path.relative_to(root_path)),
                        function_name=c["name"],
                        line_number=c["lineno"],
                        complexity_score=c["complexity"],
                    )
                )
    all_complex.sort(key=lambda x: x.complexity_score, reverse=True)
    return all_complex


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_analysis(
    path: Path,
    include_hidden: bool,
    max_files: int,
    *,
    rules_path: Optional[Path] = None,
    use_cache: bool = True,
    exclude_dirs: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
):
    """Run the full CodeTag analysis on *path*."""
    start = time.time()

    # 1. Build file tree and list -----------------------------------------
    tree = build_fs_tree(
        path,
        include_hidden=include_hidden,
        exclude_dirs=exclude_dirs,
        exclude_patterns=exclude_patterns,
    )
    all_files = flatten_fs_tree(tree, prefix=path)
    if len(all_files) > max_files:
        raise ValueError(
            f"Repository has {len(all_files)} files, exceeding limit of {max_files}."
        )

    # 2. Prepare cache directory ------------------------------------------
    cache_dir = path / ".codetag_cache"
    if use_cache:
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            use_cache = False  # Fallback if directory cannot be created

    # 3. Run analyses ------------------------------------------------------
    lang_loc, total_funcs, total_comp = _run_loc_and_metrics_analysis(
        all_files, use_cache=use_cache, cache_dir=cache_dir
    )
    all_complex_funcs = _run_complexity_analysis(all_files, root_path=path)
    todo_res = scan_for_todos(all_files)
    secrets = scan_for_secrets(all_files, path)
    deps_mapping = scan_for_dependencies(path)
    key_files_res = find_key_files(tree, path, top_n=10, rules_path=rules_path)

    # 4. Assemble the report ----------------------------------------------
    repo_summary = RepositorySummary(
        total_files=len(all_files),
        language_stats=lang_loc,
        total_lines_of_code=sum(lang_loc.values()),
        primary_language=max(lang_loc, key=lambda k: lang_loc.get(k, 0))
        if lang_loc
        else None,
        total_functions_found=total_funcs,
        average_cyclomatic_complexity=round(total_comp / total_funcs, 2)
        if total_funcs
        else 0.0,
    )

    code_insights = CodeInsights(
        **todo_res, top_complex_functions=all_complex_funcs[:5]
    )

    threat_assessment = ThreatAssessment(
        secrets_found=[FoundSecretModel(**s) for s in secrets]
    )

    # 5. Finalize and return ----------------------------------------------
    metadata = AnalysisMetadata(analysis_duration_seconds=round(time.time() - start, 2))
    report = AnalysisReport(
        analysis_metadata=metadata,
        repository_summary=repo_summary,
        directory_tree=tree,
        key_files=KeyFiles(**key_files_res),
        code_insights=code_insights,
        dependency_info=DependencyInfo(dependency_files_found=deps_mapping),
        threat_assessment=threat_assessment,
    )
    return report
