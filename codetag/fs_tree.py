import os
from pathlib import Path
from typing import List, Optional, TypedDict

from gitignore_parser import parse_gitignore

# Directories that are always skipped regardless of .gitignore
DEFAULT_IGNORES = {"node_modules", ".git", "__pycache__"}

__all__ = ["build_fs_tree", "FsNode"]


class FsNode(TypedDict):
    """Dictionary describing a single file or directory in the tree."""

    name: str
    type: str  # "file" | "directory"
    size_bytes: int
    children: Optional[List["FsNode"]]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compile_ignore(root: Path):
    """Return a callable that determines whether *rel_path* should be ignored."""

    gitignore = root / ".gitignore"
    if gitignore.is_file():
        try:
            return parse_gitignore(str(gitignore))
        except OSError:
            pass
    # Fallback – do not ignore anything
    return lambda _p: False  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_fs_tree(root_path: Path, include_hidden: bool = False) -> List[FsNode]:
    """Return a nested directory tree rooted at *root_path*.

    *include_hidden* controls whether dot‐prefixed files/dirs are considered.
    The implementation prunes ignored directories **before** `os.walk` descends
    into them so we never pay the cost of scanning large folders like
    *node_modules*.
    """

    root_path = Path(root_path).resolve()
    if not root_path.exists():
        raise FileNotFoundError(root_path)
    if not root_path.is_dir():
        raise NotADirectoryError(root_path)

    is_ignored = _compile_ignore(root_path)

    root_nodes: List[FsNode] = []
    children_map: dict[Path, List[FsNode]] = {root_path: root_nodes}

    for dirpath_str, dirnames, filenames in os.walk(root_path, topdown=True):
        current_dir = Path(dirpath_str)
        rel_dir = current_dir.relative_to(root_path)

        # ----------------- prune sub-directories -----------------------------
        # Filter/prune directories in-place (os.walk respects the modified list)
        dirnames[:] = [
            d
            for d in dirnames
            if d not in DEFAULT_IGNORES
            and (include_hidden or not d.startswith('.'))
            and not is_ignored(str(current_dir / d))
        ]

        parent_children = children_map.get(current_dir)
        if parent_children is None:  # parent was pruned
            continue

        # Add directory nodes (sorted for determinism)
        for d_name in sorted(dirnames):
            dir_path = current_dir / d_name
            dir_node: FsNode = {
                "name": d_name,
                "type": "directory",
                "size_bytes": 0,  # to be filled later
                "children": [],
            }
            parent_children.append(dir_node)
            children_map[dir_path] = dir_node["children"]  # type: ignore[index]

        # -------------------------- files -----------------------------------
        # Process files (filter hidden + ignored)
        for f_name in sorted(
            f
            for f in filenames
            if (include_hidden or not f.startswith('.'))
            and not is_ignored(str(current_dir / f))
        ):
            file_path = current_dir / f_name
            try:
                size = file_path.stat().st_size
            except (OSError, FileNotFoundError):
                continue
            file_node: FsNode = {
                "name": f_name,
                "type": "file",
                "size_bytes": size,
                "children": None,
            }
            parent_children.append(file_node)

    # -------------------- propagate directory sizes -------------------------

    def _propagate_sizes(nodes: List[FsNode]) -> int:
        total = 0
        for n in nodes:
            if n["type"] == "directory" and n["children"] is not None:
                size = _propagate_sizes(n["children"])
                n["size_bytes"] = size
                total += size
            else:
                total += n["size_bytes"]
        return total

    _propagate_sizes(root_nodes)
    return root_nodes 