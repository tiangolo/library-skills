import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

prepare_release_path = Path(__file__).parents[1] / "scripts" / "prepare_release.py"
spec = importlib.util.spec_from_file_location("prepare_release", prepare_release_path)
assert spec is not None
prepare_release = importlib.util.module_from_spec(spec)
sys.modules["prepare_release"] = prepare_release
assert spec.loader is not None
spec.loader.exec_module(prepare_release)

BumpType = prepare_release.BumpType
app = prepare_release.app
bump_version = prepare_release.bump_version
get_release_notes_body = prepare_release.get_release_notes_body
update_json_version_file = prepare_release.update_json_version_file
update_package_lock_file = prepare_release.update_package_lock_file
update_release_notes = prepare_release.update_release_notes
update_version_file = prepare_release.update_version_file

runner = CliRunner()


@pytest.mark.parametrize(
    ("current_version", "bump", "new_version"),
    [
        ("0.0.5", "major", "1.0.0"),
        ("0.0.5", "minor", "0.1.0"),
        ("0.0.5", "patch", "0.0.6"),
    ],
)
def test_bump_version(current_version: str, bump: BumpType, new_version: str) -> None:
    assert bump_version(current_version, bump) == new_version


def test_update_version_file() -> None:
    content = '[project]\nname = "library-skills"\nversion = "0.0.5"\n'

    new_content = update_version_file(content, "0.0.6", Path("pyproject.toml"))

    assert new_content == '[project]\nname = "library-skills"\nversion = "0.0.6"\n'


def test_update_version_file_requires_newer_version() -> None:
    content = '[project]\nversion = "0.0.5"\n'

    with pytest.raises(RuntimeError, match="must be greater"):
        update_version_file(content, "0.0.5", Path("pyproject.toml"))


def test_update_json_version_file() -> None:
    content = '{\n  "name": "library-skills",\n  "version": "0.0.5"\n}\n'

    new_content = update_json_version_file(content, "0.0.6", Path("package.json"))

    assert new_content == '{\n  "name": "library-skills",\n  "version": "0.0.6"\n}\n'


def test_update_package_lock_file() -> None:
    content = (
        "{\n"
        '  "name": "library-skills",\n'
        '  "version": "0.0.5",\n'
        '  "packages": {\n'
        '    "": {\n'
        '      "name": "library-skills",\n'
        '      "version": "0.0.5"\n'
        "    }\n"
        "  }\n"
        "}\n"
    )

    new_content = update_package_lock_file(content, "0.0.6", Path("package-lock.json"))

    assert (
        new_content == "{\n"
        '  "name": "library-skills",\n'
        '  "version": "0.0.6",\n'
        '  "packages": {\n'
        '    "": {\n'
        '      "name": "library-skills",\n'
        '      "version": "0.0.6"\n'
        "    }\n"
        "  }\n"
        "}\n"
    )


def test_update_release_notes() -> None:
    content = """# Release Notes

## Latest Changes

### Fixes

* Fix something.

## 0.0.5 (2026-05-01)

### Fixes

* Previous fix.
"""

    new_content = update_release_notes(
        content, "0.0.6", date(2026, 6, 20), Path("docs/release-notes.md")
    )

    assert (
        new_content
        == """# Release Notes

## Latest Changes

## 0.0.6 (2026-06-20)

### Fixes

* Fix something.

## 0.0.5 (2026-05-01)

### Fixes

* Previous fix.
"""
    )


def test_update_release_notes_rejects_existing_version() -> None:
    content = """# Release Notes

## Latest Changes

## 0.0.6 (2026-06-20)
"""

    with pytest.raises(RuntimeError, match="already contain"):
        update_release_notes(
            content, "0.0.6", date(2026, 6, 20), Path("docs/release-notes.md")
        )


def test_get_release_notes_body_with_dated_heading() -> None:
    content = """# Release Notes

## Latest Changes

## 0.0.6 (2026-06-20)

### Fixes

* Fix something.

## 0.0.5 (2026-05-01)

### Fixes

* Previous fix.
"""

    body = get_release_notes_body(content, "0.0.6", Path("docs/release-notes.md"))

    assert (
        body
        == """### Fixes

* Fix something.
"""
    )


def test_get_release_notes_body_with_plain_heading() -> None:
    content = """# Release Notes

## Latest Changes

## 0.0.6

### Fixes

* Fix something.
"""

    body = get_release_notes_body(content, "0.0.6", Path("docs/release-notes.md"))

    assert body == "### Fixes\n\n* Fix something.\n"


def test_get_release_notes_body_allows_non_version_h2_content() -> None:
    content = """# Release Notes

## Latest Changes

## 0.0.6

## Highlights

* Fix something.

## 0.0.5

* Previous fix.
"""

    body = get_release_notes_body(content, "0.0.6", Path("docs/release-notes.md"))

    assert body == "## Highlights\n\n* Fix something.\n"


