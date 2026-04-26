from library_skills.deps import get_python_top_level_deps


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
