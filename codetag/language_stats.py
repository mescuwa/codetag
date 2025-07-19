"""Utilities for detecting file language and counting lines.

The module currently focuses on single-file analysis via
:func:`analyze_file_stats` but can later be extended to walk entire
repositories and aggregate statistics.
"""

from __future__ import annotations

import hashlib  # NEW: for content hashing
from collections import namedtuple
from pathlib import Path
from typing import Dict, Optional

# ---------------------------------------------------------------------------
# Public data structures
# ---------------------------------------------------------------------------

# NEW: Added 'content_hash' to capture file content integrity
FileStats = namedtuple("FileStats", ["language", "code", "blank", "comment", "content_hash"])

# ---------------------------------------------------------------------------
# Language detection helpers
# ---------------------------------------------------------------------------

# Central list of extensions considered *source code* across CodeTag.
SOURCE_CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp", ".h", ".cs", ".go",
    ".rs", ".rb", ".php", ".swift", ".kt", ".m", ".mm", ".html", ".htm", ".css",
    ".scss", ".sass", ".md", ".rst", ".txt", ".yaml", ".yml", ".toml", ".ini",
    ".cfg", ".sh", ".bash", ".zsh", ".ps1", ".bat", ".tf", ".jsonl", "dockerfile",
    "makefile",
}

# A (very) small, easily extensible mapping of filename/extension patterns to
# human-readable language names.
LANGUAGE_MAP: Dict[str, str] = {
    # Extensions
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".java": "Java",
    ".c": "C",
    ".cpp": "C++",
    ".h": "C/C++ Header",
    ".cs": "C#",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".md": "Markdown",
    ".json": "JSON",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".sh": "Shell",
    ".bat": "Batch",
    ".ps1": "PowerShell",
    # Filenames without extension
    "Dockerfile": "Dockerfile",
}

# Comment prefix per language – keeps analysis *rough* but fast.
COMMENT_MAP: Dict[str, str] = {
    "Python": "#",
    "JavaScript": "//",
    "TypeScript": "//",
    "Java": "//",
    "C": "//",
    "C++": "//",
    "C#": "//",
    "Go": "//",
    "Rust": "//",
    "Ruby": "#",
    "Shell": "#",
}

# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def analyze_file_stats(file_path: Path) -> Optional[FileStats]:
    """Return :class:`FileStats` for *file_path* or *None* if not recognized.

    • Language is inferred first by exact filename (e.g. *Dockerfile*), then by
      extension (case-insensitive).
    • Lines are classified as *code*, *blank* (no non-whitespace chars), or
      *comment* (full-line comment using the language's single-line marker).
    • Lines with inline comments still count as *code* (this matches many LOC
      tools and is sufficient for a repository-level overview).
    """

    path = Path(file_path)

    # Determine language.
    language = LANGUAGE_MAP.get(path.name)
    if language is None:
        language = LANGUAGE_MAP.get(path.suffix.lower())
    if language is None:
        return None  # Unrecognised type – skip.

    code_lines = blank_lines = comment_lines = 0
    comment_prefix = COMMENT_MAP.get(language)

    try:
        # Read the entire content once to both analyse lines and compute hash
        content = path.read_text("utf-8", errors="ignore")
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line:
                blank_lines += 1
            elif comment_prefix and line.startswith(comment_prefix):
                comment_lines += 1
            else:
                code_lines += 1
    except (OSError, UnicodeDecodeError):
        # File cannot be read – treat as unrecognised.
        return None

    # Include the newly computed content_hash in the returned stats
    return FileStats(language, code_lines, blank_lines, comment_lines, content_hash) 