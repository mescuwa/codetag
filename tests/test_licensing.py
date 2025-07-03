"""Tests for *codetag.licensing* module."""

import hashlib
from pathlib import Path
from unittest.mock import patch

from codetag.licensing import activate_license, validate_license, SECRET_SALT

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TEST_EMAIL = "test@example.com"

def _get_test_key(email: str) -> str:
    """Generate a valid license *key* for *email*."""
    email_hash = hashlib.sha256(email.lower().strip().encode()).hexdigest()
    return hashlib.sha256((email_hash + SECRET_SALT).encode()).hexdigest()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_activation_and_validation(tmp_path: Path) -> None:
    """A valid key can be activated and later validated."""
    with patch("codetag.licensing.LICENSE_FILE", tmp_path / ".codetag.license"):
        valid_key = _get_test_key(TEST_EMAIL)
        assert activate_license(valid_key, TEST_EMAIL) is True

        data = validate_license()
        assert data is not None
        assert data.key == valid_key


def test_invalid_key_activation(tmp_path: Path) -> None:
    """Activation should fail when the key is wrong."""
    with patch("codetag.licensing.LICENSE_FILE", tmp_path / ".codetag.license"):
        assert activate_license("this-is-a-wrong-key", TEST_EMAIL) is False
        assert not (tmp_path / ".codetag.license").exists()


def test_validation_fails_if_no_license(tmp_path: Path) -> None:
    """Validation returns *None* when there is no license file."""
    with patch("codetag.licensing.LICENSE_FILE", tmp_path / ".codetag.license"):
        assert validate_license() is None


def test_validation_fails_on_tampered_file(tmp_path: Path) -> None:
    """Corrupting the license file invalidates the license."""
    license_file = tmp_path / ".codetag.license"
    with patch("codetag.licensing.LICENSE_FILE", license_file):
        valid_key = _get_test_key(TEST_EMAIL)
        activate_license(valid_key, TEST_EMAIL)

        # Tamper with the file so that validation should now fail.
        license_file.write_text('{"email_hash": "tampered", "key": "tampered"}')
        assert validate_license() is None 