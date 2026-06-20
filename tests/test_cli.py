import importlib
import json
import sys
from pathlib import Path
from unittest.mock import patch

from rich.console import Console
from typer.testing import CliRunner

import library_skills.cli as cli
from library_skills.cli import app

runner = CliRunner()


class FakeToolkit:
    def __init__(self, value):
        self.value = value

    def ask(self, *args, **kwargs):
        return self.value


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


def write_workspace(tmp_path: Path) -> Path:
    project = tmp_path / "workspace"
    site_packages = project / ".venv" / "lib" / "python3.12" / "site-packages"
    site_packages.mkdir(parents=True)
    (project / ".venv" / "pyvenv.cfg").write_text(
        "home = /usr/bin\n",
        encoding="utf-8",
    )
    (project / "pyproject.toml").write_text(
        """
[project]
name = "workspace-root"
version = "0.1.0"
dependencies = ["root-pkg>=1"]

[tool.uv.workspace]
members = ["packages/*"]
""",
        encoding="utf-8",
    )
    api = project / "packages" / "api"
    worker = project / "packages" / "worker"
    api.mkdir(parents=True)
    worker.mkdir(parents=True)
    (api / "pyproject.toml").write_text(
        """
[project]
name = "api"
version = "0.1.0"
dependencies = ["api-pkg>=1", "workspace-lib"]

[tool.uv.sources]
workspace-lib = { workspace = true }
""",
        encoding="utf-8",
    )
    (worker / "pyproject.toml").write_text(
        """
[project]
name = "worker"
version = "0.1.0"
dependencies = ["worker-pkg>=1"]
""",
        encoding="utf-8",
    )
    return project


