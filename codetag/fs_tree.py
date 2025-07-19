import os, fnmatch
from pathlib import Path
from typing import List, Optional, TypedDict, Any, Dict

from gitignore_parser import parse_gitignore
from .lfs import parse_gitattributes, is_file_lfs_managed, check_for_lfs

# Directories that are always skipped regardless of .gitignore
DEFAULT_IGNORES = {"node_modules", ".git", "__pycache__"}

__all__ = ["build_fs_tree", "FsNode", "flatten_fs_tree"]


class FsNode(TypedDict):
    """Dictionary describing a single file or directory in the tree."""

    name: str
    type: str  # "file" | "directory"
    size_bytes: int
    children: Optional[List["FsNode"]]
    # Git-LFS metadata (optional – present only for pointer files)
    is_lfs_pointer: Optional[bool]
    real_size: Optional[int]


# ---------------------------------------------------------------------------
# Helpers for build_fs_tree
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


def _process_file_node(
    file_name: str,
    *,
    current_dir: Path,
    root_path: Path,
    lfs_patterns: List[str]
) -> Optional[FsNode]:
    """Create an FsNode for a single file, including LFS checks."""

    file_path = current_dir / file_name
    # Skip symlinks to prevent traversal attacks and reading unintended files.
    if file_path.is_symlink():
        return None
    try:
        size_on_disk = file_path.stat().st_size
    except (OSError, FileNotFoundError):
        return None

    file_node: FsNode = {
        "name": file_name,
        "type": "file",
        "size_bytes": size_on_disk,
        "children": None,
        "is_lfs_pointer": False,
        "real_size": None,
    }

    # If the file matches an LFS pattern, check whether it is a pointer.
    if lfs_patterns:
        relative_file_path = file_path.relative_to(root_path)
        if is_file_lfs_managed(relative_file_path, lfs_patterns):
            lfs_info = check_for_lfs(file_path)
            if lfs_info:
                # Merge metadata and override the displayed size.
                file_node.update(lfs_info)  # type: ignore[arg-type]
                file_node["size_bytes"] = lfs_info["real_size"]  # type: ignore[index]

    return file_node


def _propagate_directory_sizes(nodes: List[FsNode]) -> int:
    """Recursively calculate directory sizes from their children."""
    total = 0
    for n in nodes:
        if n["type"] == "directory" and n["children"] is not None:
            size = _propagate_directory_sizes(n["children"])
            n["size_bytes"] = size
            total += size
        else:
            total += n["size_bytes"]
    return total


# ---------------------------------------------------------------------------
# Flatten helper
# ---------------------------------------------------------------------------


def flatten_fs_tree(
    nodes: List[FsNode],
    *,
    with_meta: bool = False,
    prefix: Path = Path(),
) -> List[Path] | List[Dict[str, Any]]:
    """Recursively flatten *nodes* into a list.

    Parameters
    ----------
    nodes:
        Nested tree structure as returned by :func:`build_fs_tree`.
    with_meta:
        If *False* (default) return a simple ``List[Path]`` containing file
        paths.  When *True* return a list of dictionaries that include all
        metadata from the original *FsNode* plus a ``path`` key with the file
        location.
    prefix:
        Internal parameter used during recursion to construct absolute paths.
    """

    flat: list[Any] = []
    for node in nodes:
        current_path = prefix / node["name"]

        if node["type"] == "file":
            if with_meta:
                node_copy: Dict[str, Any] = node.copy()  # type: ignore[assignment]
                node_copy["path"] = str(current_path)
                flat.append(node_copy)
            else:
                flat.append(current_path)
        elif node["type"] == "directory" and node.get("children"):
            flat.extend(
                flatten_fs_tree(node["children"], with_meta=with_meta, prefix=current_path)  # type: ignore[arg-type]
            )

    return flat


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_fs_tree(
    root_path: Path,
    *,
    include_hidden: bool = False,
    exclude_dirs: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
) -> List[FsNode]:
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
    lfs_patterns = parse_gitattributes(root_path)

    root_nodes: List[FsNode] = []
    children_map: dict[Path, List[FsNode]] = {root_path: root_nodes}
    exclude_dirs_set = set(exclude_dirs or [])

    for dirpath_str, dirnames, filenames in os.walk(root_path, topdown=True):
        current_dir = Path(dirpath_str)

        # Prune sub-directories in-place (os.walk respects the modified list)
        dirnames[:] = [
            d for d in dirnames
            if d not in DEFAULT_IGNORES
            and d not in exclude_dirs_set
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
                "name": d_name, "type": "directory", "size_bytes": 0,
                "children": [], "is_lfs_pointer": False, "real_size": None
            }
            parent_children.append(dir_node)
            children_map[dir_path] = dir_node["children"]  # type: ignore[index]

        # Process and filter files
        filtered_files = sorted(
            f for f in filenames
            if (include_hidden or not f.startswith('.'))
            and not is_ignored(str(current_dir / f))
            and not (exclude_patterns and any(fnmatch.fnmatch(f, pat) for pat in exclude_patterns))
        )

        for f_name in filtered_files:
            file_node = _process_file_node(
                f_name,
                current_dir=current_dir,
                root_path=root_path,
                lfs_patterns=lfs_patterns
            )
            if file_node:
                parent_children.append(file_node)

    # Propagate directory sizes up the tree
    _propagate_directory_sizes(root_nodes)
    return root_nodes 