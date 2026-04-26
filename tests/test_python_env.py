from pathlib import Path

from library_skills.python_env import (
    find_project_root,
    find_venv,
    get_site_packages_dir,
)


def make_venv(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "pyvenv.cfg").write_text("home = /usr/bin\n", encoding="utf-8")
    return path


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


def test_find_venv_prefers_uv_project_environment(monkeypatch, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n", encoding="utf-8"
    )
    uv_env = make_venv(project / ".custom-venv")
    dot_venv = make_venv(project / ".venv")
    monkeypatch.setenv("UV_PROJECT_ENVIRONMENT", ".custom-venv")
    monkeypatch.setenv("VIRTUAL_ENV", str(dot_venv))

    assert find_venv(project) == uv_env


def test_find_venv_ignores_virtual_env_outside_project(monkeypatch, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    outside = make_venv(tmp_path / "tool-env")
    monkeypatch.delenv("UV_PROJECT_ENVIRONMENT", raising=False)
    monkeypatch.setenv("VIRTUAL_ENV", str(outside))
    monkeypatch.delenv("CONDA_PREFIX", raising=False)

    assert find_venv(project) is None


def test_find_venv_uses_conda_prefix_when_no_project_env(monkeypatch, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    conda = tmp_path / "conda-env"
    conda.mkdir()
    monkeypatch.delenv("UV_PROJECT_ENVIRONMENT", raising=False)
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
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
