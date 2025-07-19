import re
from pathlib import Path
from typing import List, Optional
import fnmatch

# ---------------------------------------------------------------------------
# Constants & regex helpers
# ---------------------------------------------------------------------------

# All Git-LFS pointer files start with this version line.
LFS_POINTER_VERSION = "https://git-lfs.github.com/spec/v1"

# Regex to capture the real file size from a pointer file line like:  size 12345
LFS_SIZE_REGEX = re.compile(r"^\s*size\s+(\d+)", re.MULTILINE)


class LfsInfo(dict):
    """Dictionary describing LFS pointer metadata (duck-typed)."""

    def __init__(self, real_size: int):
        super().__init__(is_lfs_pointer=True, real_size=real_size)


# ---------------------------------------------------------------------------
# .gitattributes helpers
# ---------------------------------------------------------------------------

def parse_gitattributes(repo_root: Path) -> List[str]:
    """Return a list of glob patterns that are managed by Git-LFS.

    This function reads a .gitattributes file (if present) and extracts all
    patterns that contain the *filter=lfs* attribute.  The patterns are
    returned exactly as they appear so they can later be matched via
    :pymod:`fnmatch`.
    """

    attributes_file = repo_root / ".gitattributes"
    lfs_patterns: List[str] = []

    if not attributes_file.is_file():
        return lfs_patterns

    try:
        with attributes_file.open("r", encoding="utf-8", errors="ignore") as fp:
            for raw_line in fp:
                line = raw_line.strip()
                # Skip blanks & comments
                if not line or line.startswith("#"):
                    continue
                # Lines that declare Git-LFS typically look like:
                #   *.psd filter=lfs diff=lfs merge=lfs -text
                if "filter=lfs" in line:
                    pattern = line.split()[0]
                    lfs_patterns.append(pattern)
    except OSError:
        # Silently ignore unreadable .gitattributes files
        pass

    return lfs_patterns


# ---------------------------------------------------------------------------
# Pointer file helpers
# ---------------------------------------------------------------------------

def is_file_lfs_managed(relative_path: Path, lfs_patterns: List[str]) -> bool:
    """Return *True* if *relative_path* matches any Git-LFS glob pattern."""

    path_str = str(relative_path)
    for pattern in lfs_patterns:
        if fnmatch.fnmatch(path_str, pattern):
            return True
    return False


def check_for_lfs(file_path: Path) -> Optional[LfsInfo]:
    """Return :class:`LfsInfo` if *file_path* is a Git-LFS pointer, else *None*."""

    try:
        # Pointer files are tiny (a few hundred bytes).  Abort early if bigger.
        if file_path.stat().st_size > 500:  # heuristic – adjust if needed
            return None

        content = file_path.read_text(encoding="utf-8", errors="ignore")

        # Quick prefix check
        if not content.startswith(LFS_POINTER_VERSION):
            return None

        # Extract real size
        match = LFS_SIZE_REGEX.search(content)
        if match:
            real_size = int(match.group(1))
            return LfsInfo(real_size=real_size)

    except (OSError, UnicodeDecodeError):
        # Unreadable or binary – treat as not-a-pointer.
        return None

    return None


__all__ = [
    "parse_gitattributes",
    "is_file_lfs_managed",
    "check_for_lfs",
    "LfsInfo",
] 