from pathlib import Path
from typing import List, Optional

import pytest

from codetag.dependencies import parse_requirements_txt

# (input content, expected list or None)
REQUIREMENTS_TEST_CASES = [
    ("requests==2.28.1\npydantic", ["requests", "pydantic"]),
    ("numpy>=1.20.0\ntomli~=2.0", ["numpy", "tomli"]),
    ("  requests  \n  pydantic  ", ["requests", "pydantic"]),
    ("requests\n\npydantic", ["requests", "pydantic"]),
    ("requests # a comment", ["requests"]),
    ("# this is a comment\n# so is this", None),
    ("\n# a comment\n\n", None),
    ("", None),
]


@pytest.mark.parametrize("content, expected", REQUIREMENTS_TEST_CASES)
def test_parse_requirements_txt_various(tmp_path: Path, content: str, expected: Optional[List[str]]):
    """Parameterized checks for multiple requirement file variations."""
    req_file = tmp_path / "requirements.txt"
    req_file.write_text(content)
    assert parse_requirements_txt(req_file) == expected


def test_parse_requirements_txt_file_not_found():
    """Non-existent file path should yield None."""
    missing = Path("this/path/absolutely/does/not/exist.txt")
    assert parse_requirements_txt(missing) is None 