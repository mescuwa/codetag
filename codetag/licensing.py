"""Licensing utilities for CodeTag.

This module is intentionally self-contained so it can be frozen into a
stand-alone binary later without pulling in the rest of the application.

The public helpers are:

* ``validate_license`` – ensure a valid license file is present; exits
  the process when the license is missing or invalid.
* ``activate_license`` – store a new, verified license on disk.

Nothing in here depends on other Codetag internals aside from Pydantic.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ValidationError

# IMPORTANT: keep this salt secret in the published binary.
SECRET_SALT = "your-super-secret-salt-that-is-hard-to-guess"

# Where the license is stored on the user machine (e.g. ~/.codetag.license)
LICENSE_FILE = Path.home() / ".codetag.license"


class LicenseData(BaseModel):
    """Structured representation of a stored license file."""

    email_hash: str
    key: str

    model_config = {
        "frozen": True,  # make instances immutable so we do not mutate by accident
        "extra": "forbid",  # guard against junk fields in the json
    }


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def validate_license() -> Optional[LicenseData]:
    """Validate the locally stored license file.

    On failure the process will exit with a non-zero status code.  When the
    license is valid the parsed :class:`LicenseData` (for potential telemetry
    or analytics) is returned.
    """
    if not LICENSE_FILE.exists():
        print(
            "ERROR: No license found. Please activate using 'codetag activate <key>'.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        data = LicenseData.model_validate_json(LICENSE_FILE.read_text())
    except ValidationError:
        print("ERROR: License file is corrupted. Please reactivate.", file=sys.stderr)
        sys.exit(1)

    # Re-calculate expected signature and compare.
    expected_signature = hashlib.sha256((data.email_hash + SECRET_SALT).encode()).hexdigest()

    if hashlib.sha256(data.key.encode()).hexdigest() != expected_signature:
        print(
            "ERROR: License key is invalid. It may be for a different user or has been revoked.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Optional – implement server-side revocation list check here.

    # Informational message – can be removed in production.
    print("License valid.", file=sys.stderr)
    return data


def activate_license(key: str, email: str) -> None:
    """Validate *key* for *email* and persist it to :data:`LICENSE_FILE`."""
    email_hash = hashlib.sha256(email.lower().strip().encode()).hexdigest()
    expected_signature = hashlib.sha256((email_hash + SECRET_SALT).encode()).hexdigest()

    if hashlib.sha256(key.encode()).hexdigest() != expected_signature:
        print("ERROR: The provided key is not valid for this email address.", file=sys.stderr)
        sys.exit(1)

    license_data = LicenseData(email_hash=email_hash, key=key)
    LICENSE_FILE.write_text(license_data.model_dump_json(indent=2))
    print(f"✅ License successfully activated for {email}. Thank you!") 