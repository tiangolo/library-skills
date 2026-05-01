from pathlib import Path

from library_skills.python_env import (
    find_node_modules,
    find_project_root,
    find_venv,
    get_site_packages_dir,
)


def make_venv(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "pyvenv.cfg").write_text("home = /usr/bin\n", encoding="utf-8")
    return path


def clear_python_env_vars(monkeypatch) -> None:
    monkeypatch.delenv("UV_PROJECT_ENVIRONMENT", raising=False)
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    monkeypatch.delenv("CONDA_PREFIX", raising=False)


def test_find_project_root_uses_nearest_python_project_marker(tmp_path):
    root = tmp_path / "repo"
    subproject = root / "packages" / "api"
    nested = subproject / "src" / "pkg"
    root.mkdir(parents=True)
    subproject.mkdir(parents=True)
    nested.mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname = 'root'\n", encoding="utf-8")
    (subproject / "uv.lock").write_text("", encoding="utf-8")

    assert find_project_root(nested) == subproject


def test_find_project_root_uses_node_project_markers(tmp_path):
    project = tmp_path / "project"
    nested = project / "src"
    nested.mkdir(parents=True)
    (project / "package.json").write_text("{}", encoding="utf-8")

    assert find_project_root(nested) == project

    (project / "package.json").unlink()
    (project / "node_modules").mkdir()

    assert find_project_root(nested) == project


def test_find_venv_prefers_uv_project_environment(monkeypatch, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n", encoding="utf-8"
    )
    uv_env = make_venv(project / ".custom-venv")
    dot_venv = make_venv(project / ".venv")
    clear_python_env_vars(monkeypatch)
    monkeypatch.setenv("UV_PROJECT_ENVIRONMENT", ".custom-venv")
    monkeypatch.setenv("VIRTUAL_ENV", str(dot_venv))

    assert find_venv(project) == uv_env


def test_find_venv_supports_pep_832_redirect_file(monkeypatch, tmp_path):
    project = tmp_path / "project"
    nested = project / "src" / "pkg"
    nested.mkdir(parents=True)
    venv = make_venv(tmp_path / "envs" / "project")
    (project / ".venv").write_text("../envs/project\nignored\n", encoding="utf-8")
    clear_python_env_vars(monkeypatch)

    assert find_project_root(nested) == project
    assert find_venv(nested) == venv


def test_find_venv_supports_absolute_pep_832_redirect_file(monkeypatch, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    venv = make_venv(tmp_path / "env")
    (project / ".venv").write_text(str(venv), encoding="utf-8")
    clear_python_env_vars(monkeypatch)

    assert find_venv(project) == venv


def test_find_venv_ignores_invalid_pep_832_redirect_file(monkeypatch, tmp_path):
    project = tmp_path / "project"
    nested = project / "pkg"
    nested.mkdir(parents=True)
    (project / ".venv").write_text("missing\n", encoding="utf-8")
    clear_python_env_vars(monkeypatch)

    assert find_project_root(nested) is None
    assert find_venv(nested) is None

    (project / ".venv").write_text("", encoding="utf-8")
    assert find_project_root(nested) is None
    assert find_venv(nested) is None


def test_find_venv_ignores_invalid_pep_832_entries(monkeypatch, tmp_path):
    project = tmp_path / "project"
    nested = project / "pkg"
    nested.mkdir(parents=True)
    (project / ".venv").mkdir()
    clear_python_env_vars(monkeypatch)

    assert find_project_root(nested) is None
    assert find_venv(nested) is None

    (project / ".venv").rmdir()
    (project / ".venv").write_text("env\n", encoding="utf-8")

    def read_text(self: Path, *args, **kwargs) -> str:
        raise OSError

    monkeypatch.setattr(Path, "read_text", read_text)
    assert find_project_root(nested) is None
    assert find_venv(nested) is None


def test_find_venv_ignores_virtual_env_outside_project(monkeypatch, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    outside = make_venv(tmp_path / "tool-env")
    clear_python_env_vars(monkeypatch)
    monkeypatch.setenv("VIRTUAL_ENV", str(outside))

    assert find_venv(project) is None


def test_find_venv_uses_virtual_env_inside_project(monkeypatch, tmp_path):
    project = tmp_path / "project"
    nested = project / "src"
    nested.mkdir(parents=True)
    (project / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n", encoding="utf-8"
    )
    virtual_env = make_venv(project / "env")
    clear_python_env_vars(monkeypatch)
    monkeypatch.setenv("VIRTUAL_ENV", str(virtual_env))

    assert find_venv(nested) == virtual_env


def test_find_venv_uses_conda_prefix_when_no_project_env(monkeypatch, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    conda = tmp_path / "conda-env"
    conda.mkdir()
    clear_python_env_vars(monkeypatch)
    monkeypatch.setenv("CONDA_PREFIX", str(conda))

    assert find_venv(project) == conda


def test_get_site_packages_dir_supports_windows_lib_and_lib64(tmp_path):
    windows_env = tmp_path / "windows"
    windows_site = windows_env / "Lib" / "site-packages"
    windows_site.mkdir(parents=True)

    linux_env = tmp_path / "linux"
    linux_site = linux_env / "lib64" / "python3.12" / "site-packages"
    linux_site.mkdir(parents=True)

    assert get_site_packages_dir(windows_env) == windows_site
    assert get_site_packages_dir(linux_env) == linux_site


def test_get_site_packages_dir_returns_none_without_site_packages(tmp_path):
    venv = tmp_path / "venv"
    (venv / "lib" / "python3.12").mkdir(parents=True)

    assert get_site_packages_dir(venv) is None


def test_find_node_modules_uses_nearest_ancestor(tmp_path):
    project = tmp_path / "project"
    nested = project / "src" / "pkg"
    node_modules = project / "node_modules"
    nested.mkdir(parents=True)
    node_modules.mkdir()

    assert find_node_modules(nested) == node_modules
    assert find_node_modules(tmp_path / "missing") is None
