import json
from pathlib import Path

from library_skills.scanner import scan_python_distributions


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
