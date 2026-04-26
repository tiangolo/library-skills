import os
from pathlib import Path


def find_project_root(cwd: Path) -> Path | None:
    """Find the nearest Python project/environment root walking up from cwd."""
    for directory in [cwd, *cwd.parents]:
        if (
            (directory / "pyproject.toml").is_file()
            or (directory / "uv.lock").is_file()
            or (directory / ".venv" / "pyvenv.cfg").is_file()
        ):
            return directory
    return None


def find_venv(cwd: Path | None = None) -> Path | None:
    """Find the target Python environment.

    The CLI can run from an isolated tool environment (for example via uvx), so
    prefer project-local environment signals before accepting an active shell env.

    Resolution order:
    1. UV_PROJECT_ENVIRONMENT env var
    2. Nearest project .venv
    3. VIRTUAL_ENV if it appears to belong to the project/user cwd
    4. CONDA_PREFIX env var
    """
    cwd = cwd or Path.cwd()
    project_root = find_project_root(cwd) or cwd

    # 1. UV_PROJECT_ENVIRONMENT
    uv_proj_env = os.environ.get("UV_PROJECT_ENVIRONMENT")
    if uv_proj_env:
        path = Path(uv_proj_env)
        if not path.is_absolute():
            path = project_root / path
        if (path / "pyvenv.cfg").is_file():
            return path

    # 2. Nearest project .venv
    for directory in [cwd, *cwd.parents]:
        dot_venv = directory / ".venv"
        if dot_venv.is_dir() and (dot_venv / "pyvenv.cfg").is_file():
            return dot_venv

    # 3. VIRTUAL_ENV, but avoid uvx/tool environments outside the project tree
    virtual_env = os.environ.get("VIRTUAL_ENV")
    if virtual_env:
        path = Path(virtual_env)
        if (path / "pyvenv.cfg").is_file() and _is_relative_to(path, project_root):
            return path

    # 4. CONDA_PREFIX
    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix:
        path = Path(conda_prefix)
        if path.is_dir():
            return path

    return None


def get_site_packages_dir(venv_path: Path) -> Path | None:
    """Get the site-packages directory for a Python environment."""
    windows_site_packages = venv_path / "Lib" / "site-packages"
    if windows_site_packages.is_dir():
        return windows_site_packages

    # Unix: lib/pythonX.Y/site-packages or lib64/pythonX.Y/site-packages
    for lib_name in ("lib", "lib64"):
        lib_dir = venv_path / lib_name
        if lib_dir.is_dir():
            for child in sorted(lib_dir.iterdir(), reverse=True):
                site_packages = child / "site-packages"
                if (
                    child.name.startswith("python")
                    and child.is_dir()
                    and site_packages.is_dir()
                ):
                    return site_packages

    return None


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True
