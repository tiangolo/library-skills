from library_skills.deps import (
    get_node_top_level_deps,
    get_python_top_level_deps,
    get_top_level_deps,
)


def test_get_python_top_level_deps_normalizes_required_and_optional_deps(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
dependencies = [
    "Rich-Toolkit>=0.19",
    "pydantic[email]>=2 ; python_version >= '3.10'",
]

[project.optional-dependencies]
dev = [
    "PyTest_Cov>=4",
]
""",
        encoding="utf-8",
    )

    assert get_python_top_level_deps(tmp_path) == {
        "rich-toolkit",
        "pydantic",
        "pytest-cov",
    }


def test_get_python_top_level_deps_returns_none_without_pyproject(tmp_path):
    assert get_python_top_level_deps(tmp_path) is None


def test_get_python_top_level_deps_returns_none_for_invalid_toml(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project\n", encoding="utf-8")

    assert get_python_top_level_deps(tmp_path) is None


def test_get_python_top_level_deps_returns_empty_set_for_invalid_project_table(
    tmp_path,
):
    (tmp_path / "pyproject.toml").write_text('project = "demo"\n', encoding="utf-8")

    assert get_python_top_level_deps(tmp_path) == set()


def test_get_python_top_level_deps_ignores_non_string_dependencies(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
dependencies = [
    "rich>=13",
    1,
]
""",
        encoding="utf-8",
    )

    assert get_python_top_level_deps(tmp_path) == {"rich"}


def test_get_node_top_level_deps_normalizes_dependency_fields(tmp_path):
    (tmp_path / "package.json").write_text(
        """
{
  "dependencies": {"@Scope/Demo_Pkg": "^1.0.0"},
  "devDependencies": {"Vitest": "^4.0.0"},
  "optionalDependencies": {"Optional.Pkg": "^1.0.0"},
  "peerDependencies": {"Peer_Pkg": "^1.0.0"}
}
""",
        encoding="utf-8",
    )

    assert get_node_top_level_deps(tmp_path) == {
        "@scope/demo-pkg",
        "vitest",
        "optional-pkg",
        "peer-pkg",
    }


def test_get_node_top_level_deps_handles_missing_invalid_and_non_object(tmp_path):
    assert get_node_top_level_deps(tmp_path) is None

    (tmp_path / "package.json").write_text("{", encoding="utf-8")
    assert get_node_top_level_deps(tmp_path) is None

    (tmp_path / "package.json").write_text("[]", encoding="utf-8")
    assert get_node_top_level_deps(tmp_path) == set()


def test_get_top_level_deps_combines_python_and_node_metadata(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\ndependencies = ["Python_Pkg>=1"]\n',
        encoding="utf-8",
    )
    (tmp_path / "package.json").write_text(
        '{"dependencies": {"node_pkg": "^1.0.0"}}',
        encoding="utf-8",
    )

    assert get_top_level_deps(tmp_path) == {"python-pkg", "node-pkg"}
