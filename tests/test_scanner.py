import json
from pathlib import Path

import pytest

from library_skills.scanner import (
    _is_relative_to,
    _read_editable_source_root,
    _scan_editable_direct_url,
    scan_python_distributions,
)


def write_skill(root: Path, name: str, description: str = "Demo skill.") -> Path:
    skill_dir = root / ".agents" / "skills" / name
    skill_dir.mkdir(parents=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n",
        encoding="utf-8",
    )
    return skill_md


def write_dist_info(
    site_packages: Path,
    dist_name: str,
    *,
    version: str = "1.0.0",
    record_paths: list[str] | None = None,
) -> Path:
    dist_info = site_packages / f"{dist_name.replace('-', '_')}-{version}.dist-info"
    dist_info.mkdir(parents=True)
    dist_info.joinpath("METADATA").write_text(
        f"Metadata-Version: 2.4\nName: {dist_name}\nVersion: {version}\n",
        encoding="utf-8",
    )
    if record_paths is not None:
        dist_info.joinpath("RECORD").write_text(
            "".join(f"{path},,\n" for path in record_paths),
            encoding="utf-8",
        )
    return dist_info


def test_scan_python_distributions_discovers_record_based_skills(tmp_path):
    site_packages = tmp_path / "site-packages"
    package_root = site_packages / "demo_pkg"
    skill_md = write_skill(package_root, "demo-skill")
    write_dist_info(
        site_packages,
        "demo-pkg",
        version="1.2.3",
        record_paths=[skill_md.relative_to(site_packages).as_posix()],
    )

    result = scan_python_distributions(site_packages)

    assert result.warnings == []
    assert len(result.skills) == 1
    skill = result.skills[0]
    assert skill.name == "demo-skill"
    assert skill.description == "Demo skill."
    assert skill.package_name == "demo-pkg"
    assert skill.package_version == "1.2.3"
    assert skill.path == skill_md.resolve()
    assert skill.skill_dir == skill_md.parent


def test_scan_python_distributions_warns_for_invalid_skill_metadata(tmp_path):
    site_packages = tmp_path / "site-packages"
    skill_md = write_skill(site_packages / "demo_pkg", "actual-name")
    skill_md.write_text(
        "---\nname: different-name\ndescription: Demo skill.\n---\n",
        encoding="utf-8",
    )
    write_dist_info(
        site_packages,
        "demo-pkg",
        record_paths=[skill_md.relative_to(site_packages).as_posix()],
    )

    result = scan_python_distributions(site_packages)

    assert result.skills == []
    assert len(result.warnings) == 1
    assert "must match parent directory name" in result.warnings[0]


def test_scan_python_distributions_uses_editable_direct_url_fallback(tmp_path):
    site_packages = tmp_path / "site-packages"
    source_root = tmp_path / "source"
    skill_md = write_skill(source_root / "demo_pkg", "editable-skill")
    dist_info = write_dist_info(site_packages, "editable-pkg")
    dist_info.joinpath("direct_url.json").write_text(
        json.dumps(
            {
                "url": source_root.as_uri(),
                "dir_info": {"editable": True},
            }
        ),
        encoding="utf-8",
    )

    result = scan_python_distributions(site_packages)

    assert result.warnings == []
    assert [skill.name for skill in result.skills] == ["editable-skill"]
    assert result.skills[0].path == skill_md.resolve()


def test_scan_python_distributions_warns_when_site_packages_is_missing(tmp_path):
    result = scan_python_distributions(tmp_path / "missing")

    assert result.skills == []
    assert result.warnings == [
        f"Site-packages directory not found: {tmp_path / 'missing'}"
    ]


def test_scan_python_distributions_warns_for_invalid_distribution_metadata(tmp_path):
    site_packages = tmp_path / "site-packages"
    (site_packages / "invalid-1.0.0.dist-info").mkdir(parents=True)

    result = scan_python_distributions(site_packages)

    assert result.skills == []
    assert len(result.warnings) == 1
    assert "Skipping invalid distribution metadata" in result.warnings[0]


def test_scan_python_distributions_skips_dist_info_files(tmp_path):
    site_packages = tmp_path / "site-packages"
    site_packages.mkdir()
    (site_packages / "not-a-directory.dist-info").write_text("", encoding="utf-8")

    result = scan_python_distributions(site_packages)

    assert result.skills == []
    assert result.warnings == []


def test_scan_python_distributions_warns_for_metadata_without_name(tmp_path):
    site_packages = tmp_path / "site-packages"
    dist_info = site_packages / "demo-1.0.0.dist-info"
    dist_info.mkdir(parents=True)
    dist_info.joinpath("METADATA").write_text(
        "Metadata-Version: 2.4\nVersion: 1.0.0\n",
        encoding="utf-8",
    )

    result = scan_python_distributions(site_packages)

    assert result.skills == []
    assert len(result.warnings) == 1
    assert "Skipping invalid distribution metadata" in result.warnings[0]


def test_scan_python_distributions_ignores_empty_non_skill_and_duplicate_records(
    tmp_path,
):
    site_packages = tmp_path / "site-packages"
    skill_md = write_skill(site_packages / "demo_pkg", "demo-skill")
    dist_info = write_dist_info(site_packages, "demo-pkg")
    record_path = skill_md.relative_to(site_packages).as_posix()
    dist_info.joinpath("RECORD").write_text(
        f"\nnot/a/skill.txt,,\n{record_path},,\n{record_path},,\n",
        encoding="utf-8",
    )

    result = scan_python_distributions(site_packages)

    assert result.warnings == []
    assert [skill.name for skill in result.skills] == ["demo-skill"]


