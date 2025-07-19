"""
Core logic for the `audit` command.

This module wraps the vulnerability-scanning logic that used to live inside
`cli.py`.  Moving it here removes a significant chunk of imperative code from
the CLI layer and makes the auditing functionality reusable from other entry
points (e.g. a future API server).
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import List

import typer
from pydantic import BaseModel, Field

# Internal helpers -----------------------------------------------------------
from .fs_tree import build_fs_tree, flatten_fs_tree
from .secrets import scan_for_secrets
# _get_all_files_from_tree replaced by flatten_fs_tree
from .models import (
    DependencyVulnerability, CodeVulnerability, FoundSecretModel, ThreatAssessment,
)

# ---------------------------------------------------------------------------
# Pydantic models have been centralized in codetag.models

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def audit_repository(path: Path, *, strict_semgrep: bool = False) -> ThreatAssessment:
    """Run dependency, SAST and secret scanning on *path*.

    Parameters
    ----------
    path:
        Root directory of the project to audit.
    strict_semgrep:
        Whether to use the stricter "p/ci" Semgrep ruleset instead of the
        default "p/default".
    """
    start = time.time()
    typer.echo(f"🛡️  Running threat assessment on: {path}", err=True)

    # ------------------------------------------------------------------
    # 1. Dependency scan (OSV-Scanner) ----------------------------------
    # ------------------------------------------------------------------
    dep_vulns = _run_osv_scanner(path)
    if dep_vulns:
        typer.secho(f"🚨 Found {len(dep_vulns)} potential dependency vulnerabilities.", fg=typer.colors.RED, err=True)
    else:
        typer.secho("✅ No dependency vulnerabilities found.", fg=typer.colors.GREEN, err=True)

    # ------------------------------------------------------------------
    # 2. Static analysis (Semgrep) --------------------------------------
    # ------------------------------------------------------------------
    code_vulns = _run_semgrep(path, strict_semgrep)
    if code_vulns:
        typer.secho(f"🚨 Found {len(code_vulns)} potential code vulnerabilities.", fg=typer.colors.RED, err=True)
    else:
        typer.secho("✅ No code vulnerabilities found.", fg=typer.colors.GREEN, err=True)

    # ------------------------------------------------------------------
    # 3. Secret scan ----------------------------------------------------
    # ------------------------------------------------------------------
    tree = build_fs_tree(path, include_hidden=True)
    all_files = flatten_fs_tree(tree, prefix=path)
    secrets_raw = scan_for_secrets(all_files, path)
    secrets_models = [FoundSecretModel(**s) for s in secrets_raw]
    if secrets_models:
        typer.secho(f"🚨 Found {len(secrets_models)} potential secret(s).", fg=typer.colors.RED, err=True)
    else:
        typer.secho("✅ No hardcoded secrets found.", fg=typer.colors.GREEN, err=True)

    # Duration ----------------------------------------------------------
    typer.echo(f"⏱️  Audit completed in {round(time.time() - start, 2)}s", err=True)

    return ThreatAssessment(
        dependency_vulnerabilities=dep_vulns,
        code_vulnerabilities=code_vulns,
        secrets_found=secrets_models,
    )

# ---------------------------------------------------------------------------
# Helper subprocess wrappers
# ---------------------------------------------------------------------------

def _run_osv_scanner(path: Path) -> List[DependencyVulnerability]:
    """Execute *osv-scanner* and parse JSON output into Pydantic objects."""

    typer.echo("\n--- 1. Dependency Vulnerability Scan (OSV-Scanner) ---", err=True)

    cmd = ["osv-scanner", "--json", "-r", str(path), "--skip-git"]
    vulns: List[DependencyVulnerability] = []
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if not result.stdout:
            return []
        data = json.loads(result.stdout)
        for res in data.get("results", []):
            for pkg in res.get("packages", []):
                pkg_info = pkg.get("package", {})
                for vuln in pkg.get("vulnerabilities", []):
                    vulns.append(
                        DependencyVulnerability(
                            id=vuln.get("id", ""),
                            package_name=pkg_info.get("name", "unknown"),
                            vulnerable_version=pkg_info.get("version", "unknown"),
                            summary=vuln.get("summary", ""),
                            severity=vuln.get("database_specific", {}).get("severity"),
                        )
                    )
        return vulns
    except FileNotFoundError:
        typer.echo("⚠️  'osv-scanner' not installed. Skipping dependency scan.", err=True)
        return []
    except Exception as exc:
        typer.echo(f"⚠️  OSV-Scanner failed: {exc}", err=True)
        return []


def _run_semgrep(path: Path, strict: bool) -> List[CodeVulnerability]:
    """Execute *semgrep* and parse JSON output into Pydantic objects."""

    typer.echo("\n--- 2. Code Vulnerability Scan (Semgrep) ---", err=True)

    config = "p/ci" if strict else "p/default"
    cmd = ["semgrep", "scan", "--json", "--config", config, str(path)]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode not in (0, 1):
            raise subprocess.CalledProcessError(result.returncode, cmd, output=result.stdout, stderr=result.stderr)
        if not result.stdout:
            return []
        data = json.loads(result.stdout)
        vulns: List[CodeVulnerability] = []
        for finding in data.get("results", []):
            vulns.append(
                CodeVulnerability(
                    check_id=finding.get("check_id", ""),
                    path=finding.get("path", ""),
                    line=finding.get("start", {}).get("line", 0),
                    message=finding.get("extra", {}).get("message", ""),
                    severity=finding.get("extra", {}).get("severity", "INFO"),
                )
            )
        return vulns
    except FileNotFoundError:
        typer.echo("⚠️  'semgrep' not installed. Skipping SAST scan.", err=True)
        return []
    except Exception as exc:
        typer.echo(f"⚠️  Semgrep scan failed: {exc}", err=True)
        return [] 