import library_skills.workspace as workspace
from library_skills.python_env import find_project_root


def test_find_uv_workspace_handles_invalid_and_missing_workspace_tables(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    pyproject = project / "pyproject.toml"

    pyproject.write_text("[tool.uv.workspace\n", encoding="utf-8")
    assert workspace.find_uv_workspace(project) is None
    assert workspace._read_pyproject(pyproject) == {}

    assert workspace._has_uv_workspace({}) is False
    assert workspace._has_uv_workspace({"tool": {"uv": "not-table"}}) is False
    assert workspace._find_workspace_members(project, {}) == []
    assert (
        workspace._find_workspace_members(project, {"tool": {"uv": {"workspace": {}}}})
        == []
    )
    assert workspace._get_workspace_table({}) is None
    assert workspace._get_workspace_table({"tool": {"uv": "not-table"}}) is None


def test_find_uv_workspace_filters_members_and_selects_nearest_member(tmp_path):
    project = tmp_path / "project"
    api = project / "packages" / "api"
    nested_member = api / "plugins" / "demo"
    ignored = project / "packages" / "ignored"
    skipped = project / "packages" / "skip-one"
    not_project = project / "packages" / "not-project"
    file_match = project / "packages" / "file"
    for directory in (api, nested_member, ignored, skipped, not_project):
        directory.mkdir(parents=True)
    file_match.parent.mkdir(parents=True, exist_ok=True)
    file_match.write_text("not a directory", encoding="utf-8")
    for directory in (api, nested_member, ignored, skipped):
        (directory / "pyproject.toml").write_text(
            "[project]\nname = 'demo'\n", encoding="utf-8"
        )
    (project / "pyproject.toml").write_text(
        """
[tool.uv.workspace]
members = [1, "packages/*", "packages/api/plugins/*"]
exclude = [1, "packages/ignored", "packages/skip-*"]
""",
        encoding="utf-8",
    )

    found = workspace.find_uv_workspace(nested_member)

    assert found is not None
    assert found.root == project
    assert found.members == (api.resolve(), nested_member.resolve())
    assert found.current_member == nested_member.resolve()
    assert workspace.workspace_dependency_files(found) == [
        nested_member.resolve() / "pyproject.toml"
    ]


def test_find_node_workspace_filters_members_and_selects_nearest_member(tmp_path):
    project = tmp_path / "project"
    api = project / "packages" / "api"
    nested_member = api / "plugins" / "demo"
    ignored = project / "packages" / "ignored"
    skipped = project / "packages" / "skip-one"
    not_project = project / "packages" / "not-project"
    file_match = project / "packages" / "file"
    for directory in (api, nested_member, ignored, skipped, not_project):
        directory.mkdir(parents=True)
    file_match.parent.mkdir(parents=True, exist_ok=True)
    file_match.write_text("not a directory", encoding="utf-8")
    for directory in (api, nested_member, ignored):
        (directory / "package.json").write_text('{"name": "demo"}', encoding="utf-8")
    (project / "package.json").write_text(
        """
{
  "workspaces": [
    1,
    "packages/*",
    "packages/api/plugins/*",
    "!packages/ignored",
    "!packages/skip-*"
  ]
}
""",
        encoding="utf-8",
    )

    found = workspace.find_node_workspace(nested_member)

    assert found is not None
    assert found.root == project
    assert found.members == (api.resolve(), nested_member.resolve())
    assert found.current_member == nested_member.resolve()
    assert workspace.node_workspace_dependency_files(found) == [
        nested_member.resolve() / "package.json"
    ]
    assert find_project_root(nested_member) == project


def test_find_node_workspace_supports_npm_object_form(tmp_path):
    project = tmp_path / "project"
    api = project / "apps" / "api"
    api.mkdir(parents=True)
    (api / "package.json").write_text('{"name": "api"}', encoding="utf-8")
    (project / "package.json").write_text(
        '{"workspaces": {"packages": ["apps/*"]}}',
        encoding="utf-8",
    )

    found = workspace.find_node_workspace(api)

    assert found is not None
    assert found.root == project
    assert found.members == (api.resolve(),)


def test_find_node_workspace_handles_invalid_and_non_object_package_json(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    package_json = project / "package.json"

    package_json.write_text("{", encoding="utf-8")
    assert workspace.find_node_workspace(project) is None
    assert workspace._read_package_json(package_json) == {}

    package_json.write_text("[]", encoding="utf-8")
    assert workspace.find_node_workspace(project) is None
    assert workspace._read_package_json(package_json) == {}