@pytest.mark.parametrize(
    ("skill_text", "expected_warning"),
    [
        ("name: no-frontmatter\n", "missing YAML frontmatter"),
        ("---\nname: unterminated\n", "unterminated YAML frontmatter"),
        ("---\ndescription: Missing name.\n---\n", "missing required 'name' field"),
        (
            "---\nname: Invalid_Name\ndescription: Invalid name.\n---\n",
            "invalid 'name' field",
        ),
        ("---\nname: demo-skill\n---\n", "missing required 'description' field"),
        (
            "---\nthis line has no separator\n"
            "name: demo-skill\ndescription: Demo skill.\n---\n",
            "",
        ),
        (
            f"---\nname: demo-skill\ndescription: {'x' * 1025}\n---\n",
            "'description' field must be at most 1024 characters",
        ),
    ],
)
def test_scan_python_distributions_warns_for_invalid_skill_files(
    tmp_path,
    skill_text,
    expected_warning,
):
    site_packages = tmp_path / "site-packages"
    skill_md = write_skill(site_packages / "demo_pkg", "demo-skill")
    skill_md.write_text(skill_text, encoding="utf-8")
    write_dist_info(
        site_packages,
        "demo-pkg",
        record_paths=[skill_md.relative_to(site_packages).as_posix()],
    )

    result = scan_python_distributions(site_packages)

    if expected_warning:
        assert result.skills == []
        assert len(result.warnings) == 1
        assert expected_warning in result.warnings[0]
    else:
        assert [skill.name for skill in result.skills] == ["demo-skill"]
        assert result.warnings == []


def test_scan_python_distributions_warns_when_skill_file_is_not_utf8(tmp_path):
    site_packages = tmp_path / "site-packages"
    skill_md = write_skill(site_packages / "demo_pkg", "demo-skill")
    skill_md.write_bytes(b"\xff")
    write_dist_info(
        site_packages,
        "demo-pkg",
        record_paths=[skill_md.relative_to(site_packages).as_posix()],
    )

    result = scan_python_distributions(site_packages)

    assert result.skills == []
    assert len(result.warnings) == 1
    assert "could not read SKILL.md" in result.warnings[0]


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"dir_info": {"editable": False}, "url": "file:///tmp/demo"},
        {"dir_info": {"editable": True}, "url": 1},
        {"dir_info": {"editable": True}, "url": "https://example.com/demo"},
        {"dir_info": {"editable": True}, "url": "file:///path/that/does/not/exist"},
    ],
)
def test_read_editable_source_root_rejects_invalid_direct_url_payloads(
    tmp_path,
    payload,
):
    dist_info = tmp_path / "demo-1.0.0.dist-info"
    dist_info.mkdir()
    dist_info.joinpath("direct_url.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    assert _read_editable_source_root(dist_info) is None


def test_is_relative_to_returns_false_for_unrelated_paths(tmp_path):
    assert _is_relative_to(tmp_path / "one", tmp_path / "two") is False


def test_scan_editable_direct_url_skips_symlinked_skills_outside_source_root(
    tmp_path,
):
    site_packages = tmp_path / "site-packages"
    source_root = tmp_path / "source"
    outside_root = tmp_path / "outside"
    skill_link_dir = source_root / "demo_pkg" / ".agents" / "skills" / "linked-skill"
    skill_link_dir.mkdir(parents=True)
    outside_skill_md = write_skill(outside_root / "demo_pkg", "linked-skill")
    (skill_link_dir / "SKILL.md").symlink_to(outside_skill_md)
    dist_info = write_dist_info(site_packages, "editable-pkg")
    dist_info.joinpath("direct_url.json").write_text(
        json.dumps({"url": source_root.as_uri(), "dir_info": {"editable": True}}),
        encoding="utf-8",
    )

    result = scan_python_distributions(site_packages)

    assert result.skills == []
    assert result.warnings == []


def test_scan_editable_direct_url_skips_seen_skill_dirs(tmp_path):
    dist_info = tmp_path / "editable-1.0.0.dist-info"
    source_root = tmp_path / "source"
    skill_md = write_skill(source_root / "demo_pkg", "editable-skill")
    dist_info.mkdir()
    dist_info.joinpath("direct_url.json").write_text(
        json.dumps({"url": source_root.as_uri(), "dir_info": {"editable": True}}),
        encoding="utf-8",
    )

    result = _scan_editable_direct_url(
        dist_info=dist_info,
        package_name="editable-pkg",
        package_version="1.0.0",
        seen_skill_dirs={skill_md.parent},
    )

    assert result.skills == []
    assert result.warnings == []


def test_scan_editable_direct_url_reports_invalid_skill_warning(tmp_path):
    site_packages = tmp_path / "site-packages"
    source_root = tmp_path / "source"
    skill_md = write_skill(source_root / "demo_pkg", "editable-skill")
    skill_md.write_text(
        "---\nname: different-name\ndescription: Demo skill.\n---\n",
        encoding="utf-8",
    )
    dist_info = write_dist_info(site_packages, "editable-pkg")
    dist_info.joinpath("direct_url.json").write_text(
        json.dumps({"url": source_root.as_uri(), "dir_info": {"editable": True}}),
        encoding="utf-8",
    )

    result = scan_python_distributions(site_packages)

    assert result.skills == []
    assert len(result.warnings) == 1
    assert "must match parent directory name" in result.warnings[0]
