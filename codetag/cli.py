# """Command-line interface for CodeTag with structured JSON output."""

import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

import typer
from pydantic import BaseModel, Field

from .fs_tree import build_fs_tree, FsNode
# --- Imports -------------------------------------------------------------
# Language and line statistics
from .language_stats import analyze_file_stats, FileStats
# TODO/FIXME scanner
from .todos import scan_for_todos
# Key‐file heuristics
from .important import find_key_files

# --- Pydantic Models --------------------------------------------------------

class AnalysisMetadata(BaseModel):
    report_version: str = "1.0"
    timestamp: str = Field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ"))
    analysis_duration_seconds: float


class RepositorySummary(BaseModel):
    total_files: int = 0
    total_lines_of_code: int = 0
    primary_language: Optional[str] = None
    language_stats: Dict[str, int] = Field(default_factory=dict)


class LargestFile(BaseModel):
    path: str
    size_bytes: int


class KeyFiles(BaseModel):
    largest_files: List[LargestFile] = Field(default_factory=list)
    important_files_detected: List[str] = Field(default_factory=list)


class CodeInsights(BaseModel):
    todo_count: int = 0  # Placeholder for now
    fixme_count: int = 0  # Placeholder for now


class AnalysisReport(BaseModel):
    analysis_metadata: AnalysisMetadata
    repository_summary: RepositorySummary
    directory_tree: List[FsNode]
    key_files: KeyFiles = Field(default_factory=KeyFiles)
    code_insights: CodeInsights = Field(default_factory=CodeInsights)


# --- CLI --------------------------------------------------------------------

app = typer.Typer(
    help="CodeTag: A CLI tool to quickly understand a new codebase by generating a structured JSON report."
)


@app.command(name="scan")
def scan_repository(
    path: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help="The path to the directory to analyze.",
    ),
    include_hidden: bool = typer.Option(
        False, "-i", "--include-hidden", help="Include hidden files and directories (e.g., .git)."
    ),
    output_file: Optional[Path] = typer.Option(
        None, "-o", "--output", help="Path to save the JSON report. Prints to stdout if not provided."
    ),
):
    """Analyze *path* and output a JSON summary of the repository."""

    start_time = time.time()
    typer.echo(f"🔍 Analyzing repository at: {path}", err=True)

    # 1. Build directory tree (wrap root node in a list to match model)
    root_node = build_fs_tree(path, include_hidden=include_hidden)
    directory_tree: List[FsNode] = [root_node]

    # Gather all files once so we can reuse the list for multiple analyses
    repo_summary = RepositorySummary()

    all_files: List[Path] = [p for p in path.rglob("**/*") if p.is_file()]
    if not include_hidden:
        all_files = [f for f in all_files if not any(part.startswith(".") for part in f.parts)]

    repo_summary.total_files = len(all_files)

    lang_loc_map: Dict[str, int] = {}

    for file in all_files:
        if file.is_file():
            stats: Optional[FileStats] = analyze_file_stats(file)
            if stats:
                lang_loc_map[stats.language] = lang_loc_map.get(stats.language, 0) + stats.code

    repo_summary.language_stats = lang_loc_map
    repo_summary.total_lines_of_code = sum(lang_loc_map.values())
    if lang_loc_map:
        repo_summary.primary_language = max(lang_loc_map, key=lang_loc_map.get)

    # 3. Scan for TODO / FIXME occurrences across the repository
    todo_results = scan_for_todos(all_files)
    code_insights = CodeInsights(
        todo_count=todo_results.get("todo_count", 0),
        fixme_count=todo_results.get("fixme_count", 0),
    )

    # 4. Identify key files (largest / heuristically important)
    key_files_result = find_key_files(all_files, top_n=10, root_dir=path)
    key_files = KeyFiles(
        largest_files=[LargestFile(**entry) for entry in key_files_result.get("largest_files", [])],
        important_files_detected=key_files_result.get("important_files_detected", []),
    )

    # 5. Assemble full report
    duration = time.time() - start_time
    metadata = AnalysisMetadata(analysis_duration_seconds=round(duration, 2))

    report = AnalysisReport(
        analysis_metadata=metadata,
        repository_summary=repo_summary,
        directory_tree=directory_tree,
        key_files=key_files,
        code_insights=code_insights,
    )

    output_json = report.model_dump_json(indent=2)

    # 4. Output handling
    if output_file:
        output_file.write_text(output_json)
        typer.echo(f"✅ Report saved to: {output_file}", err=True)
    else:
        print(output_json)


if __name__ == "__main__":  # pragma: no cover
    app() 