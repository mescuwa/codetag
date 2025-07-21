"""Lightweight Tree-sitter based distillation helpers.

This module is *optional*. If the `tree_sitter` binary bindings or the compiled
language library are unavailable, the public ``TREE_SITTER_AVAILABLE`` flag will
be *False* and callers should fall back to heuristic distillers.

Current implementation supports comment stripping for Python files as a proof
of concept (Level 1). More languages and advanced structural distillation can
be added incrementally.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

TREE_SITTER_AVAILABLE: bool

try:
    from tree_sitter import Language, Parser  # type: ignore

    # ------------------------------------------------------------------
    # Attempt to load a pre-compiled language bundle. The bundle creation is
    # environment-specific; users are expected to build it beforehand, e.g.:
    #
    #   Language.build_library(
    #       "build/my-languages.so",
    #       ["vendor/tree-sitter-python", ...],
    #   )
    #
    # and set the environment variable CODETAG_TS_LIB or place the .so at the
    # default path below.
    # ------------------------------------------------------------------
    import os

    DEFAULT_TS_LIB = Path("build/my-languages.so")
    TS_LIB_PATH = Path(os.getenv("CODETAG_TS_LIB", DEFAULT_TS_LIB))

    if TS_LIB_PATH.is_file():
        _PY_LANGUAGE = Language(str(TS_LIB_PATH), "python")
        LANGUAGE_MAP = {
            ".py": _PY_LANGUAGE,
            # Future: add other langs ("javascript", "java", ...)
        }
        TREE_SITTER_AVAILABLE = True
    else:
        LANGUAGE_MAP = {}
        TREE_SITTER_AVAILABLE = False
except Exception:  # pragma: no cover – missing or failing tree_sitter
    TREE_SITTER_AVAILABLE = False
    LANGUAGE_MAP = {}

# ----------------------------------------------------------------------
# Public helpers
# ----------------------------------------------------------------------


def distill_with_tree_sitter(
    content: str, file_extension: str, level: int
) -> Optional[str]:
    """Attempt Tree-sitter based distillation.

    Returns *None* if the given *file_extension* is unsupported or Tree-sitter
    is unavailable.
    """

    if not TREE_SITTER_AVAILABLE:
        return None

    lang = LANGUAGE_MAP.get(file_extension)
    if lang is None:
        return None

    parser = Parser()
    parser.set_language(lang)

    try:
        tree = parser.parse(bytes(content, "utf8"))
    except Exception:
        # Parsing error – fall back
        return None

    # ---------------- Level 1: Comment stripping ------------------------
    if level == 1:
        # Query for *comment* nodes in the grammar. Not all grammars define
        # the same node names; Python uses "comment".
        QUERY_STR = "(comment) @c"
        try:
            query = lang.query(QUERY_STR)
        except Exception:
            return None

        # Collect byte ranges of all comment nodes
        comment_ranges = []
        for node, _name in query.captures(tree.root_node):
            comment_ranges.append((node.start_byte, node.end_byte))

        if not comment_ranges:
            return content  # nothing to strip

        # Build new source by skipping comment ranges
        parts = []
        cursor = 0
        for start, end in sorted(comment_ranges):
            parts.append(content[cursor:start])
            cursor = end
        parts.append(content[cursor:])

        # Replace stripped segments with a single space to preserve offsets
        stripped = " ".join(part for part in parts if part)
        return stripped

    # ---------------- Level 2: (placeholder) ----------------------------
    # Proper structural distillation requires non-trivial subtree slicing
    # which is out of scope for this minimal integration.
    return None
