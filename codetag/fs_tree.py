from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Union, TypedDict, Any

# Public alias that represents a single node (directory or file) in the
# filesystem tree. Using *TypedDict* keeps runtime representation identical to
# a plain ``dict`` while providing type-checking benefits.


class FsNode(TypedDict, total=False):
    name: str
    type: str  # "file" or "directory"
    size: int  # only for files
    children: List["FsNode"]  # only for directories


__all__ = ["build_fs_tree", "FsNode"]


def build_fs_tree(root_path: Union[str, Path], *, include_hidden: bool = False) -> FsNode:
    """Return a dictionary describing the file-system tree rooted at *root_path*.

    Each node in the tree is a mapping with at least the keys ``name`` and ``type``.
    Directories additionally contain a ``children`` key listing their contents.
    Files contain a ``size`` key with their byte size.

    Parameters
    ----------
    root_path: Union[str, Path]
        Path to the directory or file to scan.
    include_hidden: bool, default False
        Whether to include hidden files/directories (those whose names start with ".").
    """
    root = Path(root_path)

    if not root.exists():
        raise FileNotFoundError(f"{root_path} does not exist")

    def _node(path: Path) -> FsNode:
        if path.is_dir():
            children: List[FsNode] = []
            for child in sorted(path.iterdir(), key=lambda p: p.name):
                if not include_hidden and child.name.startswith("."):
                    continue
                children.append(_node(child))
            return {"name": path.name, "type": "directory", "children": children}
        else:
            return {
                "name": path.name,
                "type": "file",
                "size": path.stat().st_size,
            }

    return _node(root) 