def write_node_workspace(tmp_path: Path) -> Path:
    project = tmp_path / "node-workspace"
    (project / "node_modules").mkdir(parents=True)
    (project / "package.json").write_text(
        json.dumps(
            {
                "name": "workspace-root",
                "workspaces": ["packages/*"],
                "dependencies": {"root-pkg": "^1.0.0"},
            }
        ),
        encoding="utf-8",
    )
    api = project / "packages" / "api"
    worker = project / "packages" / "worker"
    api.mkdir(parents=True)
    worker.mkdir(parents=True)
    (api / "package.json").write_text(
        json.dumps(
            {
                "name": "api",
                "dependencies": {"api-pkg": "^1.0.0"},
                "devDependencies": {"workspace-lib": "workspace:*"},
            }
        ),
        encoding="utf-8",
    )
    (worker / "package.json").write_text(
        json.dumps(
            {
                "name": "worker",
                "optionalDependencies": {"worker-pkg": "^1.0.0"},
            }
        ),
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


def write_node_package_skill(
    project: Path,
    *,
    package_name: str,
    skill_name: str,
) -> Path:
    package_root = project / "node_modules" / package_name
    return write_node_package_skill_at(
        package_root,
        package_name=package_name,
        skill_name=skill_name,
    )


def write_node_package_skill_at(
    package_root: Path,
    *,
    package_name: str,
    skill_name: str,
) -> Path:
    skill_dir = package_root / ".agents" / "skills" / skill_name
    skill_dir.mkdir(parents=True)
    skill_dir.joinpath("SKILL.md").write_text(
        f"---\nname: {skill_name}\ndescription: Node skill.\n---\n",
        encoding="utf-8",
    )
    package_root.joinpath("package.json").write_text(
        json.dumps({"name": package_name, "version": "2.0.0"}),
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


def make_cli_skill(tmp_path: Path, name: str = "demo-skill") -> cli.Skill:
    skill_dir = tmp_path / "source" / ".agents" / "skills" / name
    skill_dir.mkdir(parents=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        f"---\nname: {name}\ndescription: Demo skill.\n---\n",
        encoding="utf-8",
    )
    return cli.Skill(
        name=name,
        description="Demo skill.",
        path=skill_md,
        package_name="demo-pkg",
        package_version="1.0.0",
        skill_dir=skill_dir,
    )


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
    assert "Target Python environment: .venv" in result.output
    assert "Site-packages: .venv" in result.output
    assert "top-skill" in result.output
    assert "transitive-skill" not in result.output
    assert all_result.exit_code == 0
    assert "top-skill" in all_result.output
    assert "transitive-skill" in all_result.output


def test_workspace_member_scan_uses_workspace_venv_and_member_deps(
    tmp_path,
    monkeypatch,
):
    project = write_workspace(tmp_path)
    api = project / "packages" / "api"
    member_venv = api / ".venv"
    member_venv.mkdir()
    site_packages = project / ".venv" / "lib" / "python3.12" / "site-packages"
    api_skill = write_distribution_skill(
        site_packages,
        dist_name="api-pkg",
        package_dir="api_pkg",
        skill_name="api-skill",
    )
    write_distribution_skill(
        site_packages,
        dist_name="workspace-lib",
        package_dir="workspace_lib",
        skill_name="workspace-lib-skill",
    )
    write_distribution_skill(
        site_packages,
        dist_name="root-pkg",
        package_dir="root_pkg",
        skill_name="root-skill",
    )
    write_distribution_skill(
        site_packages,
        dist_name="worker-pkg",
        package_dir="worker_pkg",
        skill_name="worker-skill",
    )
    write_distribution_skill(
        site_packages,
        dist_name="transitive-pkg",
        package_dir="transitive_pkg",
        skill_name="transitive-skill",
    )
    (api / "src").mkdir()
    monkeypatch.chdir(api / "src")

    result = runner.invoke(app, ["scan", "--json"])
    install_result = runner.invoke(
        app, ["install", "--skill", "api-skill", "--yes", "--claude"]
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["project_root"] == str(project)
    assert payload["workspace_root"] == str(project)
    assert payload["workspace_member"] == str(api.resolve())
    assert payload["dependency_files"] == [str(api.resolve() / "pyproject.toml")]
    assert payload["target_environment"] == str(project / ".venv")
    assert "Ignoring member-local .venv" in "\n".join(payload["warnings"])
    assert [skill["name"] for skill in payload["skills"]] == [
        "api-skill",
        "workspace-lib-skill",
    ]
    assert install_result.exit_code == 0
    installed = project / ".agents" / "skills" / "api-skill"
    claude_installed = project / ".claude" / "skills" / "api-skill"
    assert installed.is_symlink()
    assert installed.resolve() == api_skill.resolve()
    assert claude_installed.is_symlink()
    assert claude_installed.resolve() == api_skill.resolve()
    assert not (api / ".agents" / "skills" / "api-skill").exists()


def test_workspace_root_scan_uses_root_and_all_member_deps(tmp_path, monkeypatch):
    project = write_workspace(tmp_path)
    site_packages = project / ".venv" / "lib" / "python3.12" / "site-packages"
    for dist_name, package_dir, skill_name in [
        ("api-pkg", "api_pkg", "api-skill"),
        ("workspace-lib", "workspace_lib", "workspace-lib-skill"),
        ("root-pkg", "root_pkg", "root-skill"),
        ("worker-pkg", "worker_pkg", "worker-skill"),
        ("transitive-pkg", "transitive_pkg", "transitive-skill"),
    ]:
        write_distribution_skill(
            site_packages,
            dist_name=dist_name,
            package_dir=package_dir,
            skill_name=skill_name,
        )
    monkeypatch.chdir(project)

    result = runner.invoke(app, ["scan", "--json"])
    all_result = runner.invoke(app, ["scan", "--json", "--all"])

    payload = json.loads(result.output)
    all_payload = json.loads(all_result.output)
    assert result.exit_code == 0
    assert payload["workspace_member"] == ""
    assert payload["dependency_files"] == [
        str(project / "pyproject.toml"),
        str((project / "packages" / "api").resolve() / "pyproject.toml"),
        str((project / "packages" / "worker").resolve() / "pyproject.toml"),
    ]
    assert [skill["name"] for skill in payload["skills"]] == [
        "api-skill",
        "root-skill",
        "worker-skill",
        "workspace-lib-skill",
    ]
    assert "transitive-skill" not in [skill["name"] for skill in payload["skills"]]
    assert "transitive-skill" in [skill["name"] for skill in all_payload["skills"]]


def test_workspace_non_member_subdir_uses_root_and_all_member_deps(
    tmp_path,
    monkeypatch,
):
    project = write_workspace(tmp_path)
    docs = project / "docs"
    docs.mkdir()
    site_packages = project / ".venv" / "lib" / "python3.12" / "site-packages"
    for dist_name, package_dir, skill_name in [
        ("api-pkg", "api_pkg", "api-skill"),
        ("root-pkg", "root_pkg", "root-skill"),
        ("worker-pkg", "worker_pkg", "worker-skill"),
    ]:
        write_distribution_skill(
            site_packages,
            dist_name=dist_name,
            package_dir=package_dir,
            skill_name=skill_name,
        )
    monkeypatch.chdir(docs)

    result = runner.invoke(app, ["scan", "--json"])

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["workspace_member"] == ""
    assert [skill["name"] for skill in payload["skills"]] == [
        "api-skill",
        "root-skill",
        "worker-skill",
    ]


def test_workspace_scan_prints_workspace_context(tmp_path, monkeypatch):
    project = write_workspace(tmp_path)
    api = project / "packages" / "api"
    site_packages = project / ".venv" / "lib" / "python3.12" / "site-packages"
    write_distribution_skill(
        site_packages,
        dist_name="api-pkg",
        package_dir="api_pkg",
        skill_name="api-skill",
    )
    monkeypatch.chdir(api)

    with patch.object(cli, "console", Console(width=1000)):
        result = runner.invoke(app, ["scan"])

    assert result.exit_code == 0
    assert f"Workspace root: {project}" in result.output
    assert f"Workspace member: {api.resolve()}" in result.output


def test_node_workspace_member_scan_uses_member_deps_and_root_node_modules(
    tmp_path,
    monkeypatch,
):
    project = write_node_workspace(tmp_path)
    api = project / "packages" / "api"
    for package_name, skill_name in [
        ("api-pkg", "api-skill"),
        ("workspace-lib", "workspace-lib-skill"),
        ("root-pkg", "root-skill"),
        ("worker-pkg", "worker-skill"),
        ("transitive-node-pkg", "transitive-node-skill"),
    ]:
        write_node_package_skill(
            project, package_name=package_name, skill_name=skill_name
        )
    (api / "src").mkdir()
    monkeypatch.chdir(api / "src")

    result = runner.invoke(app, ["scan", "--json"])

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["project_root"] == str(project)
    assert payload["workspace_root"] == str(project)
    assert payload["workspace_member"] == str(api.resolve())
    assert payload["dependency_files"] == [str(api.resolve() / "package.json")]
    assert payload["node_modules"] == str(project / "node_modules")
    assert [skill["name"] for skill in payload["skills"]] == [
        "api-skill",
        "workspace-lib-skill",
    ]


def test_node_workspace_root_scan_uses_root_and_all_member_deps(tmp_path, monkeypatch):
    project = write_node_workspace(tmp_path)
    for package_name, skill_name in [
        ("api-pkg", "api-skill"),
        ("workspace-lib", "workspace-lib-skill"),
        ("root-pkg", "root-skill"),
        ("worker-pkg", "worker-skill"),
        ("transitive-node-pkg", "transitive-node-skill"),
    ]:
        write_node_package_skill(
            project, package_name=package_name, skill_name=skill_name
        )
    monkeypatch.chdir(project)

    result = runner.invoke(app, ["scan", "--json"])
    all_result = runner.invoke(app, ["scan", "--json", "--all"])

    payload = json.loads(result.output)
    all_payload = json.loads(all_result.output)
    assert result.exit_code == 0
    assert payload["workspace_member"] == ""
    assert payload["dependency_files"] == [
        str(project / "package.json"),
        str((project / "packages" / "api").resolve() / "package.json"),
        str((project / "packages" / "worker").resolve() / "package.json"),
    ]
    assert [skill["name"] for skill in payload["skills"]] == [
        "api-skill",
        "root-skill",
        "worker-skill",
        "workspace-lib-skill",
    ]
    assert "transitive-node-skill" not in [skill["name"] for skill in payload["skills"]]
    assert "transitive-node-skill" in [skill["name"] for skill in all_payload["skills"]]


def test_node_workspace_non_member_subdir_uses_root_and_all_member_deps(
    tmp_path,
    monkeypatch,
):
    project = write_node_workspace(tmp_path)
    docs = project / "docs"
    docs.mkdir()
    for package_name, skill_name in [
        ("api-pkg", "api-skill"),
        ("root-pkg", "root-skill"),
        ("worker-pkg", "worker-skill"),
    ]:
        write_node_package_skill(
            project, package_name=package_name, skill_name=skill_name
        )
    monkeypatch.chdir(docs)

    result = runner.invoke(app, ["scan", "--json"])

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["workspace_member"] == ""
    assert [skill["name"] for skill in payload["skills"]] == [
        "api-skill",
        "root-skill",
        "worker-skill",
    ]


def test_node_workspace_member_local_node_modules_is_not_ignored(tmp_path, monkeypatch):
    project = write_node_workspace(tmp_path)
    api = project / "packages" / "api"
    write_node_package_skill(
        project, package_name="api-pkg", skill_name="root-api-skill"
    )
    write_node_package_skill_at(
        api / "node_modules" / "api-pkg",
        package_name="api-pkg",
        skill_name="member-api-skill",
    )
    monkeypatch.chdir(api)

    result = runner.invoke(app, ["scan", "--json"])

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["node_modules"] == str(api / "node_modules")
    assert [skill["name"] for skill in payload["skills"]] == ["member-api-skill"]


def test_scan_includes_python_and_node_package_skills(tmp_path, monkeypatch):
    project = write_project(tmp_path, dependencies=["top-pkg>=1"])
    site_packages = project / ".venv" / "lib" / "python3.12" / "site-packages"
    write_distribution_skill(
        site_packages,
        dist_name="top-pkg",
        package_dir="top_pkg",
        skill_name="python-skill",
    )
    write_distribution_skill(
        site_packages,
        dist_name="transitive-pkg",
        package_dir="transitive_pkg",
        skill_name="transitive-skill",
    )
    write_node_package_skill(
        project,
        package_name="@scope/node-pkg",
        skill_name="node-skill",
    )
    write_node_package_skill(
        project,
        package_name="transitive-node-pkg",
        skill_name="transitive-node-skill",
    )
    project.joinpath("package.json").write_text(
        json.dumps({"devDependencies": {"@scope/node-pkg": "^2.0.0"}}),
        encoding="utf-8",
    )
    monkeypatch.chdir(project)

    result = runner.invoke(app, ["scan"])
    all_result = runner.invoke(app, ["scan", "--all"])
    json_result = runner.invoke(app, ["scan", "--json", "--all"])

    assert result.exit_code == 0
    assert "Target Python environment: .venv" in result.output
    assert "node_modules: node_modules" in result.output
    assert "python-skill" in result.output
    assert "node-skill" in result.output
    assert "transitive-skill" not in result.output
    assert "transitive-node-skill" not in result.output
    assert all_result.exit_code == 0
    assert "transitive-skill" in all_result.output
    assert "transitive-node-skill" in all_result.output
    assert json_result.exit_code == 0
    payload = json.loads(json_result.output)
    assert payload["project_root"] == str(project)
    assert "installed" not in payload
    assert [skill["name"] for skill in payload["skills"]] == [
        "python-skill",
        "transitive-skill",
        "node-skill",
        "transitive-node-skill",
    ]


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


def test_list_json_reports_discovered_and_installed_skills(tmp_path, monkeypatch):
    project = write_project(tmp_path, dependencies=["demo-pkg>=1"])
    site_packages = project / ".venv" / "lib" / "python3.12" / "site-packages"
    skill_dir = write_distribution_skill(
        site_packages,
        dist_name="demo-pkg",
        package_dir="demo_pkg",
        skill_name="demo-skill",
    )
    installed_dir = project / ".agents" / "skills"
    installed_dir.mkdir(parents=True)
    (installed_dir / "demo-skill").symlink_to(skill_dir, target_is_directory=True)
    monkeypatch.chdir(project)

    with patch.object(cli, "console", Console(width=1000)):
        result = runner.invoke(app, ["list", "--json"])

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["skills"][0]["name"] == "demo-skill"
    assert payload["installed"][0]["status"] == "up to date"


def test_list_installed_prints_no_skills_when_target_is_empty(tmp_path, monkeypatch):
    project = write_project(tmp_path, dependencies=[])
    monkeypatch.chdir(project)

    result = runner.invoke(app, ["list", "--installed"])

    assert result.exit_code == 0
    assert "No skills installed." in result.output


def test_list_installed_prints_installed_statuses(tmp_path, monkeypatch):
    project = write_project(tmp_path, dependencies=["demo-pkg>=1"])
    site_packages = project / ".venv" / "lib" / "python3.12" / "site-packages"
    skill_dir = write_distribution_skill(
        site_packages,
        dist_name="demo-pkg",
        package_dir="demo_pkg",
        skill_name="demo-skill",
    )
    installed_dir = project / ".agents" / "skills"
    installed_dir.mkdir(parents=True)
    (installed_dir / "demo-skill").symlink_to(skill_dir, target_is_directory=True)
    monkeypatch.chdir(project)

    result = runner.invoke(app, ["list", "--installed"])

    assert result.exit_code == 0
    assert "up to date" in result.output
    assert ".agents" in result.output
    assert str(project / ".agents") not in result.output


def test_install_all_copy_mode_installs_to_agents_and_claude(tmp_path, monkeypatch):
    project = write_project(tmp_path, dependencies=["demo-pkg>=1"])
    site_packages = project / ".venv" / "lib" / "python3.12" / "site-packages"
    write_distribution_skill(
        site_packages,
        dist_name="demo-pkg",
        package_dir="demo_pkg",
        skill_name="demo-skill",
    )
    monkeypatch.chdir(project)

    result = runner.invoke(app, ["install", "--all", "--yes", "--copy", "--claude"])

    agents_skill = project / ".agents" / "skills" / "demo-skill"
    claude_skill = project / ".claude" / "skills" / "demo-skill"
    assert result.exit_code == 0
    assert agents_skill.is_dir()
    assert not agents_skill.is_symlink()
    assert claude_skill.is_dir()
    assert not claude_skill.is_symlink()


def test_install_without_selection_and_yes_prints_no_skills_selected(
    tmp_path,
    monkeypatch,
):
    project = write_project(tmp_path, dependencies=[])
    monkeypatch.chdir(project)

    result = runner.invoke(app, ["install", "--yes"])

    assert result.exit_code == 0
    assert "No skills selected." in result.output


def test_remove_named_symlink(tmp_path, monkeypatch):
    project = write_project(tmp_path, dependencies=["demo-pkg>=1"])
    site_packages = project / ".venv" / "lib" / "python3.12" / "site-packages"
    skill_dir = write_distribution_skill(
        site_packages,
        dist_name="demo-pkg",
        package_dir="demo_pkg",
        skill_name="demo-skill",
    )
    installed_dir = project / ".agents" / "skills"
    installed_dir.mkdir(parents=True)
    installed = installed_dir / "demo-skill"
    installed.symlink_to(skill_dir, target_is_directory=True)
    monkeypatch.chdir(project)

    result = runner.invoke(app, ["remove", "demo-skill"])

    assert result.exit_code == 0
    assert "Removed:" in result.output
    assert not installed.exists()


def test_remove_with_yes_and_no_names_does_not_prompt(tmp_path, monkeypatch):
    project = write_project(tmp_path, dependencies=[])
    monkeypatch.chdir(project)

    result = runner.invoke(app, ["remove", "--yes"])

    assert result.exit_code == 0
    assert "No skills selected." in result.output


def test_check_exits_non_zero_for_colliding_skill_names(tmp_path, monkeypatch):
    project = write_project(tmp_path, dependencies=["first-pkg>=1", "second-pkg>=1"])
    site_packages = project / ".venv" / "lib" / "python3.12" / "site-packages"
    write_distribution_skill(
        site_packages,
        dist_name="first-pkg",
        package_dir="first_pkg",
        skill_name="duplicate-skill",
    )
    write_distribution_skill(
        site_packages,
        dist_name="second-pkg",
        package_dir="second_pkg",
        skill_name="duplicate-skill",
    )
    monkeypatch.chdir(project)

    result = runner.invoke(app, ["--check"])

    assert result.exit_code == 1


def test_scan_without_target_environment_prints_warning(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    monkeypatch.delenv("UV_PROJECT_ENVIRONMENT", raising=False)
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    monkeypatch.delenv("CONDA_PREFIX", raising=False)

    result = runner.invoke(app, ["scan"])

    assert result.exit_code == 0
    assert "Run from a project root after installing dependencies" in result.output
    assert "uv sync" in result.output
    assert "npm install" in result.output


def test_default_check_without_environment_reports_no_discovered_skills(
    tmp_path,
    monkeypatch,
):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    monkeypatch.delenv("UV_PROJECT_ENVIRONMENT", raising=False)
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    monkeypatch.delenv("CONDA_PREFIX", raising=False)

    result = runner.invoke(app, ["--check"])

    assert result.exit_code == 0
    assert "No installed or discovered skills found." in result.output


def test_list_without_installed_option_prints_discovered_skills(tmp_path, monkeypatch):
    project = write_project(tmp_path, dependencies=["demo-pkg>=1"])
    site_packages = project / ".venv" / "lib" / "python3.12" / "site-packages"
    write_distribution_skill(
        site_packages,
        dist_name="demo-pkg",
        package_dir="demo_pkg",
        skill_name="demo-skill",
    )
    monkeypatch.chdir(project)

    result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    assert "demo-skill" in result.output


def test_install_interactive_selection_installs_selected_skill(
    tmp_path,
    monkeypatch,
):
    project = write_project(tmp_path, dependencies=["demo-pkg>=1"])
    site_packages = project / ".venv" / "lib" / "python3.12" / "site-packages"
    skill_dir = write_distribution_skill(
        site_packages,
        dist_name="demo-pkg",
        package_dir="demo_pkg",
        skill_name="demo-skill",
    )
    monkeypatch.chdir(project)

    with patch.object(cli, "_select_skills_interactive", lambda skills: skills):
        result = runner.invoke(app, ["install"])

    installed = project / ".agents" / "skills" / "demo-skill"
    assert result.exit_code == 0
    assert installed.is_symlink()
    assert installed.resolve() == skill_dir.resolve()


def test_default_command_interactive_selection_installs_selected_skill(
    tmp_path,
    monkeypatch,
):
    project = write_project(tmp_path, dependencies=["demo-pkg>=1"])
    site_packages = project / ".venv" / "lib" / "python3.12" / "site-packages"
    skill_dir = write_distribution_skill(
        site_packages,
        dist_name="demo-pkg",
        package_dir="demo_pkg",
        skill_name="demo-skill",
    )
    monkeypatch.chdir(project)

    with patch.object(cli, "_select_skills_interactive", lambda skills: skills):
        result = runner.invoke(app)

    installed = project / ".agents" / "skills" / "demo-skill"
    assert result.exit_code == 0
    assert "Installed 1 skill target(s)." in result.output
    assert installed.is_symlink()
    assert installed.resolve() == skill_dir.resolve()


def test_remove_interactive_selection_removes_selected_skill(tmp_path, monkeypatch):
    project = write_project(tmp_path, dependencies=["demo-pkg>=1"])
    site_packages = project / ".venv" / "lib" / "python3.12" / "site-packages"
    skill_dir = write_distribution_skill(
        site_packages,
        dist_name="demo-pkg",
        package_dir="demo_pkg",
        skill_name="demo-skill",
    )
    installed_dir = project / ".agents" / "skills"
    installed_dir.mkdir(parents=True)
    installed = installed_dir / "demo-skill"
    installed.symlink_to(skill_dir, target_is_directory=True)
    monkeypatch.chdir(project)

    with patch.object(
        cli, "_select_installed_skills_interactive", lambda statuses: statuses
    ):
        result = runner.invoke(app, ["remove"])

    assert result.exit_code == 0
    assert not installed.exists()


def test_remove_prints_not_found_when_uninstall_returns_false(tmp_path, monkeypatch):
    project = write_project(tmp_path, dependencies=["demo-pkg>=1"])
    site_packages = project / ".venv" / "lib" / "python3.12" / "site-packages"
    skill_dir = write_distribution_skill(
        site_packages,
        dist_name="demo-pkg",
        package_dir="demo_pkg",
        skill_name="demo-skill",
    )
    installed_dir = project / ".agents" / "skills"
    installed_dir.mkdir(parents=True)
    (installed_dir / "demo-skill").symlink_to(skill_dir, target_is_directory=True)
    monkeypatch.chdir(project)

    with patch.object(cli, "uninstall_skill", lambda skill_name, target_dir: False):
        result = runner.invoke(app, ["remove", "demo-skill"])

    assert result.exit_code == 0
    assert "Not found:" in result.output


def test_installed_statuses_classifies_name_mismatch_outdated_and_orphaned(tmp_path):
    skill = make_cli_skill(tmp_path)
    target = cli.InstallTarget("universal", tmp_path / ".agents" / "skills")
    target.path.mkdir(parents=True)
    (target.path / "wrong-name").symlink_to(skill.skill_dir, target_is_directory=True)
    old_target = tmp_path / "old-target"
    old_target.mkdir()
    (target.path / skill.name).symlink_to(old_target, target_is_directory=True)
    orphan_target = tmp_path / "orphan-target"
    orphan_target.mkdir()
    (target.path / "orphan-skill").symlink_to(orphan_target, target_is_directory=True)
    hand_authored = target.path / "hand-authored"
    hand_authored.mkdir()

    statuses = {
        status.name: status.status
        for status in cli._installed_statuses(targets=[target], skills=[skill])
    }

    assert statuses["wrong-name"] == "name mismatch"
    assert statuses[skill.name] == "outdated"
    assert statuses["orphan-skill"] == "orphaned"
    assert statuses["hand-authored"] == "hand-authored"


def test_filter_installable_skills_skips_collisions(tmp_path):
    first = make_cli_skill(tmp_path / "first", name="duplicate-skill")
    second = make_cli_skill(tmp_path / "second", name="duplicate-skill")

    selected = cli._filter_installable_skills(
        [first, second],
        selected_names=[],
        include_all=True,
    )

    assert selected == []


def test_select_helpers_use_rich_toolkit(monkeypatch, tmp_path):
    skill = make_cli_skill(tmp_path)
    target = cli.InstallTarget("universal", tmp_path / ".agents" / "skills")
    status = cli.InstalledStatus(
        target=target,
        name=skill.name,
        type="symlink",
        path=target.path / skill.name,
        target_path=skill.skill_dir,
        status="up to date",
        skill=skill,
    )
    monkeypatch.setattr(cli, "_get_rich_toolkit", lambda: FakeToolkit([skill]))

    assert cli._select_skills_interactive([skill]) == [skill]

    monkeypatch.setattr(cli, "_get_rich_toolkit", lambda: FakeToolkit([status]))

    assert cli._select_installed_skills_interactive([status]) == [status]
    assert (
        cli._select_installed_skills_interactive(
            [
                cli.InstalledStatus(
                    target,
                    "dir",
                    "directory",
                    target.path / "dir",
                    None,
                    "hand-authored",
                )
            ]
        )
        == []
    )


def test_get_rich_toolkit_returns_toolkit_instance():
    assert cli._get_rich_toolkit() is not None


def test_install_selected_continues_after_install_error(tmp_path):
    skill = make_cli_skill(tmp_path)
    target = cli.InstallTarget("universal", tmp_path / ".agents" / "skills")
    (target.path / skill.name).mkdir(parents=True)

    assert (
        cli._install_selected(skills=[skill], targets=[target], project_root=tmp_path)
        == 0
    )


def test_display_path_prefers_project_relative_paths(tmp_path):
    project = tmp_path / "project"
    inside = project / ".agents" / "skills" / "demo"
    outside = tmp_path / "outside"
    inside.mkdir(parents=True)
    outside.mkdir()

    assert cli._display_path(inside, project) == str(
        Path(".agents") / "skills" / "demo"
    )
    assert cli._display_path(outside, project) == str(outside)
    assert cli._display_path(None, project) == ""


def test_main_module_invokes_cli_main():
    import library_skills.cli as cli

    called = []
    sys.modules.pop("library_skills.__main__", None)

    with patch.object(cli, "main", lambda: called.append(True)):
        importlib.import_module("library_skills.__main__")

    assert called == [True]
    sys.modules.pop("library_skills.__main__", None)


def test_main_invokes_typer_app():
    called = []

    with patch.object(cli, "app", lambda: called.append(True)):
        cli.main()

    assert called == [True]