def test_get_release_notes_body_requires_version_section() -> None:
    content = "# Release Notes\n\n## Latest Changes\n"

    with pytest.raises(RuntimeError, match="Could not find"):
        get_release_notes_body(content, "0.0.6", Path("docs/release-notes.md"))


def test_get_release_notes_body_requires_non_empty_section() -> None:
    content = """# Release Notes

## Latest Changes

## 0.0.6

## 0.0.5

* Previous fix.
"""

    with pytest.raises(RuntimeError, match="is empty"):
        get_release_notes_body(content, "0.0.6", Path("docs/release-notes.md"))


def test_cli_updates_configured_files(tmp_path: Path) -> None:
    version_file = tmp_path / "pyproject.toml"
    version_file.write_text('[project]\nversion = "0.0.5"\n', encoding="utf-8")
    package_json_file = tmp_path / "package.json"
    package_json_file.write_text('{"version": "0.0.5"}\n', encoding="utf-8")
    package_lock_file = tmp_path / "package-lock.json"
    package_lock_file.write_text(
        '{"version": "0.0.5", "packages": {"": {"version": "0.0.5"}}}\n',
        encoding="utf-8",
    )
    release_notes_file = tmp_path / "release-notes.md"
    release_notes_file.write_text(
        """# Release Notes

## Latest Changes

### Fixes

* Fix something.
""",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "prepare",
            "patch",
            "--version-file",
            str(version_file),
            "--package-json-file",
            str(package_json_file),
            "--package-lock-file",
            str(package_lock_file),
            "--release-notes-file",
            str(release_notes_file),
            "--date",
            "2026-06-20",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Prepared release 0.0.6 (2026-06-20)" in result.output
    assert version_file.read_text(encoding="utf-8") == '[project]\nversion = "0.0.6"\n'
    assert '"version": "0.0.6"' in package_json_file.read_text(encoding="utf-8")
    assert '"version": "0.0.6"' in package_lock_file.read_text(encoding="utf-8")
    assert "## 0.0.6 (2026-06-20)" in release_notes_file.read_text(encoding="utf-8")


def test_cli_accepts_env_vars(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    version_file = tmp_path / "pyproject.toml"
    version_file.write_text('[project]\nversion = "0.0.5"\n', encoding="utf-8")
    package_json_file = tmp_path / "package.json"
    package_json_file.write_text('{"version": "0.0.5"}\n', encoding="utf-8")
    package_lock_file = tmp_path / "package-lock.json"
    package_lock_file.write_text(
        '{"version": "0.0.5", "packages": {"": {"version": "0.0.5"}}}\n',
        encoding="utf-8",
    )
    release_notes_file = tmp_path / "docs" / "release-notes.md"
    release_notes_file.parent.mkdir()
    release_notes_file.write_text(
        "# Release Notes\n\n## Latest Changes\n", encoding="utf-8"
    )
    monkeypatch.setenv("PREPARE_RELEASE_BUMP", "minor")
    monkeypatch.setenv("PREPARE_RELEASE_VERSION_FILE", str(version_file))
    monkeypatch.setenv("PREPARE_RELEASE_PACKAGE_JSON_FILE", str(package_json_file))
    monkeypatch.setenv("PREPARE_RELEASE_PACKAGE_LOCK_FILE", str(package_lock_file))
    monkeypatch.setenv("PREPARE_RELEASE_RELEASE_NOTES_FILE", str(release_notes_file))
    monkeypatch.setenv("PREPARE_RELEASE_DATE", "2026-06-20")

    result = runner.invoke(app, ["prepare"])

    assert result.exit_code == 0, result.output
    assert "Prepared release 0.1.0 (2026-06-20)" in result.output
    assert version_file.read_text(encoding="utf-8") == '[project]\nversion = "0.1.0"\n'
    assert "0.1.0" in package_json_file.read_text(encoding="utf-8")
    assert "0.1.0" in package_lock_file.read_text(encoding="utf-8")
    assert "## 0.1.0 (2026-06-20)" in release_notes_file.read_text(encoding="utf-8")


def test_cli_prints_current_version(tmp_path: Path) -> None:
    version_file = tmp_path / "pyproject.toml"
    version_file.write_text('[project]\nversion = "0.0.5"\n', encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "current-version",
            "--version-file",
            str(version_file),
        ],
    )

    assert result.exit_code == 0, result.output
    assert result.output == "0.0.5\n"


def test_cli_prints_release_notes(tmp_path: Path) -> None:
    version_file = tmp_path / "pyproject.toml"
    version_file.write_text('[project]\nversion = "0.0.6"\n', encoding="utf-8")
    release_notes_file = tmp_path / "release-notes.md"
    release_notes_file.write_text(
        """# Release Notes

## Latest Changes

## 0.0.6 (2026-06-20)

### Fixes

* Fix something.
""",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "release-notes",
            "--version-file",
            str(version_file),
            "--release-notes-file",
            str(release_notes_file),
        ],
    )

    assert result.exit_code == 0, result.output
    assert result.output == "### Fixes\n\n* Fix something.\n"
