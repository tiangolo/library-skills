from pathlib import Path

from typer.testing import CliRunner

from library_skills.cli import app

runner = CliRunner()


def write_project(tmp_path: Path, dependencies: list[str]) -> Path:
    project = tmp_path / "project"
    site_packages = project / ".venv" / "lib" / "python3.12" / "site-packages"
    site_packages.mkdir(parents=True)
    (project / ".venv" / "pyvenv.cfg").write_text(
        "home = /usr/bin\n",
        encoding="utf-8",
    )
    quoted_deps = ", ".join(f'"{dependency}"' for dependency in dependencies)
    (project / "pyproject.toml").write_text(
        f"""
[project]
name = "demo"
version = "0.1.0"
dependencies = [{quoted_deps}]
""",
        encoding="utf-8",
    )
    return project


def write_distribution_skill(
    site_packages: Path,
    *,
    dist_name: str,
    package_dir: str,
    skill_name: str,
) -> Path:
    skill_dir = site_packages / package_dir / ".agents" / "skills" / skill_name
    skill_dir.mkdir(parents=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        f"---\nname: {skill_name}\ndescription: Demo skill.\n---\n",
        encoding="utf-8",
    )

    dist_info = site_packages / f"{package_dir}-1.0.0.dist-info"
    dist_info.mkdir(exist_ok=True)
    dist_info.joinpath("METADATA").write_text(
        f"Metadata-Version: 2.4\nName: {dist_name}\nVersion: 1.0.0\n",
        encoding="utf-8",
    )
    dist_info.joinpath("RECORD").write_text(
        f"{skill_md.relative_to(site_packages).as_posix()},,\n",
        encoding="utf-8",
    )
    return skill_dir


def write_distribution(
    site_packages: Path,
    *,
    dist_name: str,
    package_dir: str,
    skill_names: list[str],
) -> list[Path]:
    skill_dirs = [
        write_distribution_skill(
            site_packages,
            dist_name=dist_name,
            package_dir=package_dir,
            skill_name=skill_name,
        )
        for skill_name in skill_names
    ]
    dist_info = site_packages / f"{package_dir}-1.0.0.dist-info"
    record_paths = [
        (skill_dir / "SKILL.md").relative_to(site_packages).as_posix()
        for skill_dir in skill_dirs
    ]
    dist_info.joinpath("RECORD").write_text(
        "".join(f"{record_path},,\n" for record_path in record_paths),
        encoding="utf-8",
    )
    return skill_dirs


def test_scan_filters_to_top_level_dependencies_by_default(tmp_path, monkeypatch):
    project = write_project(tmp_path, dependencies=["top-pkg>=1"])
    site_packages = project / ".venv" / "lib" / "python3.12" / "site-packages"
    write_distribution_skill(
        site_packages,
        dist_name="top-pkg",
        package_dir="top_pkg",
        skill_name="top-skill",
    )
    write_distribution_skill(
        site_packages,
        dist_name="transitive-pkg",
        package_dir="transitive_pkg",
        skill_name="transitive-skill",
    )
    monkeypatch.chdir(project)

    result = runner.invoke(app, ["scan"])
    all_result = runner.invoke(app, ["scan", "--all"])

    assert result.exit_code == 0
    assert "top-skill" in result.output
    assert "transitive-skill" not in result.output
    assert all_result.exit_code == 0
    assert "top-skill" in all_result.output
    assert "transitive-skill" in all_result.output


def test_install_skill_can_explicitly_select_transitive_dependency(
    tmp_path, monkeypatch
):
    project = write_project(tmp_path, dependencies=["top-pkg>=1"])
    site_packages = project / ".venv" / "lib" / "python3.12" / "site-packages"
    transitive_skill = write_distribution_skill(
        site_packages,
        dist_name="transitive-pkg",
        package_dir="transitive_pkg",
        skill_name="transitive-skill",
    )
    monkeypatch.chdir(project)

    result = runner.invoke(app, ["install", "--skill", "transitive-skill", "--yes"])

    installed = project / ".agents" / "skills" / "transitive-skill"
    assert result.exit_code == 0
    assert installed.is_symlink()
    assert installed.resolve() == transitive_skill.resolve()


def test_yes_repairs_broken_managed_symlink_without_installing_new_skills(
    tmp_path,
    monkeypatch,
):
    project = write_project(tmp_path, dependencies=["demo-pkg>=1"])
    site_packages = project / ".venv" / "lib" / "python3.12" / "site-packages"
    repaired_skill, _new_skill = write_distribution(
        site_packages,
        dist_name="demo-pkg",
        package_dir="demo_pkg",
        skill_names=["repaired-skill", "new-skill"],
    )
    installed_dir = project / ".agents" / "skills"
    installed_dir.mkdir(parents=True)
    broken_link = installed_dir / "repaired-skill"
    broken_link.symlink_to(project / "missing")
    monkeypatch.chdir(project)

    result = runner.invoke(app, ["--yes"])

    assert result.exit_code == 0
    assert broken_link.is_symlink()
    assert broken_link.resolve() == repaired_skill.resolve()
    assert not (installed_dir / "new-skill").exists()
