from pathlib import Path

from codetag.secrets import scan_for_secrets


def test_scan_for_secrets_finds_correct_details(tmp_path: Path) -> None:
    """Secrets should be found with correct metadata (type, line, path)."""

    secrets_content = (
        "aws_key = 'AKIAABCDEFGHIJKLMNOP'\n"  # Line 1
        "github_token = 'ghp_1234567890abcdef1234567890abcdefabcd'\n"  # Line 2
        "nothing to see here\n"  # Line 3
        "-----BEGIN RSA PRIVATE KEY-----"  # Line 4
    )

    # Arrange – create file in non-excluded directory
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    test_file = src_dir / "config.py"
    test_file.write_text(secrets_content)

    # Suspicious filename in repo root
    env_file = tmp_path / ".env"
    env_file.touch()

    # Act
    findings = scan_for_secrets([test_file, env_file], tmp_path)

    # Assert general count (4 findings: 3 content + 1 filename)
    assert len(findings) == 4

    # Validate AWS Access Key finding
    aws_finding = next(
        (f for f in findings if f["secret_type"] == "AWS Access Key"),
        None,
    )
    assert aws_finding is not None
    assert aws_finding["line_number"] == 1
    assert "AKIAABCDEFGHIJKLMNOP" in aws_finding["line_content"]
    assert aws_finding["file_path"] == "src/config.py"

    # Validate suspicious filename finding
    filename_finding = next(
        (f for f in findings if f["secret_type"] == "Suspicious Filename"),
        None,
    )
    assert filename_finding is not None
    assert filename_finding["file_path"] == ".env"
