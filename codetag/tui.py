# FILE: codetag/tui.py

"""Rich Text-User Interface (TUI) for **CodeTag**.

Major UX highlights
-------------------
* Branded banner with version & author.
* Persistent history for last repo/output dirs.
* Optional GUI picker with `CODETAG_NOGUI=1` fallback.
* Path autocompletion + `~` expansion.
* Progress spinners & success panels.
* Syntax-highlighted *command echo*.
* Two-step output-file flow (dir → filename) to avoid `~` bugs.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Optional, Callable, Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from prompt_toolkit.completion import PathCompleter
from prompt_toolkit.shortcuts import (
    checkboxlist_dialog,
    input_dialog,
    message_dialog,
    radiolist_dialog,
)
from prompt_toolkit.styles import Style
from prompt_toolkit.validation import ValidationError, Validator
import inspect

# ---------------------------------------------------------------------------
# Globals & config
# ---------------------------------------------------------------------------

console = Console()
HISTORY_FILE = Path.home() / ".codetag_history.json"
DISABLE_GUI = os.getenv("CODETAG_NOGUI") == "1"

# ---------------------------------------------------------------------------
# Style definition
# ---------------------------------------------------------------------------

TUI_STYLE = Style.from_dict({
    "dialog": "bg:#333332",
    "dialog.body": "bg:#444442 #ffffff",
    "dialog shadow": "bg:#222222",
    "dialog.body label": "#d1d1d1",
    "button": "bg:#005555 #ffffff",
    "button.focused": "bg:#007777 #ffffff",
    "checkbox": "#00ff00",
    "radio": "#00ff00",
})

# ---------------------------------------------------------------------------
# History helpers
# ---------------------------------------------------------------------------

def _load_history() -> Dict[str, str]:
    if not HISTORY_FILE.exists():
        return {}
    try:
        return json.loads(HISTORY_FILE.read_text("utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_history(data: Dict[str, str]) -> None:
    try:
        HISTORY_FILE.write_text(json.dumps(data, indent=2), "utf-8")
    except OSError:
        # best-effort only
        pass

# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

class PathValidator(Validator):
    """Require an existing directory (expands ~)."""

    def validate(self, document):  # type: ignore[override]
        text = document.text
        if not text:
            return
        if not Path(text).expanduser().is_dir():
            raise ValidationError(message="Path is not a valid directory.")


class NumberValidator(Validator):
    def validate(self, document):  # type: ignore[override]
        if document.text and not document.text.isdigit():
            raise ValidationError(message="Please enter a valid number.")


class NonEmptyValidator(Validator):
    def validate(self, document):  # type: ignore[override]
        if not document.text.strip():
            raise ValidationError(message="This field cannot be empty.")

# ---------------------------------------------------------------------------
# Native directory picker
# ---------------------------------------------------------------------------

def _open_native_directory_picker() -> Optional[Path]:
    """Return a directory path chosen via *tkinter* file-dialog."""
    if DISABLE_GUI:
        message_dialog(
            title="GUI Disabled",
            text="Visual browsing is disabled in this environment (CODETAG_NOGUI=1).",
            style=TUI_STYLE,
        ).run()
        return None
    try:
        import tkinter as tk  # noqa: WPS433
        from tkinter import filedialog as tk_fd  # noqa: WPS433

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        chosen = tk_fd.askdirectory(title="Select a Folder")  # type: ignore[arg-type]
        root.destroy()
        return Path(chosen) if chosen else None
    except Exception:  # noqa: BLE001
        message_dialog(
            title="GUI Error",
            text="Could not open the graphical file picker.",
            style=TUI_STYLE,
        ).run()
        return None

# ---------------------------------------------------------------------------
# Path selection helpers
# ---------------------------------------------------------------------------

def _choose_directory(title: str, history_key: str, history: Dict[str, str]) -> Optional[Path]:
    """Generic directory chooser with browse/type options."""
    browse_lbl = "Browse for a folder visually" + (" (Disabled)" if DISABLE_GUI else "")
    method = radiolist_dialog(
        title=title,
        text="How would you like to select the folder?",
        values=[("browse", browse_lbl), ("type", "Type the path manually")],
        style=TUI_STYLE,
    ).run()

    if method == "browse":
        return _open_native_directory_picker()

    if method == "type":
        default = history.get(history_key, str(Path.home()))
        typed = input_dialog(
            title="Enter Folder Path",
            text="Enter the full directory path:",
            default=default,
            completer=PathCompleter(expanduser=True),
            validator=PathValidator(),
            style=TUI_STYLE,
        ).run()
        return Path(typed).expanduser() if typed else None

    return None  # cancelled


def _get_output_path(history: Dict[str, str], step_prefix: str, default_name: str, ext: str) -> Optional[Path]:
    """Two-step flow: pick directory, then filename."""
    dir_path = _choose_directory(f"{step_prefix} – Select Output Directory", "last_output_dir", history)
    if not dir_path:
        return None

    # store history immediately so filename dialog default can use it next time
    history["last_output_dir"] = str(dir_path)

    filename = input_dialog(
        title=f"{step_prefix} – Enter Filename",
        text=f"Enter the filename (.{ext} will be added automatically):",
        default=default_name,
        validator=NonEmptyValidator(),
        style=TUI_STYLE,
    ).run()
    if not filename:
        return None

    return dir_path / f"{filename.strip()}.{ext}"

# ---------------------------------------------------------------------------
# Command echo
# ---------------------------------------------------------------------------

def _echo_command(cmd: str, args: Dict[str, Any]) -> None:
    """Generate an accurate shell command reflecting the current CLI definition."""
    from typer.models import ArgumentInfo, OptionInfo  # type: ignore
    from . import cli  # local import to avoid circular issues

    # Resolve the callback function for the given CLI command name.
    func = None
    if hasattr(cli, cmd):
        func = getattr(cli, cmd)  # type: ignore[attr-defined]
    else:
        for cinfo in getattr(cli.app, "registered_commands", []):
            if cinfo.name == cmd or cinfo.callback.__name__ == cmd:
                func = cinfo.callback
                break

    parts: list[str] = ["codetag", cmd]

    if func is None:
        # Fallback to naive behaviour.
        for key, val in args.items():
            if val in (None, False):
                continue
            flag = f"--{key.replace('_', '-')}"
            if val is True:
                parts.append(flag)
            else:
                parts.extend([flag, f'"{val}"'])
    else:
        import inspect as _ins
        sig = _ins.signature(func)
        for name, param in sig.parameters.items():
            if name not in args:
                continue
            val = args[name]
            if val in (None, False):
                continue

            default = param.default
            if isinstance(default, ArgumentInfo):
                parts.append(f'"{val}"')
                continue

            if isinstance(default, OptionInfo):
                long_opt = None
                if default.param_decls:
                    long_opt = next((d for d in default.param_decls if d.startswith("--")), default.param_decls[0])
                if long_opt is None:
                    long_opt = f"--{name.replace('_', '-')}"

                if isinstance(val, bool):
                    all_decls: list[str] = []
                    for decl in default.param_decls:
                        if "/" in decl:
                            all_decls.extend(decl.split("/"))
                        else:
                            all_decls.append(decl)
                    positive = next((d for d in all_decls if d.startswith("--") and not d.startswith("--no-")), None)
                    negative = next((d for d in all_decls if d.startswith("--no-")), None)
                    chosen = positive if val else (negative or positive)
                    if chosen:
                        parts.append(chosen)
                else:
                    parts.extend([long_opt, f'"{val}"'])
                continue

            flag = f"--{name.replace('_', '-')}"
            if val is True:
                parts.append(flag)
            else:
                parts.extend([flag, f'"{val}"'])

    console.print("\n[bold green]Equivalent Scriptable Command:[/bold green]")
    console.print(Syntax(" ".join(parts), "bash", theme="monokai", word_wrap=True))
    console.print()

# ---------------------------------------------------------------------------
# Utility – progress wrapper
# ---------------------------------------------------------------------------

def _run_with_progress(desc: str, func: Callable[..., Any], **kwargs) -> None:
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as prog:
        prog.add_task(description=desc, total=None)
        func(**kwargs)

# ---------------------------------------------------------------------------
# Main menu
# ---------------------------------------------------------------------------

def _select_main_action() -> Optional[str]:
    return radiolist_dialog(
        title="Step 1 – Choose Action",
        text="What would you like to do?",
        values=[
            ("scan", "Scan a repository"),
            ("pack", "Pack for LLM"),
            ("distill", "Distill a codebase"),
            ("audit", "Audit for threats"),
        ],
        style=TUI_STYLE,
    ).run()

# ---------------------------------------------------------------------------
# SCAN
# ---------------------------------------------------------------------------

def _run_scan_flow(history: Dict[str, str]) -> None:
    from .cli import scan_repository

    repo = _choose_directory("Step 2 – Select Repository", "last_repo", history)
    if not repo:
        return
    history["last_repo"] = str(repo)

    args = {
        "path": repo,
        "include_hidden": False,
        "no_cache": False,
        "output_file": None,
        "rules": None,
        "exclude_dirs": None,
        "exclude_patterns": None,
    }
    _run_with_progress("Scanning repository…", scan_repository, **args)
    console.print(Panel("[bold green]✔ Scan complete.[/bold green]", padding=1))
    _echo_command("scan", args)

# ---------------------------------------------------------------------------
# PACK
# ---------------------------------------------------------------------------

def _run_pack_flow(history: Dict[str, str]) -> None:
    from .cli import pack

    repo = _choose_directory("Step 2/3 – Select Repository", "last_repo", history)
    if not repo:
        return
    history["last_repo"] = str(repo)

    output = _get_output_path(history, "Step 3/3", "packed_code", "txt")
    if not output:
        return

    args = {
        "path": repo,
        "output_file": output,
        "max_tokens": 250_000,
        "max_file_size_kb": 100,
        "exclude_extensions": "",
        "format": "raw",
    }
    _run_with_progress("Packing repository…", pack, **args)
    console.print(Panel(f"[bold green]✔ Pack complete.[/bold green]\nSaved to [cyan]{output}[/cyan]", padding=1))
    _echo_command("pack", args)

# ---------------------------------------------------------------------------
# DISTILL
# ---------------------------------------------------------------------------

def _run_distill_flow(history: Dict[str, str]) -> None:
    from .cli import distill

    repo = _choose_directory("Step 2/4 – Select Repository", "last_repo", history)
    if not repo:
        return
    history["last_repo"] = str(repo)

    level = radiolist_dialog(
        title="Step 3/4 – Distillation Level",
        text="Select level:",
        values=[("2", "Level 2 – Structural"), ("1", "Level 1 – Cleanup")],
        style=TUI_STYLE,
    ).run()
    if not level:
        return

    output = _get_output_path(history, "Step 4/4", "distilled", "txt")
    if not output:
        return

    args = {
        "path": repo,
        "level": int(level),
        "output_file": output,
        "anchors": True,
    }
    _run_with_progress("Distilling codebase…", distill, **args)
    console.print(Panel(f"[bold green]✔ Distill complete.[/bold green]\nSaved to [cyan]{output}[/cyan]", padding=1))
    _echo_command("distill", args)

# ---------------------------------------------------------------------------
# AUDIT
# ---------------------------------------------------------------------------

def _run_audit_flow(history: Dict[str, str]) -> None:
    from .cli import audit
    import typer

    repo = _choose_directory("Step 2 – Select Repository", "last_repo", history)
    if not repo:
        return
    history["last_repo"] = str(repo)

    strict_choice = checkboxlist_dialog(
        title="Audit Options",
        text="Select options:",
        values=[("strict", "Use stricter Semgrep ruleset")],
        style=TUI_STYLE,
    ).run()
    if strict_choice is None:
        return

    args = {"path": repo, "strict": "strict" in strict_choice}
    try:
        _run_with_progress("Auditing repository…", audit, **args)
        console.print(Panel("[bold green]✔ Audit complete: No issues found.[/bold green]", padding=1))
    except typer.Exit as exc:
        if exc.exit_code == 1:
            console.print(Panel("[bold yellow]⚠ Audit finished: Potential issues found.[/bold yellow]", padding=1))
        else:
            raise
    _echo_command("audit", args)

# ---------------------------------------------------------------------------
# Launcher
# ---------------------------------------------------------------------------

def run_tui() -> None:  # pragma: no cover
    from . import __version__

    console.print(
        Panel.fit(
            f"[bold magenta]CodeTag[/bold magenta] v{__version__}",
            title="[dim]Lumina Mescuwa[/dim]",
            padding=(1, 5),
            style="magenta",
        )
    )
    console.print()

    history = _load_history()

    try:
        action = _select_main_action()
        flows = {
            "scan": _run_scan_flow,
            "pack": _run_pack_flow,
            "distill": _run_distill_flow,
            "audit": _run_audit_flow,
        }
        if action in flows:
            flows[action](history)
        else:
            console.print("[dim]Goodbye![/dim]")
    except Exception as err:  # noqa: BLE001
        message_dialog(
            title="Fatal Error",
            text=f"An unexpected error occurred:\n\n{err}",
            style=TUI_STYLE,
        ).run()
    finally:
        _save_history(history) 