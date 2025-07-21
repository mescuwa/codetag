import re
from pathlib import Path
from typing import List, Tuple

# Common binary or large file extensions to skip for secret scanning
BINARY_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".ico",
    ".svg",  # Images
    ".mp3",
    ".wav",
    ".flac",
    ".mp4",
    ".mov",
    ".avi",  # Media
    ".zip",
    ".tar",
    ".gz",
    ".rar",
    ".7z",  # Archives
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",  # Docs
    ".exe",
    ".dll",
    ".so",
    ".o",
    ".a",
    ".lib",  # Binaries
    ".lock",
    ".bin",
    ".dat",
}

# Do not attempt to scan files larger than 1 MB – reduces I/O overhead
MAX_SECRET_FILE_SIZE = 1_000_000  # bytes (≈1 MB)

# ---------------------------------------------------------------------------
# Simple pattern-based secrets detection helpers
# ---------------------------------------------------------------------------

# (name, compiled-regex) tuples for common secret formats.
SECRET_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("AWS Access Key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("GitHub Token", re.compile(r"ghp_[0-9a-zA-Z]{36}")),
    ("Generic API Key", re.compile(r"[A-Za-z0-9]{20,40}_[A-Za-z0-9_]{20,40}")),
    ("RSA Private Key", re.compile(r"-----BEGIN RSA PRIVATE KEY-----")),
]

# File names that often contain secrets
SUSPICIOUS_FILENAMES: List[str] = [
    ".env",
    "credentials",
    ".secret",
    "private.key",
]


class FoundSecret(dict):
    """Dictionary describing a single potential secret finding."""

    def __init__(
        self, file_path: str, secret_type: str, line_number: int, line_content: str
    ):
        super().__init__(
            file_path=file_path,
            secret_type=secret_type,
            line_number=line_number,
            line_content=line_content.strip()[:200],  # Truncate overly long lines
        )


def scan_for_secrets(file_paths: List[Path], root_path: Path) -> List[FoundSecret]:
    """Return a list of *FoundSecret* for any secrets detected in *file_paths*."""

    findings: List[FoundSecret] = []

    for path in file_paths:
        # -------- quick filters to avoid heavy I/O -----------------------
        # 1. Skip obvious binary files by extension
        if path.suffix.lower() in BINARY_EXTENSIONS:
            continue

        # 2. Skip the scanner's own implementation file to avoid self-detection false positives
        if path.name == "secrets.py":
            continue

        # 3. Skip very large files
        try:
            if path.stat().st_size > MAX_SECRET_FILE_SIZE:
                continue
        except OSError:
            # Unable to stat file; skip
            continue

        try:
            rel_path = str(path.relative_to(root_path))
        except ValueError:
            rel_path = str(path)

        # -------- filename heuristics -------------------------------------
        lowered_name = path.name.lower()
        for suspicious in SUSPICIOUS_FILENAMES:
            if suspicious in lowered_name:
                findings.append(
                    FoundSecret(rel_path, "Suspicious Filename", 1, path.name)
                )
                # Break from this filename heuristic loop; still scan file contents below.
                break

        # -------- content regex scanning ----------------------------------
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as fp:
                for lineno, line in enumerate(fp, 1):
                    for secret_name, pattern in SECRET_PATTERNS:
                        if pattern.search(line):
                            findings.append(
                                FoundSecret(rel_path, secret_name, lineno, line)
                            )
                            # Optimization: if a secret is found, no need to check other patterns on the same line
                            break
        except (OSError, UnicodeDecodeError):
            # Skip unreadable files; treat as no findings.
            continue

    return findings


__all__ = ["scan_for_secrets", "FoundSecret"]
