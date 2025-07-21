"""Configuration loading and merging utilities for CodeTag.

This helper enables per-repository defaults via a `.codetag.yaml` file
placed at the root of the project being analysed.  Each top-level key in
that YAML maps to a command name (e.g. `scan`, `pack`) and contains the
same options that would normally be provided on the command line.

Command-line flags always take precedence over values coming from the
configuration file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

CONFIG_FILENAME = ".codetag.yaml"


def load_config(repo_path: Path) -> Dict[str, Any]:
    """Load `.codetag.yaml` from *repo_path*.

    If the file does not exist or cannot be parsed, an empty ``dict`` is
    returned.  Errors are swallowed intentionally – configuration should
    never break analysis.
    """
    config_file = repo_path / CONFIG_FILENAME
    if not config_file.is_file():
        return {}

    try:
        with config_file.open("r", encoding="utf-8") as fp:
            data = yaml.safe_load(fp) or {}
            if isinstance(data, dict):
                return data
            # Malformed content – we expect a mapping at top level
            return {}
    except (yaml.YAMLError, OSError):
        # Invalid YAML or unreadable file – ignore silently
        return {}


def merge_options(
    config: Dict[str, Any],
    command: str,
    cli_args: Dict[str, Any],
) -> Dict[str, Any]:
    """Merge *cli_args* with config file entries for *command*.

    ``cli_args`` is expected to be a mapping of option name → value.  Any
    *truthy* value in ``cli_args`` overrides the config file.
    """
    merged: Dict[str, Any] = {}

    # Base from config file, if available
    command_cfg = config.get(command, {})
    if isinstance(command_cfg, dict):
        merged.update(command_cfg)

    # CLI overrides
    for key, value in cli_args.items():
        if value not in (None, "", False):
            merged[key] = value

    return merged


# Convenience for the `scan` command ----------------------------------------


def _split_comma_list(raw: Optional[str]) -> Optional[List[str]]:
    if raw is None:
        return None
    return [item.strip() for item in raw.split(",") if item.strip()]


def get_scan_exclusions(
    config: Dict[str, Any],
    cli_exclude_dirs: Optional[str],
    cli_exclude_patterns: Optional[str],
) -> Dict[str, Optional[List[str]]]:
    """Return merged *exclude_dirs* and *exclude_patterns* lists for scanning."""

    scan_cfg: Dict[str, Any] = (
        config.get("scan", {}) if isinstance(config.get("scan"), dict) else {}
    )

    dirs_from_cfg = scan_cfg.get("exclude_dirs")
    patterns_from_cfg = scan_cfg.get("exclude_patterns")

    dirs_list = (
        _split_comma_list(cli_exclude_dirs)
        if cli_exclude_dirs is not None
        else dirs_from_cfg
    )
    patterns_list = (
        _split_comma_list(cli_exclude_patterns)
        if cli_exclude_patterns is not None
        else patterns_from_cfg
    )

    return {"exclude_dirs": dirs_list, "exclude_patterns": patterns_list}


__all__ = [
    "load_config",
    "merge_options",
    "get_scan_exclusions",
]
