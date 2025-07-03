# """Command-line interface for CodeTag with structured JSON output."""

import json
import time
from pathlib import Path
from typing import List, Dict, Optional

import typer
from pydantic import BaseModel, Field

from .fs_tree import build_fs_tree, FsNode
from .language_stats import analyze_file_stats, FileStats
from .todos import scan_for_todos
from .important import find_key_files
from .licensing import activate_license, validate_license

__version__ = "1.0.0"

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class LargestFile(BaseModel):
    path: str
    size_bytes: int


class AnalysisMetadata(BaseModel):
    report_version: str = "1.0"
    timestamp: str = Field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ"))
    analysis_duration_seconds: float


class RepositorySummary(BaseModel):
    total_files: int = 0
    total_lines_of_code: int = 0
    primary_language: Optional[str] = None
    language_stats: Dict[str, int] = Field(default_factory=dict)


class KeyFiles(BaseModel):
    largest_files: List[LargestFile] = Field(default_factory=list)
    important_files_detected: List[str] = Field(default_factory=list)


class CodeInsights(BaseModel):
    todo_count: int = 0
    fixme_count: int = 0


class AnalysisReport(BaseModel):
    analysis_metadata: AnalysisMetadata
    repository_summary: RepositorySummary
    directory_tree: List[FsNode]
    key_files: KeyFiles = Field(default_factory=KeyFiles)
    code_insights: CodeInsights = Field(default_factory=CodeInsights)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_all_files_from_tree(nodes: List[FsNode], prefix: Path) -> List[Path]:
    """Flatten *nodes* into a list of file paths under *prefix*."""

    files: List[Path] = []
    for node in nodes:
        current = prefix / node["name"]
        if node["type"] == "file":
            files.append(current)
        elif node["type"] == "directory" and node["children"] is not None:
            files.extend(_get_all_files_from_tree(node["children"], current))
    return files


# ---------------------------------------------------------------------------
# CLI application
# ---------------------------------------------------------------------------

def version_callback(value: bool):
    if value:
        typer.echo(f"CodeTag Version: {__version__}")
        raise typer.Exit()

app = typer.Typer(
    help="CodeTag: Quickly understand a codebase via a JSON report.",
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
)

# --- root callback to expose global --version flag ---

@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show the application's version and exit.",
        callback=version_callback,
        is_eager=True,
    )
):
    """CodeTag: Quickly understand a codebase via a JSON report."""
    pass


@app.command()
def activate(
    key: str = typer.Argument(..., help="Your purchased license key."),
    email: str = typer.Argument(..., help="The email used during purchase."),
):
    """Activate a CodeTag Pro license."""

    activate_license(key, email)


@app.command(name="scan")
def scan_repository(
    path: Path = typer.Argument(..., exists=True, resolve_path=True, help="Directory to analyze."),
    include_hidden: bool = typer.Option(False, "-i", "--include-hidden", help="Include hidden files."),
    output_file: Optional[Path] = typer.Option(None, "-o", "--output", help="Save the JSON report here."),
):
    """Analyze *path* and produce a JSON summary on stdout or *output_file*."""

    license_data = validate_license()
    if license_data:
        typer.echo("✅ Pro license active.", err=True)
    else:
        typer.echo(
            "ℹ️  Running in community mode. Activate a license for full features.",
            err=True,
        )

    start = time.time()
    typer.echo(f"🔍 Analyzing repository at: {path}", err=True)

    # 1. Build directory tree & derive file list
    tree = build_fs_tree(path, include_hidden=include_hidden)
    all_files = _get_all_files_from_tree(tree, path)

    # 2. Repository summary – language stats
    repo_summary = RepositorySummary(total_files=len(all_files))
    lang_loc: Dict[str, int] = {}
    for f in all_files:
        stats: Optional[FileStats] = analyze_file_stats(f)
        if stats:
            lang_loc[stats.language] = lang_loc.get(stats.language, 0) + stats.code
    repo_summary.language_stats = lang_loc
    repo_summary.total_lines_of_code = sum(lang_loc.values())
    if lang_loc:
        repo_summary.primary_language = max(lang_loc, key=lang_loc.get)

    # 3. TODO / FIXME detection
    todo_res = scan_for_todos(all_files)
    code_insights = CodeInsights(**todo_res)

    # 4. Key files (largest + heuristics)
    key_files_res = find_key_files(all_files, path, top_n=10)
    key_files = KeyFiles(**key_files_res)

    # 5. Assemble report
    metadata = AnalysisMetadata(analysis_duration_seconds=round(time.time() - start, 2))
    report = AnalysisReport(
        analysis_metadata=metadata,
        repository_summary=repo_summary,
        directory_tree=tree,
        key_files=key_files,
        code_insights=code_insights,
    )

    out_json = report.model_dump_json(indent=2)
    if output_file:
        output_file.write_text(out_json)
        typer.echo(f"✅ Report saved to: {output_file}", err=True)
    else:
        print(out_json)


