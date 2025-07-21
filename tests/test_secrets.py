from pathlib import Path

from codetag.secrets import scan_for_secrets


def test_scan_for_secrets(tmp_path: Path) -> None:
    """scan_for_secrets should detect AWS keys and generic API keys."""
    sample = (
        "AWS_SECRET=AKIAABCDEFGHIJKLMNOP\n"
        "token='ghp_abcdefghijklmnopqrstuvwxyz1234567890'\n"
        "api_key=api_key:1234567890ABCDEF\n"
    )

    test_file = tmp_path / "settings.env"
    test_file.write_text(sample)

    findings = scan_for_secrets([test_file], tmp_path)
    types = {f["secret_type"] for f in findings}

    assert "AWS Access Key" in types
    assert "Generic API Key" in types
    assert "GitHub Token" in types 