# ---------------------------------------------------------------------------
# pack command
# ---------------------------------------------------------------------------


@app.command()
def pack(
    path: Path = typer.Argument(..., exists=True, resolve_path=True, help="Path to the project directory."),
    output_file: Path = typer.Option(..., "-o", "--output", help="Path to save the packed text file."),
    max_file_size_kb: int = typer.Option(100, help="Maximum size (in KB) of a single file to include."),
    exclude_extensions: str = typer.Option(
        ".lock,.json,.map,.min.js",
        help="Comma-separated list of file extensions to exclude (include the leading dot).",
    ),
):
    """Pack source code into a single plaintext file for easy AI consumption *(Pro feature)*.

    The packing process respects `.gitignore` rules via :pyfunc:`build_fs_tree`,
    skips files exceeding *max_file_size_kb*, and excludes any file whose suffix
    matches one of *exclude_extensions*.
    """

    # -------------------------------------------------------------------
    # License gating – only available to Pro users
    # -------------------------------------------------------------------

    license_data = validate_license()
    if not license_data:
        typer.echo("❌ ERROR: The 'pack' command is a Pro feature.", err=True)
        typer.echo(
            "Please activate a license to use it: codetag activate <key> <email>",
            err=True,
        )
        raise typer.Exit(code=1)

    typer.echo("✅ Pro license active. Starting pack operation.", err=True)

    start_time = time.time()
    typer.echo(f"📦 Packing repository at: {path}", err=True)

    # 1. Build directory tree & derive list of candidate files
    tree = build_fs_tree(path, include_hidden=False)
    all_files = _get_all_files_from_tree(tree, path)

    # 2. Parse extension blacklist
    blacklist = {
        ext.strip().lower() if ext.strip().startswith(".") else f".{ext.strip().lower()}"
        for ext in exclude_extensions.split(",")
        if ext.strip()
    }

    max_bytes = max_file_size_kb * 1024

    included_files: List[Path] = []
    for f in all_files:
        # Extension filter
        if f.suffix.lower() in blacklist:
            continue

        # Size filter (ignore errors when stat fails)
        try:
            if f.stat().st_size > max_bytes:
                continue
        except (OSError, FileNotFoundError):
            continue

        included_files.append(f)

    if not included_files:
        typer.echo("⚠️  No files matched the given criteria. Nothing to pack.", err=True)
        raise typer.Exit(code=1)

    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with output_file.open("w", encoding="utf-8", errors="replace") as out_fp:
        for f in included_files:
            rel = f.relative_to(path)
            out_fp.write(f"--- FILE: {rel} ---\n")
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
            except Exception:
                # If reading fails, skip the file but note it in the output
                out_fp.write("[Error reading file]\n\n")
                continue
            out_fp.write(content)
            if not content.endswith("\n"):
                out_fp.write("\n")
            # Add an extra newline to separate files
            out_fp.write("\n")

    duration = round(time.time() - start_time, 2)
    typer.echo(
        f"✅ Packed {len(included_files)} files into {output_file} in {duration}s.",
        err=True,
    )


if __name__ == "__main__":  # pragma: no cover
    app() 